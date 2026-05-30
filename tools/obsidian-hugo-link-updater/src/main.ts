import { App, ItemView, Notice, Plugin, PluginSettingTab, Setting, TAbstractFile, TFile, WorkspaceLeaf } from 'obsidian';
import { ChildProcessWithoutNullStreams, spawn } from 'child_process';

interface HugoLinkUpdaterSettings {
  updateRelref: boolean;
  backendUrl: string;
  autoStartBackend: boolean;
  pythonCommand: string;
  serveCommand: string;
  initCommand: string;
}

const DEFAULT_SETTINGS: HugoLinkUpdaterSettings = {
  updateRelref: true,
  backendUrl: 'http://127.0.0.1:1314',
  autoStartBackend: true,
  pythonCommand: 'uv run python',
  serveCommand: 'scripts/serve.py',
  initCommand: 'uv run python init.py --no-shell',
};

const WIKI_EMBED_PATTERN = /!\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
const WIKI_LINK_PATTERN = /(?<!!)\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
const RELREF_PATTERN = /(\{\{<\s*relref\s+")([^"]+)("\s*>\}\})/g;
const BLOG_WORKSPACE_VIEW = 'hugo-blog-workspace-view';

interface BlogPage {
  path: string;
  title: string;
  date: string;
  draft: boolean;
  modified: string;
  directory: string;
  normalized: boolean;
  normalize_reasons: string[];
  preview_url?: string;
  scope?: 'normal' | 'pending';
}

interface HealthResponse {
  status: string;
  project_root: string;
  content_dir: string;
  hugo_available: boolean;
  issues: { errors: number; warnings: number };
}

interface CleanupResponse {
  unused_images: string[];
  deleted: string[];
}

type BlogTab = 'drafts' | 'needs' | 'pending' | 'images';
type BlogSort = 'modified' | 'date' | 'title' | 'directory';

export default class HugoLinkUpdaterPlugin extends Plugin {
  settings: HugoLinkUpdaterSettings = DEFAULT_SETTINGS;
  private updating = false;
  private backendProcess: ChildProcessWithoutNullStreams | null = null;
  client!: BlogBackendClient;

  async onload() {
    await this.loadSettings();
    this.client = new BlogBackendClient(() => this.settings.backendUrl);
    this.addSettingTab(new HugoLinkUpdaterSettingTab(this.app, this));
    this.registerView(BLOG_WORKSPACE_VIEW, leaf => new BlogWorkspaceView(leaf, this));
    this.addRibbonIcon('newspaper', 'Blog Workspace', () => {
      void this.activateBlogWorkspace();
    });
    this.addCommand({
      id: 'open-blog-workspace',
      name: 'Open blog workspace',
      callback: () => void this.activateBlogWorkspace(),
    });
    this.addCommand({
      id: 'normalize-current-blog-post',
      name: 'Normalize current blog post',
      callback: () => void this.normalizeCurrentFile(),
    });
    this.addCommand({
      id: 'cleanup-unused-blog-images',
      name: 'Cleanup unused blog images',
      callback: () => void this.cleanupUnusedImages(),
    });
    this.addCommand({
      id: 'initialize-blog-environment',
      name: 'Initialize blog Python environment',
      callback: () => void this.initializeEnvironment(),
    });

    this.registerEvent(
      this.app.vault.on('rename', (file, oldPath) => {
        if (this.updating) {
          return;
        }
        void this.handleRename(file, oldPath);
      })
    );
    this.registerEvent(this.app.vault.on('modify', () => this.refreshWorkspaceSoon()));
    this.registerEvent(this.app.vault.on('delete', () => this.refreshWorkspaceSoon()));
    this.app.workspace.onLayoutReady(() => {
      if (this.settings.autoStartBackend) {
        void this.ensureBackend();
      }
    });
  }

  async onunload() {
    if (this.backendProcess) {
      this.backendProcess.kill();
      this.backendProcess = null;
    }
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async activateBlogWorkspace() {
    await this.ensureBackend();
    const leaves = this.app.workspace.getLeavesOfType(BLOG_WORKSPACE_VIEW);
    const leaf = leaves[0] ?? this.app.workspace.getRightLeaf(false);
    await leaf.setViewState({ type: BLOG_WORKSPACE_VIEW, active: true });
    this.app.workspace.revealLeaf(leaf);
  }

  async ensureBackend(): Promise<boolean> {
    if (await this.client.isHealthy()) {
      return true;
    }
    if (!this.settings.autoStartBackend) {
      new Notice('Blog backend is not running.');
      return false;
    }
    if (this.backendProcess) {
      return false;
    }
    const cwd = getVaultBasePath(this.app);
    const command = `${this.settings.pythonCommand} ${this.settings.serveCommand}`;
    const parts = splitShellCommand(command);
    if (!parts.length) {
      new Notice('Blog backend command is empty.');
      return false;
    }
    this.backendProcess = spawn(parts[0], parts.slice(1), { cwd });
    this.backendProcess.on('exit', () => {
      this.backendProcess = null;
      this.refreshWorkspaceSoon();
    });
    this.backendProcess.stderr.on('data', data => console.error('[hugo-blog-workspace]', String(data)));
    this.backendProcess.stdout.on('data', data => console.log('[hugo-blog-workspace]', String(data)));
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await sleep(500);
      if (await this.client.isHealthy()) {
        new Notice('Blog backend started.');
        return true;
      }
    }
    new Notice('Blog backend did not become ready. Run python init.py, then python scripts/serve.py.');
    return false;
  }

  async initializeEnvironment() {
    const cwd = getVaultBasePath(this.app);
    const parts = splitShellCommand(this.settings.initCommand);
    if (!parts.length) {
      new Notice('Init command is empty.');
      return;
    }
    new Notice('Initializing blog environment...');
    await runCommand(parts, cwd);
    new Notice('Blog environment initialization finished. If LLM config is missing, run python init.py in a terminal.');
    await this.ensureBackend();
    this.refreshWorkspaceSoon();
  }

  async openBlogFile(path: string) {
    const file = this.app.vault.getAbstractFileByPath(path);
    if (file instanceof TFile) {
      await this.app.workspace.getLeaf(false).openFile(file);
    } else {
      new Notice(`File not found: ${path}`);
    }
  }

  async normalizePage(path: string) {
    if (!(await this.ensureBackend())) {
      return;
    }
    new Notice(`Normalizing ${basename(path)}...`);
    await this.client.normalize(path);
    new Notice(`Normalized ${basename(path)}`);
    this.refreshWorkspaceSoon();
  }

  async normalizeCurrentFile() {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      new Notice('No active file.');
      return;
    }
    await this.normalizePage(file.path);
  }

  async cleanupUnusedImages() {
    if (!(await this.ensureBackend())) {
      return;
    }
    const dryRun = await this.client.cleanupImages(false);
    if (!dryRun.unused_images.length) {
      new Notice('No unused images found.');
      return;
    }
    const confirmed = window.confirm(`Delete ${dryRun.unused_images.length} unused images?`);
    if (!confirmed) {
      return;
    }
    const result = await this.client.cleanupImages(true);
    new Notice(`Deleted ${result.deleted.length} unused images.`);
    this.refreshWorkspaceSoon();
  }

  refreshWorkspaceSoon() {
    window.setTimeout(() => {
      for (const leaf of this.app.workspace.getLeavesOfType(BLOG_WORKSPACE_VIEW)) {
        const view = leaf.view;
        if (view instanceof BlogWorkspaceView) {
          void view.refresh();
        }
      }
    }, 300);
  }

  private async handleRename(file: TAbstractFile, oldPath: string) {
    if (!(file instanceof TFile)) {
      return;
    }

    const oldBase = basename(oldPath);
    const newBase = file.basename;
    const oldStem = stripExtension(oldBase);
    const newStem = stripExtension(newBase);
    const oldRel = normalizePath(oldPath);
    const newRel = normalizePath(file.path);
    const oldRelNoExt = stripMdExtension(oldRel);
    const newRelNoExt = stripMdExtension(newRel);

    if (oldBase === newBase && oldRelNoExt === newRelNoExt) {
      return;
    }

    this.updating = true;
    try {
      const markdownFiles = this.app.vault.getMarkdownFiles();
      for (const mdFile of markdownFiles) {
        const original = await this.app.vault.read(mdFile);
        let updated = original;
        let changed = false;

        if (file.extension === 'md') {
          updated = this.replaceWikiTargets(updated, oldStem, newStem, oldRelNoExt, newRelNoExt);
          if (this.settings.updateRelref) {
            const relrefUpdated = this.replaceRelrefTargets(updated, oldRel, newRel);
            if (relrefUpdated !== updated) {
              updated = relrefUpdated;
              changed = true;
            }
          }
        } else {
          updated = this.replaceWikiTargets(updated, oldBase, newBase, oldBase, newBase, true);
        }

        if (updated !== original) {
          changed = true;
        }

        if (changed) {
          await this.app.vault.modify(mdFile, updated);
        }
      }
    } finally {
      this.updating = false;
    }
  }

  private replaceWikiTargets(
    content: string,
    oldStem: string,
    newStem: string,
    oldPath: string,
    newPath: string,
    imageOnly = false
  ): string {
    const replaceInner = (inner: string): string => {
      const parsed = parseWikiInner(inner);
      if (parsed.target === oldStem || parsed.target === oldPath || parsed.target === stripMdExtension(oldPath)) {
        const nextTarget = imageOnly ? newStem : chooseNewTarget(parsed.target, oldStem, newStem, oldPath, newPath);
        return formatWikiInner(nextTarget, parsed.anchor, parsed.alias);
      }
      return inner;
    };

    if (imageOnly) {
      return content.replace(WIKI_EMBED_PATTERN, (full, target, anchor = '', alias = '') => {
        const inner = `${target}${anchor}${alias}`;
        const replaced = replaceInner(inner);
        return replaced === inner ? full : `![[${replaced}]]`;
      });
    }

    let updated = content.replace(WIKI_EMBED_PATTERN, (full, target, anchor = '', alias = '') => {
      const inner = `${target}${anchor}${alias}`;
      const replaced = replaceInner(inner);
      return replaced === inner ? full : `![[${replaced}]]`;
    });

    updated = updated.replace(WIKI_LINK_PATTERN, (full, target, anchor = '', alias = '') => {
      const inner = `${target}${anchor}${alias}`;
      const replaced = replaceInner(inner);
      return replaced === inner ? full : `[[${replaced}]]`;
    });

    return updated;
  }

  private replaceRelrefTargets(content: string, oldRel: string, newRel: string): string {
    const oldCandidates = new Set([
      oldRel,
      stripMdExtension(oldRel),
      `${stripMdExtension(oldRel)}.md`,
    ]);
    return content.replace(RELREF_PATTERN, (full, prefix, path, suffix) => {
      if (oldCandidates.has(path)) {
        const nextPath = path.endsWith('.md') ? newRel : stripMdExtension(newRel);
        return `${prefix}${nextPath}${suffix}`;
      }
      return full;
    });
  }
}

class BlogBackendClient {
  constructor(private readonly urlProvider: () => string) {}

  async isHealthy(): Promise<boolean> {
    try {
      const health = await this.health();
      return health.status === 'ok';
    } catch {
      return false;
    }
  }

  async health(): Promise<HealthResponse> {
    return this.getJson('/api/health');
  }

  async listContent(scope: 'normal' | 'pending'): Promise<BlogPage[]> {
    return this.getJson(`/api/content?status=all&scope=${scope}`);
  }

  async normalize(path: string): Promise<unknown> {
    return this.postJson(`/api/content-normalize/${encodeURIComponent(path)}`, { use_llm: true });
  }

  async cleanupImages(deleteImages: boolean): Promise<CleanupResponse> {
    return this.postJson('/api/images/cleanup', { delete: deleteImages });
  }

  private async getJson<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl()}${path}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json() as Promise<T>;
  }

  private async postJson<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json() as Promise<T>;
  }

  private baseUrl(): string {
    return this.urlProvider().replace(/\/+$/, '');
  }
}

class BlogWorkspaceView extends ItemView {
  private tab: BlogTab = 'drafts';
  private sort: BlogSort = 'modified';
  private query = '';
  private pages: BlogPage[] = [];
  private pending: BlogPage[] = [];
  private health: HealthResponse | null = null;
  private cleanup: CleanupResponse | null = null;

  constructor(leaf: WorkspaceLeaf, private readonly plugin: HugoLinkUpdaterPlugin) {
    super(leaf);
  }

  getViewType(): string {
    return BLOG_WORKSPACE_VIEW;
  }

  getDisplayText(): string {
    return 'Blog Workspace';
  }

  async onOpen() {
    await this.refresh();
  }

  async refresh() {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass('hugo-blog-workspace');
    container.createEl('h2', { text: 'Blog Workspace' });
    const status = container.createDiv({ cls: 'blog-status' });
    status.setText('Connecting...');
    try {
      await this.plugin.ensureBackend();
      this.health = await this.plugin.client.health();
      this.pages = await this.plugin.client.listContent('normal');
      this.pending = await this.plugin.client.listContent('pending');
      status.setText(
        `Backend OK · errors ${this.health.issues.errors} · warnings ${this.health.issues.warnings}`
      );
    } catch (error) {
      status.setText(`Backend unavailable: ${String(error)}`);
      this.renderToolbar(container);
      return;
    }
    this.renderToolbar(container);
    this.renderList(container);
  }

  private renderToolbar(container: HTMLElement) {
    const actions = container.createDiv({ cls: 'blog-actions' });
    actions.createEl('button', { text: 'Refresh' }).onclick = () => void this.refresh();
    actions.createEl('button', { text: 'Normalize current' }).onclick = () => void this.plugin.normalizeCurrentFile();
    actions.createEl('button', { text: 'Cleanup images' }).onclick = () => void this.cleanupImages();

    const tabs = container.createDiv({ cls: 'blog-tabs' });
    this.addTab(tabs, 'drafts', 'Drafts');
    this.addTab(tabs, 'needs', 'Needs normalize');
    this.addTab(tabs, 'pending', 'Pending');
    this.addTab(tabs, 'images', 'Image issues');

    const filters = container.createDiv({ cls: 'blog-filters' });
    const search = filters.createEl('input', { type: 'search', placeholder: 'Search title or path' });
    search.value = this.query;
    search.oninput = () => {
      this.query = search.value;
      this.renderListOnly();
    };
    const sort = filters.createEl('select');
    for (const [value, label] of [
      ['modified', 'Modified'],
      ['date', 'Date'],
      ['title', 'Title'],
      ['directory', 'Directory'],
    ] as [BlogSort, string][]) {
      const option = sort.createEl('option', { text: label, value });
      option.selected = this.sort === value;
    }
    sort.onchange = () => {
      this.sort = sort.value as BlogSort;
      this.renderListOnly();
    };
  }

  private addTab(container: HTMLElement, tab: BlogTab, label: string) {
    const button = container.createEl('button', { text: label });
    if (this.tab === tab) {
      button.addClass('is-active');
    }
    button.onclick = () => {
      this.tab = tab;
      void this.refresh();
    };
  }

  private async cleanupImages() {
    try {
      this.cleanup = await this.plugin.client.cleanupImages(false);
      this.tab = 'images';
      this.renderListOnly();
      if (!this.cleanup.unused_images.length) {
        new Notice('No unused images found.');
        return;
      }
      const confirmed = window.confirm(`Delete ${this.cleanup.unused_images.length} unused images?`);
      if (confirmed) {
        this.cleanup = await this.plugin.client.cleanupImages(true);
        new Notice(`Deleted ${this.cleanup.deleted.length} unused images.`);
        await this.refresh();
      }
    } catch (error) {
      new Notice(`Image cleanup failed: ${String(error)}`);
    }
  }

  private renderListOnly() {
    const container = this.containerEl.children[1] as HTMLElement;
    const old = container.querySelector('.blog-list');
    old?.remove();
    this.renderList(container);
  }

  private renderList(container: HTMLElement) {
    const list = container.createDiv({ cls: 'blog-list' });
    if (this.tab === 'images') {
      const images = this.cleanup?.unused_images ?? [];
      list.createEl('h3', { text: `Unused images (${images.length})` });
      for (const image of images.slice(0, 200)) {
        list.createDiv({ cls: 'blog-image-row', text: image });
      }
      return;
    }

    const pages = this.filteredPages();
    list.createEl('h3', { text: `${this.currentLabel()} (${pages.length})` });
    for (const page of pages) {
      const row = list.createDiv({ cls: 'blog-row' });
      const title = row.createDiv({ cls: 'blog-title', text: page.title || page.path });
      title.onclick = () => void this.plugin.openBlogFile(page.path);
      row.createDiv({ cls: 'blog-meta', text: `${page.directory || '-'} · ${page.modified || page.date || '-'}` });
      if (!page.normalized) {
        row.createDiv({ cls: 'blog-warn', text: page.normalize_reasons.join(', ') });
      }
      const buttons = row.createDiv({ cls: 'blog-row-actions' });
      buttons.createEl('button', { text: 'Open' }).onclick = () => void this.plugin.openBlogFile(page.path);
      buttons.createEl('button', { text: 'Normalize' }).onclick = () => void this.plugin.normalizePage(page.path);
    }
  }

  private filteredPages(): BlogPage[] {
    const source = this.tab === 'pending' ? this.pending : this.pages;
    const query = this.query.trim().toLowerCase();
    return source
      .filter(page => {
        if (this.tab === 'drafts' && !page.draft) return false;
        if (this.tab === 'needs' && page.normalized) return false;
        if (query && !`${page.title} ${page.path}`.toLowerCase().includes(query)) return false;
        return true;
      })
      .sort((left, right) => comparePages(left, right, this.sort));
  }

  private currentLabel(): string {
    if (this.tab === 'drafts') return 'Drafts';
    if (this.tab === 'needs') return 'Needs normalize';
    if (this.tab === 'pending') return 'Pending';
    return 'Images';
  }
}

class HugoLinkUpdaterSettingTab extends PluginSettingTab {
  plugin: HugoLinkUpdaterPlugin;

  constructor(app: App, plugin: HugoLinkUpdaterPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl('h2', { text: 'Hugo Link Updater' });

    new Setting(containerEl)
      .setName('Update Hugo relref shortcodes')
      .setDesc('When renaming markdown files, also update {{< relref "..." >}} paths.')
      .addToggle(toggle =>
        toggle
          .setValue(this.plugin.settings.updateRelref)
          .onChange(async value => {
            this.plugin.settings.updateRelref = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Backend URL')
      .setDesc('Python admin backend URL used by Blog Workspace.')
      .addText(text =>
        text
          .setValue(this.plugin.settings.backendUrl)
          .onChange(async value => {
            this.plugin.settings.backendUrl = value.trim() || DEFAULT_SETTINGS.backendUrl;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Auto-start Python backend')
      .setDesc('Start the local Python preview/admin backend when Obsidian opens.')
      .addToggle(toggle =>
        toggle
          .setValue(this.plugin.settings.autoStartBackend)
          .onChange(async value => {
            this.plugin.settings.autoStartBackend = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Python command')
      .setDesc('Command prefix used to start the backend.')
      .addText(text =>
        text
          .setValue(this.plugin.settings.pythonCommand)
          .onChange(async value => {
            this.plugin.settings.pythonCommand = value.trim() || DEFAULT_SETTINGS.pythonCommand;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Serve command')
      .setDesc('Script passed to the Python command.')
      .addText(text =>
        text
          .setValue(this.plugin.settings.serveCommand)
          .onChange(async value => {
            this.plugin.settings.serveCommand = value.trim() || DEFAULT_SETTINGS.serveCommand;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Init command')
      .setDesc('Command used for first-time Python environment setup.')
      .addText(text =>
        text
          .setValue(this.plugin.settings.initCommand)
          .onChange(async value => {
            this.plugin.settings.initCommand = value.trim() || DEFAULT_SETTINGS.initCommand;
            await this.plugin.saveSettings();
          })
      );
  }
}

interface ParsedWikiInner {
  target: string;
  anchor?: string;
  alias?: string;
}

function parseWikiInner(inner: string): ParsedWikiInner {
  let target = inner.trim();
  let alias: string | undefined;
  if (target.includes('|')) {
    const parts = target.split('|');
    target = parts[0].trim();
    alias = parts.slice(1).join('|').trim() || undefined;
  }
  let anchor: string | undefined;
  if (target.includes('#')) {
    const parts = target.split('#');
    target = parts[0].trim();
    anchor = parts.slice(1).join('#').trim() || undefined;
  }
  return { target, anchor, alias };
}

function formatWikiInner(target: string, anchor?: string, alias?: string): string {
  let value = target;
  if (anchor) {
    value += `#${anchor}`;
  }
  if (alias) {
    value += `|${alias}`;
  }
  return value;
}

function chooseNewTarget(
  currentTarget: string,
  oldStem: string,
  newStem: string,
  oldPath: string,
  newPath: string
): string {
  if (currentTarget === oldPath || currentTarget === stripMdExtension(oldPath)) {
    return newPath.includes('/') ? newPath : newStem;
  }
  return newStem;
}

function basename(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1] ?? path;
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, '/');
}

function stripExtension(name: string): string {
  const index = name.lastIndexOf('.');
  return index >= 0 ? name.slice(0, index) : name;
}

function stripMdExtension(path: string): string {
  return path.endsWith('.md') ? path.slice(0, -3) : path;
}

function comparePages(left: BlogPage, right: BlogPage, sort: BlogSort): number {
  if (sort === 'title') {
    return (left.title || left.path).localeCompare(right.title || right.path);
  }
  if (sort === 'directory') {
    return `${left.directory}/${left.title}`.localeCompare(`${right.directory}/${right.title}`);
  }
  const leftValue = sort === 'date' ? left.date : left.modified;
  const rightValue = sort === 'date' ? right.date : right.modified;
  return String(rightValue || '').localeCompare(String(leftValue || ''));
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

function getVaultBasePath(app: App): string {
  const adapter = app.vault.adapter as { getBasePath?: () => string; basePath?: string };
  return adapter.getBasePath?.() ?? adapter.basePath ?? '.';
}

function splitShellCommand(command: string): string[] {
  const parts: string[] = [];
  let current = '';
  let quote: string | null = null;
  for (const char of command.trim()) {
    if ((char === '"' || char === "'") && quote === null) {
      quote = char;
      continue;
    }
    if (char === quote) {
      quote = null;
      continue;
    }
    if (char === ' ' && quote === null) {
      if (current) {
        parts.push(current);
        current = '';
      }
      continue;
    }
    current += char;
  }
  if (current) {
    parts.push(current);
  }
  return parts;
}

function runCommand(parts: string[], cwd: string): Promise<void> {
  return new Promise(resolve => {
    const child = spawn(parts[0], parts.slice(1), { cwd });
    child.stdout.on('data', data => console.log('[hugo-blog-workspace:init]', String(data)));
    child.stderr.on('data', data => console.error('[hugo-blog-workspace:init]', String(data)));
    child.on('exit', () => resolve());
    child.on('error', error => {
      console.error('[hugo-blog-workspace:init]', error);
      resolve();
    });
  });
}

import { App, Plugin, PluginSettingTab, Setting, TAbstractFile, TFile } from 'obsidian';

interface HugoLinkUpdaterSettings {
  updateRelref: boolean;
}

const DEFAULT_SETTINGS: HugoLinkUpdaterSettings = {
  updateRelref: true,
};

const WIKI_EMBED_PATTERN = /!\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
const WIKI_LINK_PATTERN = /(?<!!)\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
const RELREF_PATTERN = /(\{\{<\s*relref\s+")([^"]+)("\s*>\}\})/g;

export default class HugoLinkUpdaterPlugin extends Plugin {
  settings: HugoLinkUpdaterSettings = DEFAULT_SETTINGS;
  private updating = false;

  async onload() {
    await this.loadSettings();
    this.addSettingTab(new HugoLinkUpdaterSettingTab(this.app, this));

    this.registerEvent(
      this.app.vault.on('rename', (file, oldPath) => {
        if (this.updating) {
          return;
        }
        void this.handleRename(file, oldPath);
      })
    );
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
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

var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/main.ts
var main_exports = {};
__export(main_exports, {
  default: () => HugoLinkUpdaterPlugin
});
module.exports = __toCommonJS(main_exports);
var import_obsidian = require("obsidian");
var import_child_process = require("child_process");
var DEFAULT_SETTINGS = {
  updateRelref: true,
  backendUrl: "http://127.0.0.1:1314",
  autoStartBackend: true,
  pythonCommand: "uv run python",
  serveCommand: "scripts/serve.py",
  initCommand: "uv run python init.py --no-shell"
};
var WIKI_EMBED_PATTERN = /!\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
var WIKI_LINK_PATTERN = /(?<!!)\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
var RELREF_PATTERN = /(\{\{<\s*relref\s+")([^"]+)("\s*>\}\})/g;
var BLOG_WORKSPACE_VIEW = "hugo-blog-workspace-view";
var HugoLinkUpdaterPlugin = class extends import_obsidian.Plugin {
  constructor() {
    super(...arguments);
    this.settings = DEFAULT_SETTINGS;
    this.updating = false;
    this.backendProcess = null;
  }
  async onload() {
    await this.loadSettings();
    this.client = new BlogBackendClient(() => this.settings.backendUrl);
    this.addSettingTab(new HugoLinkUpdaterSettingTab(this.app, this));
    this.registerView(BLOG_WORKSPACE_VIEW, (leaf) => new BlogWorkspaceView(leaf, this));
    this.addRibbonIcon("newspaper", "Blog Workspace", () => {
      void this.activateBlogWorkspace();
    });
    this.addCommand({
      id: "open-blog-workspace",
      name: "Open blog workspace",
      callback: () => void this.activateBlogWorkspace()
    });
    this.addCommand({
      id: "normalize-current-blog-post",
      name: "Normalize current blog post",
      callback: () => void this.normalizeCurrentFile()
    });
    this.addCommand({
      id: "cleanup-unused-blog-images",
      name: "Cleanup unused blog images",
      callback: () => void this.cleanupUnusedImages()
    });
    this.addCommand({
      id: "initialize-blog-environment",
      name: "Initialize blog Python environment",
      callback: () => void this.initializeEnvironment()
    });
    this.registerEvent(
      this.app.vault.on("rename", (file, oldPath) => {
        if (this.updating) {
          return;
        }
        void this.handleRename(file, oldPath);
      })
    );
    this.registerEvent(this.app.vault.on("modify", () => this.refreshWorkspaceSoon()));
    this.registerEvent(this.app.vault.on("delete", () => this.refreshWorkspaceSoon()));
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
    var _a;
    await this.ensureBackend();
    const leaves = this.app.workspace.getLeavesOfType(BLOG_WORKSPACE_VIEW);
    const leaf = (_a = leaves[0]) != null ? _a : this.app.workspace.getRightLeaf(false);
    await leaf.setViewState({ type: BLOG_WORKSPACE_VIEW, active: true });
    this.app.workspace.revealLeaf(leaf);
  }
  async ensureBackend() {
    if (await this.client.isHealthy()) {
      return true;
    }
    if (!this.settings.autoStartBackend) {
      new import_obsidian.Notice("Blog backend is not running.");
      return false;
    }
    if (this.backendProcess) {
      return false;
    }
    const cwd = getVaultBasePath(this.app);
    const command = `${this.settings.pythonCommand} ${this.settings.serveCommand}`;
    const parts = splitShellCommand(command);
    if (!parts.length) {
      new import_obsidian.Notice("Blog backend command is empty.");
      return false;
    }
    this.backendProcess = (0, import_child_process.spawn)(parts[0], parts.slice(1), { cwd });
    this.backendProcess.on("exit", () => {
      this.backendProcess = null;
      this.refreshWorkspaceSoon();
    });
    this.backendProcess.stderr.on("data", (data) => console.error("[hugo-blog-workspace]", String(data)));
    this.backendProcess.stdout.on("data", (data) => console.log("[hugo-blog-workspace]", String(data)));
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await sleep(500);
      if (await this.client.isHealthy()) {
        new import_obsidian.Notice("Blog backend started.");
        return true;
      }
    }
    new import_obsidian.Notice("Blog backend did not become ready. Run python init.py, then python scripts/serve.py.");
    return false;
  }
  async initializeEnvironment() {
    const cwd = getVaultBasePath(this.app);
    const parts = splitShellCommand(this.settings.initCommand);
    if (!parts.length) {
      new import_obsidian.Notice("Init command is empty.");
      return;
    }
    new import_obsidian.Notice("Initializing blog environment...");
    await runCommand(parts, cwd);
    new import_obsidian.Notice("Blog environment initialization finished. If LLM config is missing, run python init.py in a terminal.");
    await this.ensureBackend();
    this.refreshWorkspaceSoon();
  }
  async openBlogFile(path) {
    const file = this.app.vault.getAbstractFileByPath(path);
    if (file instanceof import_obsidian.TFile) {
      await this.app.workspace.getLeaf(false).openFile(file);
    } else {
      new import_obsidian.Notice(`File not found: ${path}`);
    }
  }
  async normalizePage(path) {
    if (!await this.ensureBackend()) {
      return;
    }
    new import_obsidian.Notice(`Normalizing ${basename(path)}...`);
    await this.client.normalize(path);
    new import_obsidian.Notice(`Normalized ${basename(path)}`);
    this.refreshWorkspaceSoon();
  }
  async normalizeCurrentFile() {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      new import_obsidian.Notice("No active file.");
      return;
    }
    await this.normalizePage(file.path);
  }
  async cleanupUnusedImages() {
    if (!await this.ensureBackend()) {
      return;
    }
    const dryRun = await this.client.cleanupImages(false);
    if (!dryRun.unused_images.length) {
      new import_obsidian.Notice("No unused images found.");
      return;
    }
    const confirmed = window.confirm(`Delete ${dryRun.unused_images.length} unused images?`);
    if (!confirmed) {
      return;
    }
    const result = await this.client.cleanupImages(true);
    new import_obsidian.Notice(`Deleted ${result.deleted.length} unused images.`);
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
  async handleRename(file, oldPath) {
    if (!(file instanceof import_obsidian.TFile)) {
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
        if (file.extension === "md") {
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
  replaceWikiTargets(content, oldStem, newStem, oldPath, newPath, imageOnly = false) {
    const replaceInner = (inner) => {
      const parsed = parseWikiInner(inner);
      if (parsed.target === oldStem || parsed.target === oldPath || parsed.target === stripMdExtension(oldPath)) {
        const nextTarget = imageOnly ? newStem : chooseNewTarget(parsed.target, oldStem, newStem, oldPath, newPath);
        return formatWikiInner(nextTarget, parsed.anchor, parsed.alias);
      }
      return inner;
    };
    if (imageOnly) {
      return content.replace(WIKI_EMBED_PATTERN, (full, target, anchor = "", alias = "") => {
        const inner = `${target}${anchor}${alias}`;
        const replaced = replaceInner(inner);
        return replaced === inner ? full : `![[${replaced}]]`;
      });
    }
    let updated = content.replace(WIKI_EMBED_PATTERN, (full, target, anchor = "", alias = "") => {
      const inner = `${target}${anchor}${alias}`;
      const replaced = replaceInner(inner);
      return replaced === inner ? full : `![[${replaced}]]`;
    });
    updated = updated.replace(WIKI_LINK_PATTERN, (full, target, anchor = "", alias = "") => {
      const inner = `${target}${anchor}${alias}`;
      const replaced = replaceInner(inner);
      return replaced === inner ? full : `[[${replaced}]]`;
    });
    return updated;
  }
  replaceRelrefTargets(content, oldRel, newRel) {
    const oldCandidates = /* @__PURE__ */ new Set([
      oldRel,
      stripMdExtension(oldRel),
      `${stripMdExtension(oldRel)}.md`
    ]);
    return content.replace(RELREF_PATTERN, (full, prefix, path, suffix) => {
      if (oldCandidates.has(path)) {
        const nextPath = path.endsWith(".md") ? newRel : stripMdExtension(newRel);
        return `${prefix}${nextPath}${suffix}`;
      }
      return full;
    });
  }
};
var BlogBackendClient = class {
  constructor(urlProvider) {
    this.urlProvider = urlProvider;
  }
  async isHealthy() {
    try {
      const health = await this.health();
      return health.status === "ok";
    } catch (e) {
      return false;
    }
  }
  async health() {
    return this.getJson("/api/health");
  }
  async listContent(scope) {
    return this.getJson(`/api/content?status=all&scope=${scope}`);
  }
  async normalize(path) {
    return this.postJson(`/api/content-normalize/${encodeURIComponent(path)}`, { use_llm: true });
  }
  async cleanupImages(deleteImages) {
    return this.postJson("/api/images/cleanup", { delete: deleteImages });
  }
  async getJson(path) {
    const response = await fetch(`${this.baseUrl()}${path}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  }
  async postJson(path, payload) {
    const response = await fetch(`${this.baseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  }
  baseUrl() {
    return this.urlProvider().replace(/\/+$/, "");
  }
};
var BlogWorkspaceView = class extends import_obsidian.ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin;
    this.tab = "drafts";
    this.sort = "modified";
    this.query = "";
    this.pages = [];
    this.pending = [];
    this.health = null;
    this.cleanup = null;
  }
  getViewType() {
    return BLOG_WORKSPACE_VIEW;
  }
  getDisplayText() {
    return "Blog Workspace";
  }
  async onOpen() {
    await this.refresh();
  }
  async refresh() {
    const container = this.containerEl.children[1];
    container.empty();
    container.addClass("hugo-blog-workspace");
    container.createEl("h2", { text: "Blog Workspace" });
    const status = container.createDiv({ cls: "blog-status" });
    status.setText("Connecting...");
    try {
      await this.plugin.ensureBackend();
      this.health = await this.plugin.client.health();
      this.pages = await this.plugin.client.listContent("normal");
      this.pending = await this.plugin.client.listContent("pending");
      status.setText(
        `Backend OK \xB7 errors ${this.health.issues.errors} \xB7 warnings ${this.health.issues.warnings}`
      );
    } catch (error) {
      status.setText(`Backend unavailable: ${String(error)}`);
      this.renderToolbar(container);
      return;
    }
    this.renderToolbar(container);
    this.renderList(container);
  }
  renderToolbar(container) {
    const actions = container.createDiv({ cls: "blog-actions" });
    actions.createEl("button", { text: "Refresh" }).onclick = () => void this.refresh();
    actions.createEl("button", { text: "Normalize current" }).onclick = () => void this.plugin.normalizeCurrentFile();
    actions.createEl("button", { text: "Cleanup images" }).onclick = () => void this.cleanupImages();
    const tabs = container.createDiv({ cls: "blog-tabs" });
    this.addTab(tabs, "drafts", "Drafts");
    this.addTab(tabs, "needs", "Needs normalize");
    this.addTab(tabs, "pending", "Pending");
    this.addTab(tabs, "images", "Image issues");
    const filters = container.createDiv({ cls: "blog-filters" });
    const search = filters.createEl("input", { type: "search", placeholder: "Search title or path" });
    search.value = this.query;
    search.oninput = () => {
      this.query = search.value;
      this.renderListOnly();
    };
    const sort = filters.createEl("select");
    for (const [value, label] of [
      ["modified", "Modified"],
      ["date", "Date"],
      ["title", "Title"],
      ["directory", "Directory"]
    ]) {
      const option = sort.createEl("option", { text: label, value });
      option.selected = this.sort === value;
    }
    sort.onchange = () => {
      this.sort = sort.value;
      this.renderListOnly();
    };
  }
  addTab(container, tab, label) {
    const button = container.createEl("button", { text: label });
    if (this.tab === tab) {
      button.addClass("is-active");
    }
    button.onclick = () => {
      this.tab = tab;
      void this.refresh();
    };
  }
  async cleanupImages() {
    try {
      this.cleanup = await this.plugin.client.cleanupImages(false);
      this.tab = "images";
      this.renderListOnly();
      if (!this.cleanup.unused_images.length) {
        new import_obsidian.Notice("No unused images found.");
        return;
      }
      const confirmed = window.confirm(`Delete ${this.cleanup.unused_images.length} unused images?`);
      if (confirmed) {
        this.cleanup = await this.plugin.client.cleanupImages(true);
        new import_obsidian.Notice(`Deleted ${this.cleanup.deleted.length} unused images.`);
        await this.refresh();
      }
    } catch (error) {
      new import_obsidian.Notice(`Image cleanup failed: ${String(error)}`);
    }
  }
  renderListOnly() {
    const container = this.containerEl.children[1];
    const old = container.querySelector(".blog-list");
    old == null ? void 0 : old.remove();
    this.renderList(container);
  }
  renderList(container) {
    var _a, _b;
    const list = container.createDiv({ cls: "blog-list" });
    if (this.tab === "images") {
      const images = (_b = (_a = this.cleanup) == null ? void 0 : _a.unused_images) != null ? _b : [];
      list.createEl("h3", { text: `Unused images (${images.length})` });
      for (const image of images.slice(0, 200)) {
        list.createDiv({ cls: "blog-image-row", text: image });
      }
      return;
    }
    const pages = this.filteredPages();
    list.createEl("h3", { text: `${this.currentLabel()} (${pages.length})` });
    for (const page of pages) {
      const row = list.createDiv({ cls: "blog-row" });
      const title = row.createDiv({ cls: "blog-title", text: page.title || page.path });
      title.onclick = () => void this.plugin.openBlogFile(page.path);
      row.createDiv({ cls: "blog-meta", text: `${page.directory || "-"} \xB7 ${page.modified || page.date || "-"}` });
      if (!page.normalized) {
        row.createDiv({ cls: "blog-warn", text: page.normalize_reasons.join(", ") });
      }
      const buttons = row.createDiv({ cls: "blog-row-actions" });
      buttons.createEl("button", { text: "Open" }).onclick = () => void this.plugin.openBlogFile(page.path);
      buttons.createEl("button", { text: "Normalize" }).onclick = () => void this.plugin.normalizePage(page.path);
    }
  }
  filteredPages() {
    const source = this.tab === "pending" ? this.pending : this.pages;
    const query = this.query.trim().toLowerCase();
    return source.filter((page) => {
      if (this.tab === "drafts" && !page.draft)
        return false;
      if (this.tab === "needs" && page.normalized)
        return false;
      if (query && !`${page.title} ${page.path}`.toLowerCase().includes(query))
        return false;
      return true;
    }).sort((left, right) => comparePages(left, right, this.sort));
  }
  currentLabel() {
    if (this.tab === "drafts")
      return "Drafts";
    if (this.tab === "needs")
      return "Needs normalize";
    if (this.tab === "pending")
      return "Pending";
    return "Images";
  }
};
var HugoLinkUpdaterSettingTab = class extends import_obsidian.PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }
  display() {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Hugo Link Updater" });
    new import_obsidian.Setting(containerEl).setName("Update Hugo relref shortcodes").setDesc('When renaming markdown files, also update {{< relref "..." >}} paths.').addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.updateRelref).onChange(async (value) => {
        this.plugin.settings.updateRelref = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Backend URL").setDesc("Python admin backend URL used by Blog Workspace.").addText(
      (text) => text.setValue(this.plugin.settings.backendUrl).onChange(async (value) => {
        this.plugin.settings.backendUrl = value.trim() || DEFAULT_SETTINGS.backendUrl;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Auto-start Python backend").setDesc("Start the local Python preview/admin backend when Obsidian opens.").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.autoStartBackend).onChange(async (value) => {
        this.plugin.settings.autoStartBackend = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Python command").setDesc("Command prefix used to start the backend.").addText(
      (text) => text.setValue(this.plugin.settings.pythonCommand).onChange(async (value) => {
        this.plugin.settings.pythonCommand = value.trim() || DEFAULT_SETTINGS.pythonCommand;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Serve command").setDesc("Script passed to the Python command.").addText(
      (text) => text.setValue(this.plugin.settings.serveCommand).onChange(async (value) => {
        this.plugin.settings.serveCommand = value.trim() || DEFAULT_SETTINGS.serveCommand;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Init command").setDesc("Command used for first-time Python environment setup.").addText(
      (text) => text.setValue(this.plugin.settings.initCommand).onChange(async (value) => {
        this.plugin.settings.initCommand = value.trim() || DEFAULT_SETTINGS.initCommand;
        await this.plugin.saveSettings();
      })
    );
  }
};
function parseWikiInner(inner) {
  let target = inner.trim();
  let alias;
  if (target.includes("|")) {
    const parts = target.split("|");
    target = parts[0].trim();
    alias = parts.slice(1).join("|").trim() || void 0;
  }
  let anchor;
  if (target.includes("#")) {
    const parts = target.split("#");
    target = parts[0].trim();
    anchor = parts.slice(1).join("#").trim() || void 0;
  }
  return { target, anchor, alias };
}
function formatWikiInner(target, anchor, alias) {
  let value = target;
  if (anchor) {
    value += `#${anchor}`;
  }
  if (alias) {
    value += `|${alias}`;
  }
  return value;
}
function chooseNewTarget(currentTarget, oldStem, newStem, oldPath, newPath) {
  if (currentTarget === oldPath || currentTarget === stripMdExtension(oldPath)) {
    return newPath.includes("/") ? newPath : newStem;
  }
  return newStem;
}
function basename(path) {
  var _a;
  const parts = path.split("/");
  return (_a = parts[parts.length - 1]) != null ? _a : path;
}
function normalizePath(path) {
  return path.replace(/\\/g, "/");
}
function stripExtension(name) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(0, index) : name;
}
function stripMdExtension(path) {
  return path.endsWith(".md") ? path.slice(0, -3) : path;
}
function comparePages(left, right, sort) {
  if (sort === "title") {
    return (left.title || left.path).localeCompare(right.title || right.path);
  }
  if (sort === "directory") {
    return `${left.directory}/${left.title}`.localeCompare(`${right.directory}/${right.title}`);
  }
  const leftValue = sort === "date" ? left.date : left.modified;
  const rightValue = sort === "date" ? right.date : right.modified;
  return String(rightValue || "").localeCompare(String(leftValue || ""));
}
function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
function getVaultBasePath(app) {
  var _a, _b, _c;
  const adapter = app.vault.adapter;
  return (_c = (_b = (_a = adapter.getBasePath) == null ? void 0 : _a.call(adapter)) != null ? _b : adapter.basePath) != null ? _c : ".";
}
function splitShellCommand(command) {
  const parts = [];
  let current = "";
  let quote = null;
  for (const char of command.trim()) {
    if ((char === '"' || char === "'") && quote === null) {
      quote = char;
      continue;
    }
    if (char === quote) {
      quote = null;
      continue;
    }
    if (char === " " && quote === null) {
      if (current) {
        parts.push(current);
        current = "";
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
function runCommand(parts, cwd) {
  return new Promise((resolve) => {
    const child = (0, import_child_process.spawn)(parts[0], parts.slice(1), { cwd });
    child.stdout.on("data", (data) => console.log("[hugo-blog-workspace:init]", String(data)));
    child.stderr.on("data", (data) => console.error("[hugo-blog-workspace:init]", String(data)));
    child.on("exit", () => resolve());
    child.on("error", (error) => {
      console.error("[hugo-blog-workspace:init]", error);
      resolve();
    });
  });
}

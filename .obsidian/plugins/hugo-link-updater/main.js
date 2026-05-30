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
var DEFAULT_SETTINGS = {
  updateRelref: true
};
var WIKI_EMBED_PATTERN = /!\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
var WIKI_LINK_PATTERN = /(?<!!)\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]/g;
var RELREF_PATTERN = /(\{\{<\s*relref\s+")([^"]+)("\s*>\}\})/g;
var HugoLinkUpdaterPlugin = class extends import_obsidian.Plugin {
  constructor() {
    super(...arguments);
    this.settings = DEFAULT_SETTINGS;
    this.updating = false;
  }
  async onload() {
    await this.loadSettings();
    this.addSettingTab(new HugoLinkUpdaterSettingTab(this.app, this));
    this.registerEvent(
      this.app.vault.on("rename", (file, oldPath) => {
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

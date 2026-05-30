import Editor from '@monaco-editor/react';
import { useEffect, useMemo, useRef, useState } from 'react';

type Page = {
  path: string;
  title: string;
  date: string;
  modified: string;
  directory: string;
  tags: string[];
  draft: boolean;
  preview_url: string;
  normalized: boolean;
  normalize_reasons: string[];
  scope?: 'normal' | 'pending';
};

type Draft = Pick<Page, 'title' | 'date' | 'tags' | 'draft'>;
type SortKey = 'modified' | 'date' | 'title' | 'directory';

type MoveSuggestion = {
  target_path: string;
  title: string;
  reason: string;
};

type DocItem = {
  path: string;
  title: string;
  section: string;
  parts: string[];
  order: number;
  modified: number;
};

type DocTreeNode = {
  name: string;
  path: string;
  item?: DocItem;
  children: DocTreeNode[];
};

type DocHeading = {
  level: number;
  title: string;
  id: string;
};

type DocContent = {
  path: string;
  title: string;
  content: string;
  headings: DocHeading[];
};

type ValidationIssue = {
  severity: string;
  kind: string;
  source_path: string;
  line: number;
  raw_reference: string;
  target: string;
  message: string;
  candidates: string[];
};

type ValidationReport = {
  ok: boolean;
  issues: ValidationIssue[];
};

type ContentPayload = {
  path: string;
  content: string;
  page: Page;
  validation: ValidationReport;
  issues: ValidationIssue[];
};

type ContentPreview = {
  path: string;
  content: string;
  validation: ValidationReport;
};

type AdminFilters = {
  scope: 'normal' | 'pending';
  status: string;
  normalizeStatus: string;
  directory: string;
  query: string;
  sortKey: SortKey;
  sortDesc: boolean;
};

const previewOrigin = `${window.location.protocol}//${window.location.hostname}:1313`;

function draftFromPage(page: Page): Draft {
  return {
    title: page.title || '',
    date: page.date || '',
    tags: page.tags || [],
    draft: Boolean(page.draft),
  };
}

function isDirty(page: Page, draft: Draft): boolean {
  return JSON.stringify(draftFromPage(page)) !== JSON.stringify(draft);
}

function formatTags(tags: string[]): string {
  return tags.join(', ');
}

function parseTags(value: string): string[] {
  return value.split(',').map((tag) => tag.trim()).filter(Boolean);
}

function compareValues(a: string, b: string, desc: boolean): number {
  const result = a.localeCompare(b, 'zh-CN');
  return desc ? -result : result;
}

function appPath(path: '/admin/' | '/docs/' | '/issues/'): string {
  return path;
}

function editorPath(path: string): string {
  return `/editor/${encodeURIComponent(path)}`;
}

function readAdminFiltersFromUrl(): AdminFilters {
  const params = new URLSearchParams(window.location.search);
  const scope = params.get('scope') === 'pending' ? 'pending' : 'normal';
  const status = ['all', 'draft', 'published'].includes(params.get('status') || '') ? params.get('status') || 'all' : 'all';
  const normalizeStatus = ['all', 'normalized', 'needs-work'].includes(params.get('normalize') || '') ? params.get('normalize') || 'all' : 'all';
  const sortParam = params.get('sort') || 'modified';
  const sortKey = (['modified', 'date', 'title', 'directory'].includes(sortParam) ? sortParam : 'modified') as SortKey;
  return {
    scope,
    status,
    normalizeStatus,
    directory: params.get('directory') || 'all',
    query: params.get('q') || '',
    sortKey,
    sortDesc: params.get('desc') !== '0',
  };
}

function writeAdminFiltersToUrl(filters: AdminFilters) {
  const params = new URLSearchParams();
  if (filters.scope !== 'normal') params.set('scope', filters.scope);
  if (filters.status !== 'all') params.set('status', filters.status);
  if (filters.normalizeStatus !== 'all') params.set('normalize', filters.normalizeStatus);
  if (filters.directory !== 'all') params.set('directory', filters.directory);
  if (filters.query.trim()) params.set('q', filters.query.trim());
  if (filters.sortKey !== 'modified') params.set('sort', filters.sortKey);
  if (!filters.sortDesc) params.set('desc', '0');
  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}`;
  if (`${window.location.pathname}${window.location.search}` !== nextUrl) {
    window.history.replaceState(null, '', nextUrl);
  }
}

function TopNav({ active }: { active: 'admin' | 'docs' | 'issues' | 'editor' }) {
  return (
    <header className="topbar">
      <div>
        <h1>{active === 'docs' ? '开发文档' : active === 'issues' ? '内容错误' : active === 'editor' ? 'Markdown 编辑器' : '博客管理'}</h1>
        <p>
          {active === 'docs'
            ? '阅读工具链、流水线和源码说明。'
            : active === 'issues'
              ? '检查 preview/build 前会阻断的问题。'
              : active === 'editor'
                ? '编辑 content/posts 下的原始 Markdown。'
                : '管理文章 front matter、草稿和预览流程。'}
        </p>
      </div>
      <nav className="primaryNav">
        <a className={active === 'admin' ? 'active' : ''} href={appPath('/admin/')}>Admin</a>
        <a className={active === 'issues' || active === 'editor' ? 'active' : ''} href={appPath('/issues/')}>Issues</a>
        <a className={active === 'docs' ? 'active' : ''} href={appPath('/docs/')}>Docs</a>
        <a href={`${previewOrigin}/`}>Preview</a>
      </nav>
    </header>
  );
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function slugify(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fff-]+/g, '-').replace(/-{2,}/g, '-').replace(/^-|-$/g, '');
}

function inlineMarkdown(value: string): string {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function renderMarkdown(markdown: string): string {
  const lines = markdown.split(/\r?\n/);
  const html: string[] = [];
  const headingCounts = new Map<string, number>();
  let paragraph: string[] = [];
  let listOpen = false;
  let codeOpen = false;
  let codeLines: string[] = [];

  function flushParagraph() {
    if (paragraph.length) {
      html.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`);
      paragraph = [];
    }
  }

  function closeList() {
    if (listOpen) {
      html.push('</ul>');
      listOpen = false;
    }
  }

  for (const line of lines) {
    if (line.startsWith('```')) {
      if (codeOpen) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
        codeLines = [];
        codeOpen = false;
      } else {
        flushParagraph();
        closeList();
        codeOpen = true;
      }
      continue;
    }
    if (codeOpen) {
      codeLines.push(line);
      continue;
    }

    const heading = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
    if (heading) {
      flushParagraph();
      closeList();
      const title = heading[2];
      const base = slugify(title);
      const count = headingCounts.get(base) || 0;
      headingCounts.set(base, count + 1);
      const id = count === 0 ? base : `${base}-${count}`;
      html.push(`<h${heading[1].length} id="${id}">${inlineMarkdown(title)}</h${heading[1].length}>`);
      continue;
    }

    const item = /^\s*[-*]\s+(.+)$/.exec(line);
    if (item) {
      flushParagraph();
      if (!listOpen) {
        html.push('<ul>');
        listOpen = true;
      }
      html.push(`<li>${inlineMarkdown(item[1])}</li>`);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      closeList();
      continue;
    }
    paragraph.push(line.trim());
  }
  flushParagraph();
  closeList();
  if (codeOpen) {
    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
  }
  return html.join('\n');
}

function nodeLabel(name: string): string {
  if (name === 'source') return '源码说明';
  if (name.endsWith('.md')) return name.slice(0, -3);
  return name;
}

function buildDocTree(items: DocItem[]): DocTreeNode[] {
  const root: DocTreeNode = { name: '', path: '', children: [] };
  for (const item of items) {
    let current = root;
    const parts = item.parts?.length ? item.parts : item.path.split('/');
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/');
      let child = current.children.find((node) => node.name === part);
      if (!child) {
        child = { name: part, path, children: [] };
        current.children.push(child);
      }
      if (index === parts.length - 1) {
        child.item = item;
      }
      current = child;
    });
  }
  return root.children;
}

function hasActiveDoc(node: DocTreeNode, currentPath: string): boolean {
  return node.item?.path === currentPath || node.children.some((child) => hasActiveDoc(child, currentPath));
}

function DocTree({
  nodes,
  currentPath,
  expanded,
  onToggle,
  onOpen,
  level = 0,
}: {
  nodes: DocTreeNode[];
  currentPath: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onOpen: (path: string) => void;
  level?: number;
}) {
  return (
    <>
      {nodes.map((node) => {
        const expandable = node.children.length > 0;
        const active = hasActiveDoc(node, currentPath);
        const open = expanded.has(node.path) || active;
        return (
          <div className="docTreeNode" key={node.path}>
            <button
              className={`${node.item?.path === currentPath ? 'docLink active' : 'docLink'} ${expandable ? 'folder' : 'leaf'}`}
              style={{ paddingLeft: `${8 + level * 14}px` }}
              onClick={() => {
                if (node.item) {
                  onOpen(node.item.path);
                } else {
                  onToggle(node.path);
                }
              }}
            >
              {expandable && (
                <span className="treeChevron" onClick={(event) => {
                  event.stopPropagation();
                  onToggle(node.path);
                }}>
                  {open ? '▾' : '▸'}
                </span>
              )}
              <span>{node.item ? node.item.title : nodeLabel(node.name)}</span>
              {node.item && <small>{node.item.path}</small>}
            </button>
            {expandable && open && (
              <div className="docTreeChildren">
                <DocTree
                  nodes={node.children}
                  currentPath={currentPath}
                  expanded={expanded}
                  onToggle={onToggle}
                  onOpen={onOpen}
                  level={level + 1}
                />
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

function AdminView() {
  const initialFilters = useMemo(() => readAdminFiltersFromUrl(), []);
  const [pages, setPages] = useState<Page[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [scope, setScope] = useState<'normal' | 'pending'>(initialFilters.scope);
  const [status, setStatus] = useState(initialFilters.status);
  const [normalizeStatus, setNormalizeStatus] = useState(initialFilters.normalizeStatus);
  const [directory, setDirectory] = useState(initialFilters.directory);
  const [query, setQuery] = useState(initialFilters.query);
  const [sortKey, setSortKey] = useState<SortKey>(initialFilters.sortKey);
  const [sortDesc, setSortDesc] = useState(initialFilters.sortDesc);
  const [previewDrafts, setPreviewDrafts] = useState(false);
  const [busyPath, setBusyPath] = useState('');
  const [message, setMessage] = useState('');
  const [lastNormalizedPath, setLastNormalizedPath] = useState('');
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [suggestions, setSuggestions] = useState<Record<string, MoveSuggestion[]>>({});

  async function loadPages() {
    const response = await fetch(`/api/content?status=all&scope=${scope}`);
    const data = await response.json() as Page[];
    setPages(data);
    setDrafts(Object.fromEntries(data.map((page) => [page.path, draftFromPage(page)])));
    setSelected(new Set());
  }

  useEffect(() => {
    void loadPages();
  }, [scope]);

  useEffect(() => {
    writeAdminFiltersToUrl({
      scope,
      status,
      normalizeStatus,
      directory,
      query,
      sortKey,
      sortDesc,
    });
  }, [scope, status, normalizeStatus, directory, query, sortKey, sortDesc]);

  const directories = useMemo(() => {
    return Array.from(new Set(pages.map((page) => page.directory).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'zh-CN'));
  }, [pages]);

  const visiblePages = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return pages
      .filter((page) => status === 'all' || (status === 'draft' ? page.draft : !page.draft))
      .filter((page) => normalizeStatus === 'all' || (normalizeStatus === 'normalized' ? page.normalized : !page.normalized))
      .filter((page) => directory === 'all' || page.directory === directory)
      .filter((page) => {
        if (!keyword) return true;
        return [page.title, page.path, page.directory, formatTags(page.tags)].join(' ').toLowerCase().includes(keyword);
      })
      .sort((left, right) => compareValues(String(left[sortKey] || ''), String(right[sortKey] || ''), sortDesc));
  }, [pages, status, normalizeStatus, directory, query, sortKey, sortDesc]);

  function updateDraft(path: string, patch: Partial<Draft>) {
    setDrafts((current) => ({
      ...current,
      [path]: { ...current[path], ...patch },
    }));
  }

  function setSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDesc(!sortDesc);
    } else {
      setSortKey(nextKey);
      setSortDesc(nextKey === 'modified' || nextKey === 'date');
    }
  }

  function toggleSelected(path: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(path);
      } else {
        next.delete(path);
      }
      return next;
    });
  }

  async function savePage(page: Page): Promise<Page> {
    const response = await fetch(`/api/pages/${encodeURIComponent(page.path)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(drafts[page.path]),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const updated = await response.json() as Page;
    setPages((current) => current.map((item) => item.path === updated.path ? updated : item));
    setDrafts((current) => ({ ...current, [updated.path]: draftFromPage(updated) }));
    return updated;
  }

  async function saveAndMaybePreview(page: Page) {
    try {
      const dirty = isDirty(page, drafts[page.path]);
      setBusyPath(page.path);
      const updated = dirty ? await savePage(page) : page;
      setBusyPath('');
      if (dirty) {
        setMessage(`Saved ${updated.title}`);
        await new Promise((resolve) => window.setTimeout(resolve, 700));
      }
      window.open(`${previewOrigin}${updated.preview_url}`, '_blank');
    } catch (error) {
      setBusyPath('');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function restartPreview() {
    setMessage('Restarting preview...');
    const response = await fetch('/api/preview/drafts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drafts: previewDrafts }),
    });
    const result = await response.json();
    setMessage(`Preview restarted: ${result.url || previewOrigin}`);
  }

  async function saveAllAndRestartPreview() {
    try {
      const dirtyPages = pages.filter((page) => isDirty(page, drafts[page.path]));
      setMessage(dirtyPages.length ? `Saving ${dirtyPages.length} changed posts...` : 'No changes. Restarting preview...');
      for (const page of dirtyPages) {
        setBusyPath(page.path);
        await savePage(page);
      }
      setBusyPath('');
      await restartPreview();
    } catch (error) {
      setBusyPath('');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function normalizeOne(page: Page) {
    try {
      setBusyPath(page.path);
      setMessage(`Normalizing ${page.title}...`);
      const response = await fetch(`/api/content-normalize/${encodeURIComponent(page.path)}`, { method: 'POST' });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      const updated = result.page as Page;
      setPages((current) => current.map((item) => item.path === page.path ? updated : item));
      setDrafts((current) => ({ ...current, [updated.path]: draftFromPage(updated) }));
      setLastNormalizedPath(updated.path);
      setMessage(
        updated.normalized
          ? `Normalized ${updated.title}.`
          : `Normalize finished for ${updated.title}, still needs: ${updated.normalize_reasons.join(', ')}.`
      );
      await loadPages();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyPath('');
    }
  }

  async function normalizeSelected() {
    const targets = pages.filter((page) => selected.has(page.path));
    if (!targets.length) {
      setMessage('No selected posts.');
      return;
    }
    for (const page of targets) {
      await normalizeOne(page);
    }
    setSelected(new Set());
  }

  async function refactorPage(page: Page, targetPath: string, title?: string) {
    setBusyPath(page.path);
    const response = await fetch('/api/content-refactor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_path: page.path,
        target_path: targetPath,
        title,
        use_llm: false,
      }),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const result = await response.json();
    setPages((current) => current.filter((item) => item.path !== page.path));
    setSelected((current) => {
      const next = new Set(current);
      next.delete(page.path);
      return next;
    });
    setBusyPath('');
    setMessage(`Moved ${result.old_path} -> ${result.new_path}`);
  }

  async function moveToPending(page: Page) {
    try {
      const target = page.path.startsWith('pending/') ? page.path : `pending/${page.path}`;
      await refactorPage(page, target);
    } catch (error) {
      setBusyPath('');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function loadSuggestions(page: Page) {
    try {
      setBusyPath(page.path);
      setMessage(`Analyzing ${page.title}...`);
      const response = await fetch(`/api/content-suggestions/${encodeURIComponent(page.path)}`, { method: 'POST' });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = await response.json() as { suggestions: MoveSuggestion[] };
      setSuggestions((current) => ({ ...current, [page.path]: data.suggestions }));
      setMessage(`Got ${data.suggestions.length} suggestions for ${page.title}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyPath('');
    }
  }

  async function applySuggestion(page: Page, suggestion: MoveSuggestion) {
    try {
      await refactorPage(page, suggestion.target_path, suggestion.title);
    } catch (error) {
      setBusyPath('');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <main>
      <TopNav active="admin" />

      <section className="toolbar">
        <select value={scope} onChange={(event) => setScope(event.target.value as 'normal' | 'pending')}>
          <option value="normal">Normal content</option>
          <option value="pending">Pending content</option>
        </select>
        <select value={directory} onChange={(event) => setDirectory(event.target.value)}>
          <option value="all">All directories</option>
          {directories.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">All status</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
        </select>
        <select value={normalizeStatus} onChange={(event) => setNormalizeStatus(event.target.value)}>
          <option value="all">All normalize</option>
          <option value="normalized">Normalized</option>
          <option value="needs-work">Needs normalize</option>
        </select>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, path, tags" />
        <label className="check">
          <input type="checkbox" checked={previewDrafts} onChange={(event) => setPreviewDrafts(event.target.checked)} />
          Preview drafts
        </label>
        <button onClick={saveAllAndRestartPreview}>Save all & restart preview</button>
        <button disabled={!selected.size || scope !== 'normal'} onClick={() => void normalizeSelected()}>
          Normalize selected ({selected.size})
        </button>
      </section>

      {message && <div className="message">{message}</div>}

      <section className="tableWrap">
        <table>
          <thead>
            <tr>
              <th><input type="checkbox" checked={visiblePages.length > 0 && visiblePages.every((page) => selected.has(page.path))} onChange={(event) => setSelected(event.target.checked ? new Set(visiblePages.map((page) => page.path)) : new Set())} /></th>
              <th><button onClick={() => setSort('title')}>Title</button></th>
              <th><button onClick={() => setSort('directory')}>Directory</button></th>
              <th><button onClick={() => setSort('date')}>Date</button></th>
              <th><button onClick={() => setSort('modified')}>Modified</button></th>
              <th>Tags</th>
              <th>Normalized</th>
              <th>Draft</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {visiblePages.map((page) => {
              const draft = drafts[page.path] || draftFromPage(page);
              const dirty = isDirty(page, draft);
              return (
                <tr
                  key={page.path}
                  className={[
                    lastNormalizedPath === page.path ? 'recentlyUpdated' : '',
                    selected.has(page.path) ? 'selectedRow' : '',
                  ].filter(Boolean).join(' ')}
                >
                  <td><input type="checkbox" checked={selected.has(page.path)} onChange={(event) => toggleSelected(page.path, event.target.checked)} /></td>
                  <td>
                    <input value={draft.title} onChange={(event) => updateDraft(page.path, { title: event.target.value })} />
                    <div className="path">{page.path}</div>
                    {suggestions[page.path]?.length > 0 && (
                      <div className="suggestions">
                        {suggestions[page.path].map((item) => (
                          <button key={item.target_path} onClick={() => void applySuggestion(page, item)} title={item.reason}>
                            {item.target_path}
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>{page.directory || '-'}</td>
                  <td><input value={draft.date} onChange={(event) => updateDraft(page.path, { date: event.target.value })} /></td>
                  <td className="time">{page.modified}</td>
                  <td><textarea value={formatTags(draft.tags)} onChange={(event) => updateDraft(page.path, { tags: parseTags(event.target.value) })} /></td>
                  <td>
                    <span className={page.normalized ? 'badge ok' : 'badge warn'}>
                      {page.normalized ? 'Normalized' : 'Needs work'}
                    </span>
                    {!page.normalized && <div className="path">{page.normalize_reasons.join(', ')}</div>}
                  </td>
                  <td><input type="checkbox" checked={draft.draft} onChange={(event) => updateDraft(page.path, { draft: event.target.checked })} /></td>
                  <td>
                    <button disabled={busyPath === page.path} onClick={() => void saveAndMaybePreview(page)}>
                      {dirty ? 'Save & Preview' : 'Preview'}
                    </button>
                    {scope === 'normal' && (
                      <button
                        className={page.normalized ? 'normalizedButton' : ''}
                        disabled={busyPath === page.path || page.normalized}
                        onClick={() => void normalizeOne(page)}
                      >
                        {busyPath === page.path ? 'Normalizing...' : page.normalized ? 'Normalized' : 'Normalize'}
                      </button>
                    )}
                    {scope === 'normal' ? (
                      <button disabled={busyPath === page.path} onClick={() => void moveToPending(page)}>Pending</button>
                    ) : (
                      <button disabled={busyPath === page.path} onClick={() => void loadSuggestions(page)}>Suggest</button>
                    )}
                    <a className="inlineAction" href={editorPath(page.path)}>Edit</a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </main>
  );
}

function groupIssues(issues: ValidationIssue[]): [string, ValidationIssue[]][] {
  const groups = new Map<string, ValidationIssue[]>();
  for (const issue of issues) {
    const list = groups.get(issue.source_path) || [];
    list.push(issue);
    groups.set(issue.source_path, list);
  }
  return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'));
}

function IssueList({ issues, onLine }: { issues: ValidationIssue[]; onLine?: (line: number) => void }) {
  if (!issues.length) {
    return <div className="emptyDoc">没有内容错误。</div>;
  }
  return (
    <div className="issueList">
      {issues.map((issue, index) => (
        <div className="issueItem" key={`${issue.source_path}-${issue.line}-${issue.target}-${index}`}>
          <div className="issueHead">
            <button className="lineButton" onClick={() => onLine?.(issue.line)}>Line {issue.line}</button>
            <span className="badge warn">{issue.kind}</span>
          </div>
          <div className="issueMessage">{issue.message}</div>
          <div className="path">{issue.raw_reference} → {issue.target}</div>
          {issue.candidates.length > 0 && (
            <div className="candidateList">
              {issue.candidates.map((candidate) => <code key={candidate}>{candidate}</code>)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function IssuesView() {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [message, setMessage] = useState('');
  const [showWarnings, setShowWarnings] = useState(false);

  async function loadReport() {
    const response = await fetch('/api/validation');
    const data = await response.json() as ValidationReport;
    setReport(data);
  }

  async function revalidate() {
    setMessage('正在重新校验...');
    const response = await fetch('/api/validation/run', { method: 'POST' });
    const data = await response.json() as ValidationReport;
    setReport(data);
    setMessage(data.ok ? '校验通过。' : `发现 ${data.issues.length} 个问题。`);
  }

  useEffect(() => {
    void loadReport();
  }, []);

  const issues = report?.issues || [];
  const errors = issues.filter((issue) => issue.severity === 'error');
  const warnings = issues.filter((issue) => issue.severity !== 'error');
  const errorGroups = groupIssues(errors);
  const warningGroups = groupIssues(warnings);

  return (
    <main>
      <TopNav active="issues" />
      <section className="toolbar">
        <button onClick={() => void revalidate()}>Revalidate</button>
        {report && (
          <button
            className={report.ok ? 'statusButton ok' : 'statusButton warn'}
            onClick={() => setShowWarnings((current) => !current)}
            disabled={!warnings.length}
          >
            {report.ok ? `OK${warnings.length ? ` · ${warnings.length} warnings` : ''}` : `${errors.length} errors · ${warnings.length} warnings`}
          </button>
        )}
      </section>
      {message && <div className="message">{message}</div>}
      <section className="issuesShell">
        {errorGroups.length === 0 ? (
          <div className="emptyDoc">当前没有阻断 preview/build 的内容错误。</div>
        ) : errorGroups.map(([path, issues]) => (
          <article className="issueGroup" key={path}>
            <header>
              <div>
                <h2>{path}</h2>
                <p>{issues.length} 个问题</p>
              </div>
              <a className="buttonLink" href={editorPath(path)}>Edit Markdown</a>
            </header>
            <IssueList issues={issues} />
          </article>
        ))}
        {showWarnings && warningGroups.length > 0 && (
          <section className="warningDetails">
            <header>
              <div>
                <h2>Warnings</h2>
                <p>{warnings.length} 个 warning，不阻断 preview/build，但建议逐步清理。</p>
              </div>
              <button onClick={() => setShowWarnings(false)}>Hide warnings</button>
            </header>
            {warningGroups.map(([path, issues]) => (
              <article className="issueGroup warningGroup" key={path}>
                <header>
                  <div>
                    <h2>{path}</h2>
                    <p>{issues.length} 个 warning</p>
                  </div>
                  <a className="buttonLink" href={editorPath(path)}>Edit Markdown</a>
                </header>
                <IssueList issues={issues} />
              </article>
            ))}
          </section>
        )}
      </section>
    </main>
  );
}

function EditorView({ path }: { path: string }) {
  const [payload, setPayload] = useState<ContentPayload | null>(null);
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState<ContentPreview | null>(null);
  const [message, setMessage] = useState('');
  const editorRef = useRef<any>(null);

  async function loadContent() {
    setMessage('');
    const response = await fetch(`/api/content/${encodeURIComponent(path)}`);
    if (!response.ok) {
      setMessage(await response.text());
      return;
    }
    const data = await response.json() as ContentPayload;
    setPayload(data);
    setContent(data.content);
    await loadPreview(data.content);
  }

  async function loadPreview(nextContent: string) {
    const response = await fetch(`/api/content-preview/${encodeURIComponent(path)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: nextContent }),
    });
    if (response.ok) {
      setPreview(await response.json() as ContentPreview);
    }
  }

  async function saveContent() {
    setMessage('正在保存...');
    const response = await fetch(`/api/content/${encodeURIComponent(path)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      setMessage(await response.text());
      return;
    }
    const data = await response.json() as ContentPayload;
    setPayload(data);
    setMessage(data.validation.ok ? '已保存，校验通过。' : `已保存，仍有 ${data.issues.length} 个问题。`);
    await loadPreview(content);
  }

  function jumpToLine(line: number) {
    const editor = editorRef.current;
    if (!editor) return;
    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: 1 });
    editor.focus();
  }

  useEffect(() => {
    void loadContent();
  }, [path]);

  const fileIssues = payload?.issues || preview?.validation.issues || [];
  const canPreview = Boolean(payload?.page.preview_url && (preview?.validation.ok ?? payload?.validation.ok));

  return (
    <main>
      <TopNav active="editor" />
      <section className="editorToolbar">
        <div>
          <strong>{path}</strong>
          {preview && <span className={preview.validation.ok ? 'badge ok' : 'badge warn'}>{preview.validation.ok ? 'OK' : `${preview.validation.issues.length} issues`}</span>}
        </div>
        <div className="editorActions">
          <a className="buttonLink" href="/issues/">Issues</a>
          <button onClick={() => void saveContent()}>Save</button>
          <button
            disabled={!canPreview}
            onClick={() => payload && window.open(`${previewOrigin}${payload.page.preview_url}`, '_blank')}
          >
            Preview
          </button>
        </div>
      </section>
      {message && <div className="message">{message}</div>}
      <section className="editorShell">
        <div className="monacoPane">
          <Editor
            height="72vh"
            defaultLanguage="markdown"
            value={content}
            onMount={(editor) => { editorRef.current = editor; }}
            onChange={(value) => {
              const next = value || '';
              setContent(next);
            }}
            options={{
              minimap: { enabled: false },
              wordWrap: 'on',
              fontSize: 14,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
            }}
          />
        </div>
        <aside className="editorSide">
          <h2>错误</h2>
          <IssueList issues={fileIssues} onLine={jumpToLine} />
          <h2>转换预览</h2>
          <div className="markdownBody previewMarkdown" dangerouslySetInnerHTML={{ __html: renderMarkdown(preview?.content || '') }} />
        </aside>
      </section>
    </main>
  );
}

function DocsView() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [currentPath, setCurrentPath] = useState('');
  const [document, setDocument] = useState<DocContent | null>(null);
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(['source']));

  async function loadDocs() {
    const response = await fetch('/api/docs');
    const data = await response.json() as DocItem[];
    setDocs(data);
    const initial = currentPath || data[0]?.path || '';
    if (initial) {
      setCurrentPath(initial);
      await loadDocument(initial);
    }
  }

  async function loadDocument(path: string) {
    setMessage('');
    const response = await fetch(`/api/docs/${encodeURIComponent(path)}`);
    if (!response.ok) {
      setMessage(await response.text());
      return;
    }
    const data = await response.json() as DocContent;
    setDocument(data);
    setCurrentPath(data.path);
  }

  useEffect(() => {
    void loadDocs();
  }, []);

  const docTree = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const filtered = docs.filter((doc) => {
      if (!keyword) return true;
      return [doc.title, doc.path, doc.section, ...(doc.parts || [])].join(' ').toLowerCase().includes(keyword);
    });
    return buildDocTree(filtered);
  }, [docs, query]);

  function toggleNode(path: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  return (
    <main>
      <TopNav active="docs" />

      <section className="docsShell">
        <aside className="docsSidebar">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文档" />
          <div className="docsTree">
            <DocTree
              nodes={docTree}
              currentPath={currentPath}
              expanded={expanded}
              onToggle={toggleNode}
              onOpen={(path) => void loadDocument(path)}
            />
          </div>
        </aside>

        <article className="docArticle">
          {message && <div className="message">{message}</div>}
          {document ? (
            <div className="markdownBody" dangerouslySetInnerHTML={{ __html: renderMarkdown(document.content) }} />
          ) : (
            <div className="emptyDoc">未选择文档。</div>
          )}
        </article>

        <aside className="docToc">
          <div className="docTocTitle">本页目录</div>
          {document?.headings.map((heading) => (
            <a
              className={`tocLevel${Math.min(heading.level, 3)}`}
              href={`#${heading.id}`}
              key={heading.id}
            >
              {heading.title}
            </a>
          ))}
        </aside>
      </section>
    </main>
  );
}

export function App() {
  const pathname = window.location.pathname;
  if (pathname.startsWith('/docs')) return <DocsView />;
  if (pathname.startsWith('/issues')) return <IssuesView />;
  if (pathname.startsWith('/editor/')) {
    return <EditorView path={decodeURIComponent(pathname.replace(/^\/editor\/?/, ''))} />;
  }
  return <AdminView />;
}

#!/usr/bin/env python3
"""Assemble the ThousandEyes MCP Lab site.

Run from anywhere: `python3 src/build.py` (optionally with the guide HTML path as the first argument).
Ports the verified content of the lab guide (src/guide/*.html) into the SPA shell (src/shell.html),
remaps cross-references to hash routes, parses the tool catalogue into a directory, builds the
search index, hashes the checkpoint answers from api/checkpoints.json, and writes:
  site/index.html       the self-hosted page (full document, loads site/config.js)
  site/config.js        created only if missing; never overwritten (it holds your API URL)
  src/out/index.html    the Claude-artifact page (local-score mode, no config.js)
"""
import hashlib, json, pathlib, re, sys, unicodedata
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

SRC = pathlib.Path(__file__).resolve().parent
ROOT = SRC.parent
GUIDE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else SRC / 'guide' / 'thousandeyes-mcp-lab-ai-builders-v1.html'
BANK_PATH = ROOT / 'api' / 'checkpoints.json'
SITE_DIR = ROOT / 'site'
OUT = SRC / 'out'
SALT = 'te-lab-2026'

ROUTE = {'sec-00': 'setup', 'sec-01': 'setup', 'sec-02': 'labs', 'sec-03': 'build-0', 'sec-04': 'build-1',
         'sec-05': 'build-2', 'sec-06': 'build-3', 'sec-07': 'field-07', 'sec-08': 'field-08', 'sec-09': 'field-09', 'top': 'home'}


def canon(s: str) -> str:
    s = unicodedata.normalize('NFKC', s.lower())
    s = re.sub(r'[`"\'“”‘’]', '', s).strip()
    s = re.sub(r'[.!?]+$', '', s)
    return re.sub(r'[\s_-]+', '', s)


def h(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


# ── load and bucket the guide ─────────────────────────────────────────────
soup = BeautifulSoup(GUIDE.read_text(encoding='utf-8'), 'lxml')
container = soup.select_one('div.container')
sections, cur = {}, None
for child in list(container.children):
    if isinstance(child, Comment):
        continue
    if isinstance(child, NavigableString):
        continue
    if child.name == 'nav' and 'section-nav' in (child.get('class') or []):
        child.decompose(); continue
    if child.name == 'div' and 'section-break' in (child.get('class') or []):
        cur = child.get('id'); sections[cur] = [child]; continue
    if cur:
        sections[cur].append(child)
assert list(sections) == [f'sec-0{i}' for i in range(10)], list(sections)

# id -> route, for stray anchors
id_route = {}
for sec, nodes in sections.items():
    for n in nodes:
        for el in n.find_all(id=True):
            id_route[el['id']] = ROUTE[sec]
        if n.get('id'):
            id_route[n['id']] = ROUTE[sec]

unmapped = []


def clean(nodes):
    """Strip polish artefacts, remap links, wrap tables. Mutates in place."""
    for n in nodes:
        for a in n.select('a.anchor'):
            a.decompose()
        for t in n.select('.toc'):
            t.decompose()
        for a in n.find_all('a', href=True):
            href = a['href']
            if not href.startswith('#'):
                continue
            t = href[1:]
            if t in ROUTE:
                a['href'] = '#' + ROUTE[t]
            elif re.fullmatch(r'lab-[1-6]', t):
                pass
            elif t in id_route:
                a['href'] = '#' + id_route[t]
            else:
                unmapped.append(t)
        for tb in n.select('table.comp-table'):
            if tb.parent and tb.parent.get('class') and 'table-wrap' in tb.parent.get('class'):
                continue
            wrap = soup.new_tag('div'); wrap['class'] = 'table-wrap'
            tb.wrap(wrap)
        for el in n.find_all(True):
            if el.has_attr('style') and el.get('id') == 'sec-00':
                del el['style']
    return nodes


for nodes in sections.values():
    clean(nodes)


def html_of(nodes) -> str:
    return '\n'.join(('<div class="table-wrap">' + str(n) + '</div>') if n.name == 'table' else str(n) for n in nodes)


def inner(tag: Tag) -> str:
    return ''.join(str(c) for c in tag.contents)


# ── section 00 pieces ─────────────────────────────────────────────────────
s0 = sections['sec-00'][1:]
outcomes = next(n for n in s0 if 'outcome-grid' in (n.get('class') or []))
cards = [n for n in s0 if n.name == 'div' and 'card' in (n.get('class') or [])]
proctor_card, how_card = cards[0], cards[1]
assert 'proctor' in proctor_card.get_text().lower() and 'MCP server works' in how_card.get_text()
h2s = [n for n in s0 if n.name == 'h2']
timing_h2 = next(n for n in h2s if n.get('id', '').startswith('timing'))
reqs_h2 = next(n for n in h2s if n.get('id') == 'what-you-need')
cat_h2 = next(n for n in h2s if n.get('id') == 'tool-catalogue')
i = s0.index(timing_h2); timing_nodes = [timing_h2, s0[i + 1], s0[i + 2]]
i = s0.index(reqs_h2); reqs_nodes = [reqs_h2, s0[i + 1]]
i = s0.index(cat_h2); cat_table = s0[i + 2]; tool_tip = s0[i + 3]
assert cat_table.name == 'table' and 'tip-box' in (tool_tip.get('class') or [])

# tool directory from the catalogue table
TOOLS = []
for tr in cat_table.select('tbody tr'):
    tds = tr.find_all('td')
    group = tds[0].get_text(' ', strip=True)
    pending, last = [], None
    for el in tds[1].children:
        if isinstance(el, Tag) and el.name == 'code':
            last = {'n': el.get_text(strip=True), 'g': group, 'k': None, 'd': ''}
            pending.append(last)
        elif isinstance(el, Tag) and 'rw' in (el.get('class') or []):
            kind = 'r' if 'rw-r' in el['class'] else 'w' if 'rw-w' in el['class'] else 'u'
            for p in pending:
                p['k'] = kind
            TOOLS.extend(pending); pending = []
        elif isinstance(el, NavigableString):
            m = re.search(r'\(([^)]+)\)', str(el))
            if m and last is not None:
                last['d'] = m.group(1).strip()
assert len(TOOLS) == 54 and all(t['k'] for t in TOOLS), (len(TOOLS), [t for t in TOOLS if not t['k']])
tool_counts = {k: sum(1 for t in TOOLS if t['k'] == k) for k in 'rwu'}

# ── section 01: setup body ────────────────────────────────────────────────
setup_body = sections['sec-01'][1:]

# ── section 02: labs intro + lab pages ────────────────────────────────────
s2 = sections['sec-02'][1:]
labs_intro = [n for n in s2 if 'info-box' in (n.get('class') or [])]
usecases = [n for n in s2 if 'usecase' in (n.get('class') or [])]
assert len(usecases) == 6


def tag_text(uc):
    t = uc.select_one('.usecase-tag').get_text(' ', strip=True)
    return re.sub(r'^[★\s]+', '', t)


LAB_META = []
lab_pages = []
for uc in usecases:
    n = int(uc.select_one('.usecase-num').get_text(strip=True))
    title = inner(uc.select_one('.usecase-title')).strip()
    sub = inner(uc.select_one('.usecase-sub')).strip()
    tag = tag_text(uc)
    body = inner(uc.select_one('.usecase-body'))
    prev_href, prev_small, prev_label = ('#setup', 'Back · Setup', 'Choose your poison') if n == 1 else (f'#lab-{n-1}', f'Back · Lab {n-1}', LAB_META[-1]['plain'])
    if n < 6:
        nxt = usecases[n]
        next_href, next_small, next_label = f'#lab-{n+1}', f'Next · Lab {n+1}', nxt.select_one('.usecase-title').get_text(' ', strip=True)
    else:
        next_href, next_small, next_label = '#build-0', 'Next · 03', 'Connect Claude Code'
    LAB_META.append({'n': n, 'plain': uc.select_one('.usecase-title').get_text(' ', strip=True)})
    lab_pages.append(f'''
  <!-- ═══ LAB {n} ═══ -->
  <section class="view" id="view-lab-{n}" data-group="labs" hidden>
    <div class="wrap page">
      <div class="page-head">
        <span class="spine" aria-hidden="true"></span>
        <p class="eyebrow">// 02 · Lab {n} of 6 · {tag} · 100 pts</p>
        <h1><span class="hl">Lab {n}.</span> {title}</h1>
        <p class="desc">{sub}</p>
      </div>
      <div class="content">
{body}
        <div class="cp" data-cp="cp{n}"></div>
        <div class="pager"><a href="{prev_href}"><small>{prev_small}</small>{prev_label}</a><a class="next" href="{next_href}"><small>{next_small}</small>{next_label} →</a></div>
      </div>
    </div>
  </section>''')

# ── sections 03 to 06: build pages ────────────────────────────────────────
BUILD_ROUTES = [('sec-03', 'build-0', None), ('sec-04', 'build-1', 'cp7'), ('sec-05', 'build-2', 'cp8'), ('sec-06', 'build-3', 'cp9')]
build_pages = []
build_titles = {}
for sec, route, cp in BUILD_ROUTES:
    brk = sections[sec][0]
    build_titles[route] = brk.select_one('.section-title').get_text(' ', strip=True)
for idx, (sec, route, cp) in enumerate(BUILD_ROUTES):
    nodes = sections[sec]
    brk, body_nodes = nodes[0], nodes[1:]
    number = brk.select_one('.section-number').get_text(' ', strip=True).lstrip('/ ').strip()
    title_tag = brk.select_one('.section-title')
    for sp in title_tag.find_all('span'):
        sp['class'] = ['hl']
    title = inner(title_tag).strip()
    desc = inner(brk.select_one('.section-desc')).strip()
    has_os = any(n.select_one('.os-tabs') or ('os-tabs' in (n.get('class') or [])) for n in body_nodes)
    os_switch = '<div class="meta-row"><div data-os-switch></div></div>' if has_os else ''
    pts = f' · 100 pts' if cp else ''
    if idx == 0:
        prev = '<a href="#lab-6"><small>Back · Lab 6</small>Ship the alerting, then clean up</a>'
    else:
        pr = BUILD_ROUTES[idx - 1][1]
        prev = f'<a href="#{pr}"><small>Back</small>{build_titles[pr]}</a>'
    if idx < len(BUILD_ROUTES) - 1:
        nr = BUILD_ROUTES[idx + 1][1]
        nxt = f'<a class="next" href="#{nr}"><small>Next</small>{build_titles[nr]} →</a>'
    else:
        nxt = '<a class="next" href="#field"><small>Next</small>Field guide: beyond MCP, guardrails, capstone →</a>'
    cp_html = f'\n        <div class="cp" data-cp="{cp}"></div>' if cp else ''
    build_pages.append(f'''
  <!-- ═══ {route.upper()} ═══ -->
  <section class="view" id="view-{route}" data-group="builds" hidden>
    <div class="wrap page">
      <div class="page-head">
        <span class="spine" aria-hidden="true"></span>
        <p class="eyebrow">// {number}{pts}</p>
        <h1>{title}</h1>
        <p class="desc">{desc}</p>
        {os_switch}
      </div>
      <div class="content">
{html_of(body_nodes)}{cp_html}
        <div class="pager">{prev}{nxt}</div>
      </div>
    </div>
  </section>''')

# ── sections 07 to 09: field guide ────────────────────────────────────────
field_nodes = sections['sec-07'] + sections['sec-08'] + sections['sec-09']
for sec in ('sec-07', 'sec-08', 'sec-09'):
    brk = sections[sec][0]
    for sp in brk.select('.section-title span'):
        sp['class'] = ['hl']

# ── search index ──────────────────────────────────────────────────────────
HEAD_CLASSES = ('step-title', 'usecase-title', 'o-title', 'client-panel-title', 'section-title', 'req-label')
TEXT_CLASSES = ('prompt-block', 'step-desc', 'req-val', 'client-sub', 'client-panel-meta', 'section-desc')
SEARCH = []


def index(route, page_title, nodes):
    cur = {'r': route, 't': page_title, 'x': ''}
    seen = set()

    def flush():
        nonlocal cur
        if cur['x'].strip():
            SEARCH.append({'r': cur['r'], 't': cur['t'][:120], 'x': cur['x'][:600]})

    for node in nodes:
        for el in node.descendants:
            if not isinstance(el, Tag):
                continue
            cls = el.get('class') or []
            if el.name in ('h2', 'h3', 'h4') or any(c in cls for c in HEAD_CLASSES):
                flush(); cur = {'r': route, 't': el.get_text(' ', strip=True), 'x': ''}
            elif el.name in ('p', 'pre', 'td') or any(c in cls for c in TEXT_CLASSES) or (el.name == 'li' and not el.find('div')):
                t = el.get_text(' ', strip=True)
                if t and t not in seen and len(cur['x']) < 600:
                    seen.add(t); cur['x'] += (' ' if cur['x'] else '') + t
    flush()


index('setup', 'Choose your poison: connect your AI client', [how_card, proctor_card] + setup_body + [tool_tip])
index('setup', 'Tool directory', [cat_table])
index('home', 'What you’ll walk out with', [outcomes] + timing_nodes + reqs_nodes)
index('labs', 'Labs in your client', labs_intro)
for uc, meta in zip(usecases, LAB_META):
    index(f'lab-{meta["n"]}', f'Lab {meta["n"]}: {meta["plain"]}', [uc.select_one('.usecase-body')])
for sec, route, cp in BUILD_ROUTES:
    index(route, build_titles[route], sections[sec][1:])
for sec, route in (('sec-07', 'field-07'), ('sec-08', 'field-08'), ('sec-09', 'field-09')):
    index(route, sections[sec][0].select_one('.section-title').get_text(' ', strip=True), sections[sec])

# ── checkpoint bank ───────────────────────────────────────────────────────
bank = json.loads(BANK_PATH.read_text(encoding='utf-8'))
public = {'rules': bank['rules'], 'checkpoints': []}
for cp in bank['checkpoints']:
    pub = {k: v for k, v in cp.items() if k != 'answers'}
    pub['hashes'] = sorted({h(canon(a) + '|' + SALT) for a in cp['answers']})
    public['checkpoints'].append(pub)
assert sum(c['points'] for c in bank['checkpoints']) == bank['rules']['total']


# ── assemble ──────────────────────────────────────────────────────────────
shell = (SRC / 'shell.html').read_text(encoding='utf-8')


def put(name, html):
    global shell
    assert f'<!--@{name}@-->' in shell, name
    shell = shell.replace(f'<!--@{name}@-->', html)


put('OUTCOMES', str(outcomes))
put('TIMING', html_of(timing_nodes))
put('REQS', html_of(reqs_nodes))
put('PROCTORS', str(proctor_card))
put('HOW_IT_WORKS', str(how_card))
put('SETUP_BODY', html_of(setup_body))
put('TOOL_TIP', str(tool_tip))
put('LABS_INTRO', html_of(labs_intro))
put('LAB_PAGES', '\n'.join(lab_pages))
put('BUILD_PAGES', '\n'.join(build_pages))
put('FIELD_BODY', html_of(field_nodes))


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


shell = shell.replace('/*@BANK@*/null', js(public), 1)
shell = shell.replace('/*@TOOLS@*/[]', js(TOOLS), 1)
shell = shell.replace('/*@SEARCH@*/[]', js(SEARCH), 1)
assert re.findall(r'<!--@(\w+)@-->', shell) == ['CONFIG_SCRIPT'] and '/*@' not in shell, re.findall(r'<!--@(\w+)@-->', shell)

artifact_page = shell.replace('<!--@CONFIG_SCRIPT@-->', '')
dist_page = shell.replace('<!--@CONFIG_SCRIPT@-->', '<script src="config.js"></script>')

# dist: a full document, head split out
m = re.match(r'(?s)^(.*?</style>)\s*(.*)$', dist_page)
head_part, body_part = m.group(1), m.group(2)
dist_doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}img{max-width:100%}[hidden]{display:none!important}</style>\n'
            + head_part + '\n</head>\n<body>\n' + body_part + '\n</body>\n</html>\n')

config_js = '''// ThousandEyes MCP Lab: site configuration for the self-hosted copy.
// apiBase: the ApiUrl output printed by `sam deploy` (no trailing slash). Leave "" to run in local-score mode.
window.TE_LAB_CONFIG = {
  apiBase: "",
  event: { name: "AI Builders", date: "", city: "" }
};
'''

for page in (artifact_page, dist_doc):
    assert '—' not in page, 'em dash found'

OUT.mkdir(exist_ok=True)
SITE_DIR.mkdir(exist_ok=True)
(OUT / 'index.html').write_text(artifact_page, encoding='utf-8')
(SITE_DIR / 'index.html').write_text(dist_doc, encoding='utf-8')
if not (SITE_DIR / 'config.js').exists():
    (SITE_DIR / 'config.js').write_text(config_js, encoding='utf-8')

ids = re.findall(r'\sid="([^"]+)"', artifact_page)
dupes = sorted({i for i in ids if ids.count(i) > 1})
print(f'site/index.html {len(dist_doc)//1024} KB | src/out/index.html {len(artifact_page)//1024} KB | tools {len(TOOLS)} {tool_counts} | search entries {len(SEARCH)} | checkpoints {len(public["checkpoints"])}')
print('unmapped anchors:', sorted(set(unmapped)) or 'none', '| duplicate ids:', dupes or 'none')

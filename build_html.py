"""
build_html.py — 把 Markdown 講義轉成排版精美、單一檔案的教學文章 HTML

特色：
- 圖只有一份來源：images/*.svg，直接內嵌進 HTML（產出是自包含單檔）。
- 程式碼區塊：建置期做語法高亮（純 Python，無外部函式庫，離線可用），右上角有複製鈕。
- 深/淺色：跟隨系統設定 (prefers-color-scheme)。

用法：
    python build_html.py                產生 STUDENT_GUIDE.html（預設）
    python build_html.py 其他檔案.md    產生 其他檔案.html（同一套樣式與功能）
"""

import os
import re
import sys
import html

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "images")


# =============================================================================
# 語法高亮（build 時做，輸出成 <span class="tok-*">，不需執行期函式庫）
# =============================================================================
def esc(s):
    return html.escape(s)


PY_KW = {"def", "return", "import", "from", "for", "if", "elif", "else", "while",
         "in", "not", "and", "or", "with", "as", "try", "except", "finally",
         "class", "lambda", "pass", "break", "continue", "yield", "global",
         "nonlocal", "raise", "assert", "del", "is", "async", "await"}
PY_CONST = {"True", "False", "None"}
PY_BUILTIN = {"print", "len", "range", "dict", "set", "str", "int", "list", "float",
              "bool", "tuple", "enumerate", "zip", "map", "filter", "sorted", "max",
              "min", "sum", "open", "isinstance", "super", "getattr", "setattr",
              "hasattr", "type", "id", "abs", "round", "any", "all", "repr"}

PY_RE = re.compile(
    r"(?P<com>\#[^\n]*)"
    r"|(?P<str>'''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\")"
    r"|(?P<dec>@[A-Za-z_][\w.]*)"
    r"|(?P<num>\b\d+\.?\d*\b)"
    r"|(?P<id>[A-Za-z_]\w*)",
    re.S,
)


def hl_python(code):
    out, pos, prev = [], 0, None
    for m in PY_RE.finditer(code):
        if m.start() > pos:
            out.append(esc(code[pos:m.start()]))
        kind, text = m.lastgroup, m.group()
        if kind == "id":
            if prev in ("def", "class"):
                cls = "tok-fn"
            elif text in PY_KW:
                cls = "tok-kw"
            elif text in PY_CONST:
                cls = "tok-const"
            elif text in PY_BUILTIN:
                cls = "tok-bi"
            else:
                cls = None
            out.append(f'<span class="{cls}">{esc(text)}</span>' if cls else esc(text))
            prev = text
        else:
            cmap = {"com": "tok-com", "str": "tok-str", "dec": "tok-dec", "num": "tok-num"}
            out.append(f'<span class="{cmap[kind]}">{esc(text)}</span>')
            prev = None
        pos = m.end()
    if pos < len(code):
        out.append(esc(code[pos:]))
    return "".join(out)


BASH_CMD = {"pip", "python", "python3", "ollama", "adk", "export", "cd", "ls",
            "curl", "cat", "source", "bash", "sh", "mkdir", "rm", "echo", "git"}
BASH_RE = re.compile(
    r"(?P<com>\#[^\n]*)"
    r"|(?P<str>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
    r"|(?P<flag>(?<=\s)--?[A-Za-z][\w-]*)"
    r"|(?P<var>\$\{?[A-Za-z_]\w*\}?)"
    r"|(?P<id>[A-Za-z_][\w./:-]*)"
)


def hl_bash(code):
    out, pos = [], 0
    for m in BASH_RE.finditer(code):
        if m.start() > pos:
            out.append(esc(code[pos:m.start()]))
        kind, text = m.lastgroup, m.group()
        if kind == "id":
            cls = "tok-cmd" if text in BASH_CMD else None
            out.append(f'<span class="{cls}">{esc(text)}</span>' if cls else esc(text))
        else:
            cmap = {"com": "tok-com", "str": "tok-str", "flag": "tok-flag", "var": "tok-var"}
            out.append(f'<span class="{cmap[kind]}">{esc(text)}</span>')
        pos = m.end()
    if pos < len(code):
        out.append(esc(code[pos:]))
    return "".join(out)


JSON_RE = re.compile(
    r"(?P<key>\"(?:\\.|[^\"\\])*\")(?=\s*:)"
    r"|(?P<str>\"(?:\\.|[^\"\\])*\")"
    r"|(?P<num>-?\b\d+\.?\d*\b)"
    r"|(?P<const>\b(?:true|false|null)\b)"
)


def hl_json(code):
    out, pos = [], 0
    for m in JSON_RE.finditer(code):
        if m.start() > pos:
            out.append(esc(code[pos:m.start()]))
        cmap = {"key": "tok-key", "str": "tok-str", "num": "tok-num", "const": "tok-const"}
        out.append(f'<span class="{cmap[m.lastgroup]}">{esc(m.group())}</span>')
        pos = m.end()
    if pos < len(code):
        out.append(esc(code[pos:]))
    return "".join(out)


def highlight(code, lang):
    lang = (lang or "").lower()
    if lang == "python":
        return hl_python(code)
    if lang in ("bash", "sh", "shell"):
        return hl_bash(code)
    if lang == "json":
        return hl_json(code)
    return esc(code)


def mac_shell(code):
    out = []
    for line in code.split('\n'):
        line = line.replace(r'.venv\Scripts\activate', 'source .venv/bin/activate')
        line = re.sub(r'^(\s*)pip(\s+)', r'\1python3 -m pip\2', line)
        line = re.sub(r'^(\s*)python(\s+)', r'\1python3\2', line)
        out.append(line)
    return '\n'.join(out)


def should_make_os_tabs(lang, label, code):
    if lang.lower() not in ("bash", "sh", "shell"):
        return False
    if "預期輸出" in label or "不用" in label:
        return False
    return any(re.match(r'\s*(python|pip)\b', line) or r'.venv\Scripts\activate' in line
               for line in code.split('\n'))


def render_codeblock(lang, label, code, readonly):
    btn = ('' if readonly else
           '<button class="copy-btn" type="button" aria-label="複製程式碼">複製</button>')
    head = (f'<div class="codehead"><span class="codehead-label">{html.escape(label)}</span>'
            f'{btn}</div>') if (label or btn) else ''
    if should_make_os_tabs(lang, label, code):
        mac = highlight(mac_shell(code), lang)
        win = highlight(code, lang)
        return ('<div class="codeblock has-os">' + head +
                '<div class="os-variant" data-os="mac"><pre class="code"><code>' + mac +
                '</code></pre></div><div class="os-variant" data-os="windows"><pre class="code"><code>' +
                win + '</code></pre></div></div>')
    code_html = highlight(code, lang)
    return ('<div class="codeblock">' + head +
            '<pre class="code"><code>' + code_html + '</code></pre></div>')


# =============================================================================
# 樣式（含深/淺色模式與 token 顏色）
# =============================================================================
CSS = """
:root{
  --page:#fff;--ink:#202124;--muted:#5f6368;--border:#dadce0;
  --blue:#4285f4;--link:#1a73e8;
  --icode-bg:#f1f3f4;--icode:#c5221f;--th:#f1f3f4;
  --callout-info:#e8f0fe;--callout-warn:#fef7e0;
}
@media (prefers-color-scheme:dark){
  :root{
    --page:#0e1116;--ink:#e6e6e6;--muted:#9aa0a6;--border:#2a2f37;
    --link:#8ab4f8;
    --icode-bg:#20262e;--icode:#f28b82;--th:#20262e;
    --callout-info:#152232;--callout-warn:#2c2718;
  }
}
*{box-sizing:border-box}
body{max-width:820px;margin:0 auto;padding:0 20px 90px;background:var(--page);color:var(--ink);
  font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',system-ui,-apple-system,sans-serif;
  line-height:1.85;font-size:16.5px;-webkit-font-smoothing:antialiased}
.gbar{height:6px;border-radius:0 0 3px 3px;margin:0 0 30px;
  background:linear-gradient(90deg,#4285F4 0 25%,#EA4335 0 50%,#FBBC04 0 75%,#34A853 0 100%)}
h1{font-size:30px;line-height:1.35;border-bottom:3px solid var(--blue);padding-bottom:.35em;margin:0 0 .3em}
h2{font-size:23px;margin:2.1em 0 .6em;color:var(--link);border-left:5px solid var(--blue);padding-left:.55em;line-height:1.4}
h3{font-size:18px;margin:1.7em 0 .5em}
p{margin:1em 0}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
strong{font-weight:700}
code{background:var(--icode-bg);border-radius:4px;padding:.12em .42em;font-size:.88em;color:var(--icode);
  font-family:'SF Mono',Consolas,'Roboto Mono',monospace}
code[data-tip]{cursor:help;border-bottom:1px dashed var(--muted);position:relative}
code[data-tip]:hover::after{content:attr(data-tip);position:absolute;left:50%;bottom:calc(100% + 9px);
  transform:translateX(-50%);background:var(--ink);color:var(--page);padding:7px 11px;border-radius:7px;
  font-size:13px;font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',system-ui,sans-serif;
  font-weight:400;white-space:normal;width:max-content;max-width:260px;line-height:1.5;
  box-shadow:0 4px 16px rgba(0,0,0,.28);z-index:20}
code[data-tip]:hover::before{content:"";position:absolute;left:50%;bottom:calc(100% + 3px);
  transform:translateX(-50%);border:6px solid transparent;border-top-color:var(--ink);z-index:20}
.codeblock{margin:1.1em 0}
.codehead{display:flex;justify-content:space-between;align-items:center;gap:12px;
  background:#171b24;border-radius:10px 10px 0 0;padding:7px 14px;border-bottom:1px solid #2a3040}
.codehead-label{font-family:'SF Mono',Consolas,'Roboto Mono',monospace;font-size:12px;color:#9aa3b2}
pre.code{background:#1f2430;color:#abb2bf;border-radius:0 0 10px 10px;padding:16px 18px;overflow-x:auto;line-height:1.6;margin:0}
pre.code code{background:none;color:inherit;padding:0;font-size:13.5px}
.tok-kw{color:#c678dd}
.tok-const{color:#d19a66}
.tok-str{color:#98c379}
.tok-com{color:#7f848e;font-style:italic}
.tok-num{color:#d19a66}
.tok-bi{color:#56b6c2}
.tok-fn{color:#61afef}
.tok-dec{color:#e5c07b}
.tok-key{color:#61afef}
.tok-cmd{color:#61afef}
.tok-flag{color:#d19a66}
.tok-var{color:#56b6c2}
.copy-btn{font-family:inherit;font-size:12px;line-height:1;color:#cfd3dc;background:#2f3646;
  border:1px solid #3d4557;border-radius:6px;padding:5px 11px;cursor:pointer;
  transition:background .15s,color .15s,border-color .15s}
.copy-btn:hover{background:#3a4152;color:#fff}
.copy-btn.copied{color:#34a853;border-color:#34a853;background:#22331f}
.os-switch{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 28px;
  padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--th)}
.os-switch-label{font-size:13px;color:var(--muted);font-weight:600}
.os-switch-options{display:flex;gap:6px;flex-wrap:wrap}
.os-btn{font-family:inherit;font-size:13px;line-height:1;border:1px solid var(--border);
  border-radius:6px;background:var(--page);color:var(--ink);padding:8px 12px;cursor:pointer}
.os-btn.active{background:var(--blue);border-color:var(--blue);color:white}
.os-variant{display:none}
body[data-os="mac"] .os-variant[data-os="mac"],
body[data-os="windows"] .os-variant[data-os="windows"]{display:block}
.codeblock.has-os .codehead-label::after{content:" · macOS";color:#cfd3dc}
body[data-os="windows"] .codeblock.has-os .codehead-label::after{content:" · Windows"}
@media (max-width:560px){.os-switch{align-items:flex-start;flex-direction:column}.os-btn{min-height:44px}}
figure{margin:1.9em 0;text-align:center}
figure svg{width:100%;height:auto;max-width:760px}
figure img{width:100%;height:auto;max-width:760px;border-radius:8px;border:1px solid var(--border)}
figcaption{font-size:.88em;color:var(--muted);margin-top:.65em;line-height:1.6}
table{border-collapse:collapse;width:100%;margin:1.3em 0;font-size:.95em}
th,td{border:1px solid var(--border);padding:9px 13px;text-align:left;vertical-align:top}
th{background:var(--th);font-weight:600}
hr{border:none;border-top:1px solid var(--border);margin:2.6em 0}
ul,ol{padding-left:1.6em}
li{margin:.4em 0}
ul.task-list{list-style:none;padding-left:0}
.task-item{margin:.6em 0}
.task-item label{display:flex;align-items:flex-start;gap:10px;cursor:pointer}
.task-item input[type="checkbox"]{flex:none;width:18px;height:18px;margin-top:.25em;
  accent-color:var(--blue);cursor:pointer}
.task-item input[type="checkbox"]:checked ~ span{color:var(--muted);text-decoration:line-through}
.callout{border-radius:8px;padding:12px 16px;margin:1.2em 0}
.callout p{margin:0}
.callout.info{background:var(--callout-info);border-left:4px solid var(--blue)}
.callout.warn{background:var(--callout-warn);border-left:4px solid #fbbc04}
.logo-light,.logo-dark{display:inline-block;max-width:100%;height:auto;vertical-align:middle}
.logo-dark{display:none}
@media (prefers-color-scheme:dark){
  figure svg rect[fill="white"]{fill:#161b22}
  figure svg rect[fill="#f8f9fa"]{fill:#1b2129}
  figure svg rect[stroke="#dadce0"]{stroke:#2a2f37}
  figure svg rect[fill="#e8f0fe"]{fill:#17263b}
  figure svg rect[fill="#e6f4ea"]{fill:#16281c}
  figure svg rect[fill="#fef7e0"]{fill:#2a2413}
  figure svg text[fill="#202124"]{fill:#e6e6e6}
  figure svg g[fill="#202124"]{fill:#e6e6e6}
  figure svg text[fill="#5f6368"]{fill:#9aa0a6}
  figure svg text[fill="#1967d2"]{fill:#8ab4f8}
  figure svg text[fill="#188038"]{fill:#81c995}
  figure svg text[fill="#b06000"]{fill:#fdd663}
  figure svg text[fill="#ea4335"]{fill:#f28b82}
  .logo-light{display:none}
  .logo-dark{display:inline-block}
}
"""

COPY_JS = """
<script>
(function(){
  var root = document.body;
  var buttons = document.querySelectorAll('.os-btn');
  function preferredOS(){
    var saved = localStorage.getItem('guide-os');
    if(saved === 'mac' || saved === 'windows') return saved;
    var platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '';
    return /win/i.test(platform) ? 'windows' : 'mac';
  }
  function setOS(os){
    root.setAttribute('data-os', os);
    localStorage.setItem('guide-os', os);
    buttons.forEach(function(btn){
      var active = btn.getAttribute('data-os') === os;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }
  setOS(preferredOS());
  buttons.forEach(function(btn){
    btn.addEventListener('click', function(){ setOS(btn.getAttribute('data-os')); });
  });
  function legacyCopy(text){
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }
  function copyText(text){
    if(navigator.clipboard && navigator.clipboard.writeText){
      return navigator.clipboard.writeText(text).catch(function(){ return legacyCopy(text); });
    }
    return legacyCopy(text);
  }
  document.querySelectorAll('.copy-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      var block = btn.closest('.codeblock');
      var os = root.getAttribute('data-os') || 'mac';
      var code = block.querySelector('.os-variant[data-os="' + os + '"] code') || block.querySelector('code');
      copyText(code.textContent).then(function(){
        btn.textContent = '已複製'; btn.classList.add('copied');
        setTimeout(function(){ btn.textContent = '複製'; btn.classList.remove('copied'); }, 1500);
      }).catch(function(){
        btn.textContent = '請手動選取';
        setTimeout(function(){ btn.textContent = '複製'; }, 1800);
      });
    });
  });

  // 打勾狀態存在 localStorage，同一台裝置關掉分頁、隔天再回來還記得勾到哪。
  var page = location.pathname.split('/').pop() || 'index';
  document.querySelectorAll('.task-item input[type="checkbox"]').forEach(function(cb, idx){
    var span = cb.nextElementSibling;
    var key = 'gdg-task:' + page + ':' + (span ? span.textContent.trim() : idx);
    var saved = localStorage.getItem(key);
    if(saved === '1') cb.checked = true;
    else if(saved === '0') cb.checked = false;
    cb.addEventListener('change', function(){
      localStorage.setItem(key, cb.checked ? '1' : '0');
    });
  });
})();
</script>
"""


# =============================================================================
# 行內語法
# =============================================================================
def _code_tip(m):
    code, tip = m.group(1), m.group(2)
    return f'<code data-tip="{tip.replace(chr(34), "&quot;")}">{code}</code>'


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'`([^`]+)`\{([^}]+)\}', _code_tip, t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', t)
    return t


def embed_image(alt, path):
    fname = os.path.basename(path)
    fpath = os.path.join(IMG_DIR, fname)
    if path.endswith(".svg") and os.path.exists(fpath):
        with open(fpath, encoding="utf-8") as f:
            svg = re.sub(r'<\?xml.*?\?>', '', f.read(), flags=re.S).strip()
        return svg
    return f'<img src="{html.escape(path)}" alt="{html.escape(alt)}"/>'


def inline_svg_imgs(block):
    def repl(m):
        src, attrs = m.group(1), m.group(2)
        fpath = os.path.join(IMG_DIR, os.path.basename(src))
        if not (src.endswith(".svg") and os.path.exists(fpath)):
            return m.group(0)
        with open(fpath, encoding="utf-8") as f:
            svgtext = f.read()
        cm = re.search(r'class="([^"]+)"', attrs)
        wm = re.search(r'width="(\d+)"', attrs)
        cls = f' class="{cm.group(1)}"' if cm else ""
        # 若 SVG 只是包了一張點陣圖 → 直接輸出 data-URI <img>（可正確縮放，仍是單一檔案）
        im = re.search(r'(?:xlink:href|href)="(data:image/(?:png|jpe?g);base64,[^"]+)"', svgtext)
        if im:
            wattr = f' width="{wm.group(1)}"' if wm else ""
            return f'<img{cls}{wattr} src="{im.group(1)}" alt="Google Developer Groups On Campus">'
        # 否則內嵌向量 SVG
        svg = re.sub(r'<\?xml.*?\?>', '', svgtext, flags=re.S).strip()
        w = wm.group(1) + "px" if wm else "100%"
        return f'<span{cls} style="display:inline-block;width:{w};max-width:100%">{svg}</span>'
    return re.sub(r'<img\s+src="([^"]+)"([^>]*?)/?>', repl, block)


def is_separator(row):
    return bool(re.match(r'^\|[\s:|-]+\|?\s*$', row)) and set(row) <= set('|:- ')


def cells(row):
    return [c.strip() for c in row.strip().strip('|').split('|')]


def convert(md):
    lines = md.split('\n')
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]

        # OS 專屬段落：::: mac ... ::: 或 ::: windows ... :::
        # 內容照一般 Markdown 處理（可以有粗體、清單、連結…），外面包一層 os-variant，
        # 跟程式碼區塊共用同一顆頁面頂端的 macOS/Windows 切換鈕，不用另外寫兩段文字堆在一起。
        m = re.match(r'^:::\s*(mac|windows)\s*$', line)
        if m:
            os_tag = m.group(1)
            i += 1
            inner = []
            while i < n and lines[i].strip() != ':::':
                inner.append(lines[i]); i += 1
            i += 1  # 跳過結尾的 :::
            inner_html = convert('\n'.join(inner))
            out.append(f'<div class="os-variant" data-os="{os_tag}">{inner_html}</div>')
            continue

        # 程式碼區塊（含語法高亮 + 檔頭標籤 + 複製鈕）
        # fence 格式：```lang 目標標籤（GitHub 只取第一個字做高亮，其餘忽略，相容安全）
        if line.startswith('```'):
            info = line[3:].strip()
            parts = info.split(None, 1)
            lang = parts[0] if parts else ""
            label = parts[1] if len(parts) > 1 else ""
            if not label and lang and not re.match(r'^[A-Za-z0-9_+-]+$', lang):
                label, lang = lang, ""          # ``` 預期輸出 這種：整串是標籤、沒語言
            if not label:
                label = {"bash": "終端機", "sh": "終端機"}.get(lang.lower(), "")
            i += 1
            buf = []
            while i < n and not lines[i].startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            code = '\n'.join(buf)
            readonly = ("預期輸出" in label) or ("不用" in label)
            out.append(render_codeblock(lang, label, code, readonly))
            continue

        m = re.match(r'^(#{1,3})\s+(.*)$', line)
        if m:
            lv = len(m.group(1))
            out.append(f'<h{lv}>{inline(m.group(2))}</h{lv}>')
            i += 1; continue

        if line.strip() == '---':
            out.append('<hr/>'); i += 1; continue

        m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', line)
        if m:
            alt, path = m.group(1), m.group(2)
            cap = alt
            j = i + 1
            while j < n and lines[j].strip() == '':
                j += 1
            consumed = i
            if j < n:
                cm = re.match(r'^\*([^*].*[^*])\*$', lines[j].strip())
                if cm:
                    cap = cm.group(1); consumed = j
            out.append(f'<figure>{embed_image(alt, path)}<figcaption>{inline(cap)}</figcaption></figure>')
            i = consumed + 1; continue

        if line.startswith('|'):
            tbl = []
            while i < n and lines[i].startswith('|'):
                tbl.append(lines[i]); i += 1
            header = cells(tbl[0])
            body = tbl[1:]
            if body and is_separator(tbl[1]):
                body = tbl[2:]
            thead = '<thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in header) + '</tr></thead>'
            tbody = '<tbody>' + ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in cells(r)) + '</tr>' for r in body) + '</tbody>'
            out.append('<table>' + thead + tbody + '</table>')
            continue

        if re.match(r'^\s*[-*]\s+', line):
            items = []
            while i < n and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*]\s+', '', lines[i])); i += 1
            is_task_list = any(re.match(r'^\[[ xX]\]\s+', x) for x in items)
            li_parts = []
            for x in items:
                m = re.match(r'^\[([ xX])\]\s+(.*)$', x)
                if m:
                    checked = ' checked' if m.group(1).lower() == 'x' else ''
                    li_parts.append(
                        '<li class="task-item"><label>'
                        f'<input type="checkbox"{checked}><span>{inline(m.group(2))}</span>'
                        '</label></li>')
                else:
                    li_parts.append(f'<li>{inline(x)}</li>')
            cls = ' class="task-list"' if is_task_list else ''
            out.append(f'<ul{cls}>' + ''.join(li_parts) + '</ul>')
            continue

        if re.match(r'^\s*\d+\.\s+', line):
            items = []
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append(re.sub(r'^\s*\d+\.\s+', '', lines[i])); i += 1
            out.append('<ol>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + '</ol>')
            continue

        # 原生 HTML 區塊（例如置中的 logo）→ 原樣輸出，並把 <img svg> 內嵌
        if re.match(r'^\s*<\w+', line):
            buf = [line]; i += 1
            while i < n and lines[i].strip() != '':
                buf.append(lines[i]); i += 1
            out.append(inline_svg_imgs('\n'.join(buf)))
            continue

        if line.strip() == '':
            i += 1; continue

        para = [line]; i += 1
        while i < n and lines[i].strip() != '' and not re.match(r'^(#{1,3}\s|```|\||!\[|\s*[-*]\s|\s*\d+\.\s|---$|<\w)', lines[i]):
            para.append(lines[i]); i += 1
        text = ' '.join(p.strip() for p in para)
        cls = 'info' if text.startswith('確認一下') else ('warn' if text.startswith('如果出問題') else None)
        if cls:
            label, _, rest = text.partition('：')
            inner = f'<strong>{inline(label)}</strong>：{inline(rest)}' if rest else inline(text)
            out.append(f'<div class="callout {cls}"><p>{inner}</p></div>')
        else:
            out.append(f'<p>{inline(text)}</p>')

    return '\n'.join(out)


def main():
    src_name = sys.argv[1] if len(sys.argv) > 1 else "STUDENT_GUIDE.md"
    md_path = os.path.join(HERE, src_name)
    out_path = os.path.splitext(md_path)[0] + ".html"

    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    title_m = re.search(r'^#\s+(.*)$', md, re.M)
    title = title_m.group(1) if title_m else "教學講義"
    body = convert(md)

    # OS 切換列只在頁面真的有 mac/windows 雙版內容時才顯示（避免無意義的空按鈕）
    # has-os＝程式碼區塊有雙版本；os-variant＝::: mac / ::: windows 包起來的一般段落
    os_switch = (
        '<div class="os-switch" aria-label="選擇你的作業系統">'
        '<span class="os-switch-label">作業系統</span>'
        '<div class="os-switch-options">'
        '<button class="os-btn" type="button" data-os="mac" aria-pressed="false">macOS</button>'
        '<button class="os-btn" type="button" data-os="windows" aria-pressed="false">Windows</button>'
        '</div></div>\n'
    ) if ('has-os' in body or 'os-variant' in body) else ''

    doc = (
        '<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f'<title>{html.escape(title)}</title>\n'
        f'<style>{CSS}</style>\n</head>\n<body data-os="mac">\n'
        '<div class="gbar"></div>\n'
        + os_switch
        + body + '\n' + COPY_JS + '\n</body>\n</html>\n'
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"已產生 {out_path}（{len(doc):,} 字元）")


if __name__ == "__main__":
    main()

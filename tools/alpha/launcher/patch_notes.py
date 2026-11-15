"""The patch notes as the launcher shows them: its own page (launcher.py notes_page) instead of a Windows message box.

Pure logic, kept apart from Tk for the tests: the release text (PATCHNOTES-<version>.md, or a GitHub release's body) is read
into a title and sections of bullets, the bullets are wrapped to a width with the caller's own text measure, and the
result is cut into pages that fit a height. Bold (**...**) stays bold; pictographs, links and the installer hash go.
"""
import re
from pathlib import Path

BUNDLED = Path(__file__).resolve().parent / 'patchnotes.md'   # (this launcher's own version: shown without the network)
_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_BOLD = re.compile(r'\*\*(.+?)\*\*')


def plain(text):
    """without what the launcher's fonts cannot draw (pictographs past the basic plane, variation selectors)"""
    return ''.join(c for c in text if ord(c) <= 0xFFFF and not 0xFE00 <= ord(c) <= 0xFE0F and c != '‍')


def runs(text):
    """[(text, bold)] of a line with **bold** parts"""
    out, at = [], 0
    for m in _BOLD.finditer(text):
        if m.start() > at:
            out.append((text[at:m.start()], False))
        out.append((m.group(1), True))
        at = m.end()
    if at < len(text):
        out.append((text[at:], False))
    return [(t, b) for t, b in out if t]


def _heading(line):
    """a line that is a section's title: '## Title' or a line that is bold as a whole; None otherwise"""
    if line.startswith('#'):
        title = line.lstrip('#').replace('**', '')
    elif line.startswith('**') and line.endswith('**') and line.count('**') == 2:
        title = line[2:-2]
    else:
        return None
    title = title.strip()
    while title and (not title[0].isalnum() or ord(title[0]) >= 0x2000):   # (a leading symbol: the page has its own look)
        title = title[1:]
    return title.strip() or None


def parse(text):
    """(title or None, [(section title or None, [item, ...])]); an item is (bullet: bool, [(text, bold)])"""
    text = plain(text.replace('\r\n', '\n')).split('SHA-256')[0]   # (a release's body ends with the installer's hash)
    title, sections = None, []
    for raw in text.split('\n'):
        line = raw.strip()
        if not line or re.fullmatch(r'[-=_*]{3,}', line):
            continue
        if _LINK.fullmatch(line):   # (a line that is only a link: the launcher is already here)
            continue
        line = _LINK.sub(r'\1', line)
        head = _heading(line)
        if head:
            if title is None and not sections:
                title = head
            else:
                sections.append((head, []))
            continue
        bullet = line[:2] in ('- ', '* ', '• ')
        body = runs(line[2:].strip() if bullet else line)
        if not body:
            continue
        if not sections:
            sections.append((None, []))
        sections[-1][1].append((bullet, body))
    return title, [s for s in sections if s[1]]


def wrap(body, width, measure):
    """the lines of [(text, bold)] runs that fit width; measure(text, bold) is the caller's text width"""
    words = []
    for text, bold in body:
        if text[:1].isspace() and words:   # (the space between two weights belongs to the word before it)
            words[-1] = (words[-1][0].rstrip() + ' ', words[-1][1])
        words += [(w, bold) for w in re.findall(r'\S+\s*', text)]
    lines, line, used = [], [], 0.0
    for word, bold in words:
        w = measure(word.rstrip(), bold)
        if line and used + w > width:
            lines.append(line)
            line, used = [], 0.0
        line.append((word, bold))
        used += measure(word, bold)
    if line:
        lines.append(line)
    out = []
    for line in lines:   # (neighbours of one weight joined: one piece of text each)
        merged = []
        for word, bold in line:
            if merged and merged[-1][1] == bold:
                merged[-1] = (merged[-1][0] + word, bold)
            else:
                merged.append((word, bold))
        merged[-1] = (merged[-1][0].rstrip(), merged[-1][1])
        out.append(merged)
    return out


def blocks(sections, width, measure, line_h, head_h, item_gap, section_gap):
    """the page's rows in order: ('head', title, height) and ('item', bullet, lines, height); heights include the gap after"""
    out = []
    for title, items in sections:
        if title:
            out.append(('head', title, head_h))
        for i, (bullet, body) in enumerate(items):
            lines = wrap(body, width, measure)
            last = i == len(items) - 1 or items[i + 1][0] != bullet   # (a closing line stands apart from the bullets)
            gap = section_gap if last else item_gap
            out.append(('item', bullet, lines, len(lines) * line_h + gap))
    return out


def _cut(rows, height):
    pages, page, used = [], [], 0.0
    for i, row in enumerate(rows):
        h = row[-1]
        need = h
        if row[0] == 'head':   # (a section stays whole when a page can hold it; else its first item comes with the title)
            section = h
            for nxt in rows[i + 1:]:
                if nxt[0] == 'head':
                    break
                section += nxt[-1]
            need = section if section <= height else h + (rows[i + 1][-1] if i + 1 < len(rows) else 0)
        if page and used + need > height:
            pages.append(page)
            page, used = [], 0.0
        page.append(row)
        used += h
    if page:
        pages.append(page)
    return pages or [[]]


def paginate(rows, height):
    """rows cut into pages no taller than height: sections kept whole where they fit, a title never the last row of a page,
    and the pages about equally full (no last page with a single line)"""
    pages = _cut(rows, height)
    if len(pages) < 2:
        return pages
    total = sum(r[-1] for r in rows)
    target = total / len(pages)
    step = max(1.0, (height - target) / 12)
    while target < height:   # (the lowest page height that needs no more pages than the full height does)
        even = _cut(rows, target)
        if len(even) <= len(pages):
            return even
        target += step
    return pages


def version_key(text):
    return tuple(int(x) for x in re.findall(r'\d+', str(text).split('-')[0])[:3])


def bundled():
    """this launcher's own notes, or '' when the file is missing or empty"""
    try:
        return BUNDLED.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeDecodeError):
        return ''


def due(installed, seen, had_settings):
    """whether the notes open by themselves at this start: once after each update, never on a first install.
    installed: this launcher's version; seen: the version whose notes were last shown (None before 1.1.2 kept it);
    had_settings: a settings file was there before this start (so this is not a new installation)"""
    if seen is None:
        return bool(had_settings)
    return version_key(installed) != version_key(seen)

"""Turns an official PDF of the Constitution of the Dominican Republic into paragraphs, and paragraphs into provisions.
No AI, no fuzzy matching. Needs PyMuPDF.

paragraphs(pdf): every text line of every page (PyMuPDF 'dict' lines, spans joined), minus the page header (the
"-N-" page number and the rule of underscores under it). A whitespace-only line ends a paragraph (the PDFs are Word
exports that print an empty paragraph between paragraphs). Inside a page, a line that starts a provision or list item
(MARK) also starts a paragraph when the line before it is short. Across a page break the paragraph continues only when
the last line of the page reaches the right margin (justified text) or the next line starts in lower case, and the next
line does not start a provision. Lines of one paragraph are joined with one space. U+00A0 becomes a space; soft hyphens
and zero-width characters are removed; runs of whitespace become one space. The PDFs carry no end-of-line hyphenation
(checked: no line ends in letter + "-").

constitution(paras): from "PREÁMBULO" up to (not including) "DADA Y PROCLAMADA": the preamble, the structural headings
(TÍTULO, CAPÍTULO, SECCIÓN, DISPOSICIONES ...), the articles ("Artículo N.-"), the transitory provisions
("Primera:" ... ) and the final provision ("Disposición final:").
"""
import re

DROP = re.compile('[­​‌‍⁠﻿]')
WS = re.compile(r'[ \t\r\n  -   　]+')
HEADER = re.compile(r'^(-\s*\d+\s*-|_{10,})$')
MARK = re.compile(r'^(Artículo \d+\.|Párrafo\b|Disposición final|\d+\)|[a-zñ]\)|(TÍTULO|CAPÍTULO|SECCIÓN)\b|'
                  r'(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima|Decimoprimera|Decimosegunda|'
                  r'Decimotercera|Decimocuarta|Decimoquinta|Decimosexta|Decimoséptima|Decimoctava|Decimonovena|'
                  r'Vigésima)\b[^:]{0,20}:)')
ORDINALS = ['Primera', 'Segunda', 'Tercera', 'Cuarta', 'Quinta', 'Sexta', 'Séptima', 'Octava', 'Novena', 'Décima',
            'Decimoprimera', 'Decimosegunda', 'Decimotercera', 'Decimocuarta', 'Decimoquinta', 'Decimosexta', 'Decimoséptima',
            'Decimoctava', 'Decimonovena', 'Vigésima']
TRANS = re.compile(r'^(' + '|'.join(ORDINALS) + r')(?: (primera|segunda|tercera))?:\s*(.*)$')
ART = re.compile(r'^Artículo (\d+)\.-\s*(.*)$')
FINAL = re.compile(r'^Disposición final:\s*(.*)$')
KEY = re.compile(r'^(TÍTULO|CAPÍTULO|SECCIÓN|CONSTITUCIÓN$|DISPOSICIÓN FINAL$|DISPOSICIONES GENERALES$|'
                 r'DISPOSICIONES ESPECIALES$)')
BARE = re.compile(r'(TÍTULO|CAPÍTULO|SECCIÓN) [IVXLC]+')
HEAD = re.compile(r'^(TÍTULO|CAPÍTULO|SECCIÓN|DISPOSICIONES|DISPOSICIÓN|CONSTITUCIÓN)\b')


def clean(s: str) -> str:
    return WS.sub(' ', DROP.sub('', s)).strip()


def page_lines(pdf_path: str) -> list:
    """[[(text, x1)] per page], header removed; whitespace-only lines kept as ''."""
    import pymupdf
    out = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            ls = []
            for b in page.get_text('dict')['blocks']:
                for l in b.get('lines', []):
                    ls.append((clean(''.join(s['text'] for s in l['spans'])), l['bbox'][2]))
            k = 0
            while k < len(ls) and (ls[k][0] == '' or HEADER.match(ls[k][0])):
                k += 1
            out.append(ls[k:])
    return out


def paragraphs(pdf_path: str) -> list:
    pages = page_lines(pdf_path)
    right = max(x for p in pages for t, x in p if t)
    paras, cur, last = [], [], None   # last = (text, x1) of the previous non-empty line
    for pno, p in enumerate(pages):
        first = True
        for t, x in p:
            if not t:
                if cur:
                    paras.append(' '.join(cur))
                    cur = []
                continue
            if cur:
                full = last[1] >= right - 6
                if first:  # page break inside a paragraph
                    join = (full or t[:1].islower()) and not MARK.match(t)
                else:
                    join = not (MARK.match(t) and not full)
                if not join:
                    paras.append(' '.join(cur))
                    cur = []
            cur.append(t)
            last = (t, x)
            first = False
    if cur:
        paras.append(' '.join(cur))
    return paras


def trans_key(word: str) -> int:
    return ORDINALS.index(word) + 1


def constitution(paras: list) -> dict:
    """{'preamble': [paras], 'items': [(path, heading line, [paras])], 'structure': [(heading, path)]}"""
    i = paras.index('PREÁMBULO')
    j = next(k for k in range(i, len(paras)) if paras[k].startswith('DADA Y PROCLAMADA'))
    pre, items, struct, pending, cur = [], [], [], [], None
    prev_head = False
    for p in paras[i + 1:j]:
        m = ART.match(p)
        t = TRANS.match(p)
        fm = FINAL.match(p)
        if HEAD.match(p) or (prev_head and p.upper() == p and re.search('[A-ZÁÉÍÓÚÑ]', p)):
            # one heading = its keyword line plus its title, whether the PDF prints them as one paragraph or two
            bare = pending and BARE.fullmatch(pending[-1])
            if pending and (bare or not KEY.match(p)):
                pending[-1] += ' ' + p
            else:
                pending.append(p)
            prev_head = True
            continue
        prev_head = False
        if m:
            cur = (f'articulo-{int(m.group(1)):03d}.md', f'Artículo {m.group(1)}', [p])
        elif t:
            if t.group(2):
                raise ValueError(f'compound ordinal not handled: {p[:40]}')
            cur = (f'transitoria-{trans_key(t.group(1)):02d}.md', t.group(1), [p])
        elif fm:
            cur = ('disposicion-final.md', 'Disposición final', [p])
        else:
            if pending:
                raise ValueError(f'text after a heading that is not a provision: {pending} / {p[:60]}')
            (pre if cur is None else cur[2]).append(p)
            continue
        items.append(cur)
        struct += [(h, cur[0]) for h in pending]
        pending = []
    if pending:
        raise ValueError(f'heading at the end: {pending}')
    paths = [x[0] for x in items]
    if len(set(paths)) != len(paths):
        raise ValueError(f'duplicate provisions {sorted(k for k in set(paths) if paths.count(k) > 1)}')
    arts = [int(x[9:12]) for x in paths if x.startswith('articulo-')]
    if arts != list(range(1, len(arts) + 1)):
        raise ValueError('articles not numbered 1..N in order')
    tr = [int(x[12:14]) for x in paths if x.startswith('transitoria-')]
    if tr != list(range(1, len(tr) + 1)):
        raise ValueError(f'transitory provisions not 1..N in order: {tr}')
    if pre and pre[-1] == 'CONSTITUCIÓN':
        pre = pre[:-1]
    return {'preamble': pre, 'items': items, 'structure': struct}

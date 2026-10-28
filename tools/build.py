"""Builds the Dominican Republic git-for-law repository: the Constitution, 2010 to today, from the official texts
published by the Consultoría Jurídica del Poder Ejecutivo (consultoria.gov.do, publisher of the Gaceta Oficial).

    python -X utf8 build.py --repo DIR --today YYYY-MM-DD [--offline] [--wip] [--verify-rebuild]

Sources (see fetch.py): the site's collection of constitutions (GET /api/settings, `coleccion_constituciones`) and three
of its PDFs, the born-digital official texts of
  - the Constitution proclaimed on 26 January 2010 (Gaceta Oficial n.º 10561 of that day): the first version here;
  - the Constitution as reformed and proclaimed on 13 June 2015;
  - the Constitution as reformed and proclaimed on 27 October 2024.
Each text says (Disposición final) that it "entrará en vigencia a partir de su proclamación", so the in-force day is the
proclamation day printed in its "DADA Y PROCLAMADA" paragraph; the build stops unless that paragraph and the site's list
agree. The 2002 text in the collection is an image scan without a text layer and 1994 and older are OCR scans; they are
not used.

One commit per proclaimed text, authored by it, at noon in Santo Domingo (UTC-4, no summer time since 2000), built with
git fast-import (deterministic: the same data gives the same hashes). Commit messages are written as bytes (no CRs).
`--today` is the documentation commit's day (the data's retrieval day); it is required so that a rebuild on another day
gives the same hashes.
"""
import argparse
import datetime as dt
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch as F  # noqa: E402
import parse as P  # noqa: E402

FOLDER = 'constitucion'
COMMITTER = ('Lexifina', 'dominican-republic-law@lexifina.com')

# Files whose only change is spelling, capitalisation, punctuation or agreement (read by hand from --word-diff; the
# build stops if the set of changed files is not exactly WORDING | SUBSTANCE).
ACTS = [
    {'id': '2010', 'tag': 'constitucion/2010', 'author': 'Constitución de 2010',
     'email': 'constitucion-2010@consultoria.invalid', 'in_force': '2010-01-26', 'kind': 'baseline',
     'list_date': '26 de enero de 2010', 'gaceta': '10561',
     'proclaimed': 'hoy día veintiséis (26) del mes de enero del año dos mil diez (2010)',
     'title': 'Constitución de la República Dominicana, votada y proclamada por la Asamblea Nacional el 26 de enero '
              'de 2010'},
    {'id': '2015', 'tag': 'reforma/2015', 'author': 'Reforma constitucional de 2015',
     'email': 'reforma-2015@consultoria.invalid', 'in_force': '2015-06-13', 'kind': 'reform',
     'list_date': '13 de junio de 2015', 'gaceta': None,
     'proclaimed': 'hoy día trece (13) del mes de junio del año dos mil quince (2015)',
     'substance': ['articulo-124.md', 'transitoria-20.md'],
     'wording': ['articulo-035.md', 'articulo-063.md', 'articulo-093.md', 'articulo-108.md', 'articulo-128.md',
                 'articulo-141.md', 'articulo-157.md', 'articulo-178.md'],
     'title': 'Constitución de la República Dominicana, reformada y proclamada por la Asamblea Nacional Revisora el 13 '
              'de junio de 2015'},
    {'id': '2024', 'tag': 'reforma/2024', 'author': 'Reforma constitucional de 2024',
     'email': 'reforma-2024@consultoria.invalid', 'in_force': '2024-10-27', 'kind': 'reform',
     'list_date': '27 de octubre de 2024', 'gaceta': None,
     'proclaimed': 'hoy día veintisiete (27) del mes de octubre del año dos mil veinticuatro (2024)',
     'substance': ['articulo-081.md', 'articulo-166.md', 'articulo-167.md', 'articulo-169.md', 'articulo-171.md',
                   'articulo-178.md', 'articulo-179.md', 'articulo-209.md', 'articulo-268.md', 'articulo-274.md',
                   'articulo-278.md'] + [f'transitoria-{n:02d}.md' for n in range(1, 21)],
     'wording': ['articulo-018.md', 'articulo-035.md', 'articulo-064.md', 'articulo-095.md', 'articulo-154.md',
                 'articulo-217.md'],
     'title': 'Constitución de la República Dominicana, reformada y proclamada por la Asamblea Nacional Revisora el 27 '
              'de octubre de 2024'},
]
FINAL_TEXT = 'Esta Constitución entrará en vigencia a partir de su proclamación'


# ---- data ------------------------------------------------------------------------------------------------------------
def load(offline: bool) -> list:
    coll = {e['id']: e for e in F.settings(offline)['coleccion_constituciones']}
    out = []
    for a in ACTS:
        e = coll.get(a['id'])
        if not e or e['date'] != a['list_date'] or not e['title'].endswith(a['id']):
            raise SystemExit(f'collection entry {a["id"]}: {e}; review ACTS')
        pdf = F.constitution_pdf(e, offline)
        paras = P.paragraphs(str(pdf))
        dada = next(p for p in paras if p.startswith('DADA Y PROCLAMADA'))
        if a['proclaimed'] not in dada:
            raise SystemExit(f'{a["id"]}: proclamation day not as read: {dada[:300]}')
        v = P.constitution(paras)
        final = dict((x[0], x[2]) for x in v['items'])['disposicion-final.md']
        if not final[0].startswith('Disposición final: ' + FINAL_TEXT):
            raise SystemExit(f'{a["id"]}: Disposición final not as read: {final}')
        if a['gaceta']:
            head = ' '.join(paras[:12])
            if a['gaceta'] not in head or 'GACETA OFICIAL' not in head:
                raise SystemExit(f'{a["id"]}: Gaceta Oficial n.º {a["gaceta"]} not on the cover: {head[:300]}')
        out.append(dict(a, entry=e, pdf=pdf, sha256=F.sha256(pdf), paras=paras, dada=dada, version=v))
    return out


def files_of(v: dict) -> dict:
    d = {'preambulo.md': '\n'.join(v['preamble']) + '\n',
         'estructura.md': ''.join(f'{h} [{p}]\n' for h, p in v['structure'])}
    for path, _, paras in v['items']:
        d[path] = '\n'.join(paras) + '\n'
    return d


def changed(prev: dict, cur: dict) -> list:
    return sorted(n for n in set(prev) | set(cur) if prev.get(n) != cur.get(n))


# ---- dates -----------------------------------------------------------------------------------------------------------
def stamp(day: str, sec: int = 0) -> str:
    """Noon in Santo Domingo as a git raw date. The Dominican Republic keeps UTC-4 (AST) all year; its last clock
    change was a short-lived move to UTC-5 from 29 October to 3 December 2000, before this record starts."""
    d = dt.date.fromisoformat(day)
    if d < dt.date(2001, 1, 1):
        raise SystemExit(f'{day}: before the hard-coded zone rule (UTC-4 from 2001)')
    noon = dt.datetime(d.year, d.month, d.day, 12, 0, sec, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    return f'{int(noon.timestamp())} -0400'


# ---- messages --------------------------------------------------------------------------------------------------------
def message(a: dict, files: dict, prev: dict | None) -> bytes:
    e = a['entry']
    n_art = sum(1 for k in files if k.startswith('articulo-'))
    n_tr = sum(1 for k in files if k.startswith('transitoria-'))
    src = f'Source: {F.BASE}{e["url"]} (sha256 {a["sha256"]})'
    if a['kind'] == 'baseline':
        body = [f'Constitución de la República Dominicana de 2010', '', a['title'] + '.', '',
                'The first version in this record: the whole text of the Constitution proclaimed on 26 January 2010, '
                'which replaced the Constitution of 2002 (the 2002 text is published by the Consultoría only as an '
                'image scan, so it is not in this record). Every line is credited to the 2010 text; read blame on this '
                'commit as "in force from 26 January 2010 at the latest".', '',
                f'{n_art} articles, {n_tr} transitory provisions and the final provision.', '',
                'Kind: baseline', f'Published: Gaceta Oficial n.º {a["gaceta"]} del 26 de enero de 2010']
        affecting = []
    else:
        ch = changed(prev, files)
        want = sorted(set(a['substance']) | set(a['wording']))
        if ch != want:
            raise SystemExit(f'{a["id"]}: changed files {ch} != expected {want}; review ACTS')
        added = [k for k in ch if k not in prev]
        removed = [k for k in ch if k not in files]
        body = [f'Constitución: reforma proclamada el {a["list_date"]}', '', a['title'] + '.', '',
                'The Asamblea Nacional Revisora proclaimed the whole text of the reformed Constitution; this commit is '
                'that text, compared with the one before. '
                f'{len(ch)} files change: {len(added)} added, {len(removed)} removed, the rest rewritten.', '',
                'Changed in substance: ' + ', '.join(sorted(a['substance'])) + '.', '',
                'Changed in spelling, capitalisation, punctuation or agreement only, as printed in the proclaimed text '
                '(no reform is announced for them; they are credited to the proclaimed text, which is the whole text '
                'the Asamblea voted): ' + ', '.join(sorted(a['wording'])) + '.', '',
                f'{n_art} articles, {n_tr} transitory provisions and the final provision.', '',
                'Kind: reform']
        affecting = [f'Affecting: {FOLDER}/{k}' for k in ch]
    trailers = body[-2:] if a['kind'] == 'baseline' else body[-1:]
    body = body[:len(body) - len(trailers)]
    tr = trailers + [f'Proclaimed: {a["in_force"]}', f'In-force: {a["in_force"]}',
                     'In-force-basis: Disposición final: "' + FINAL_TEXT + ' por la Asamblea Nacional"; proclaimed on '
                     'the day its "DADA Y PROCLAMADA" paragraph gives (' + a['proclaimed'] + ')'] + affecting + [src]
    return ('\n'.join(body + tr) + '\n').encode('utf-8')


# ---- git -------------------------------------------------------------------------------------------------------------
def git(repo, *args, inp: bytes | None = None) -> str:
    e = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    r = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false', *args], cwd=repo, env=e,
                       input=inp, capture_output=True)
    if r.returncode:
        raise SystemExit(f'git {" ".join(args)}: {r.stderr.decode(errors="replace")}')
    return r.stdout.decode('utf-8')


def rmtree(p):
    def fix(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(p, onexc=fix)


def prepare(repo: Path) -> str:
    """Refuse a non-empty target that is not an earlier build of this repo (or the placeholder clone). Returns origin."""
    origin = ''
    if repo.exists() and any(repo.iterdir()):
        if not (repo / '.git').exists():
            raise SystemExit(f'{repo} is not empty and not a git repository')
        log = subprocess.run(['git', 'log', '--all', '--format=%ce|%s', '-500'], cwd=repo, capture_output=True,
                             text=True, encoding='utf-8').stdout.splitlines()
        ours = all(l.split('|')[0] in (COMMITTER[1], 'world-law@lexifina.com') for l in log if l)
        if not ours:
            raise SystemExit(f'{repo} holds commits that are not from this builder; refusing to overwrite')
        origin = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=repo, capture_output=True,
                                text=True).stdout.strip()
        for p in repo.iterdir():
            rmtree(p) if p.is_dir() else p.unlink()
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, 'init', '-q', '-b', 'main')
    if origin:
        git(repo, 'remote', 'add', 'origin', origin)
    return origin


def stream(commits: list, tags: list) -> bytes:
    """commits: [(author, email, day, message bytes, {path: text})]; tags: [(name, commit index)]."""
    out = bytearray()
    for i, (name, email, day, msg, files) in enumerate(commits, 1):
        out += f'commit refs/heads/main\nmark :{i}\n'.encode()
        out += f'author {name} <{email}> {stamp(day)}\n'.encode('utf-8')
        out += f'committer {COMMITTER[0]} <{COMMITTER[1]}> {stamp(day)}\n'.encode()
        out += f'data {len(msg)}\n'.encode() + msg + b'\n'
        if i > 1:
            out += f'from :{i - 1}\n'.encode()
        out += b'deleteall\n'
        for path in sorted(files):
            data = files[path] if isinstance(files[path], bytes) else files[path].encode('utf-8')
            if b'\r' in data:
                raise SystemExit(f'CR in {path}')
            out += f'M 100644 inline {path}\ndata {len(data)}\n'.encode('utf-8') + data + b'\n'
        out += b'\n'
    for name, i in tags:
        out += f'reset refs/tags/{name}\nfrom :{i}\n\n'.encode()
    return bytes(out)


def build(repo: Path, offline: bool, today: str, wip: bool = False):
    acts = load(offline)
    commits, tags, prev = [], [], None
    for a in acts:
        files = {f'{FOLDER}/{k}': v for k, v in files_of(a['version']).items()}
        msg = message(a, files_of(a['version']), prev)
        commits.append((a['author'], a['email'], a['in_force'], msg, files))
        tags.append((a['tag'], len(commits)))
        prev = files_of(a['version'])
    import reproduce
    docs = reproduce.docs(acts, today, HERE, wip)
    last = dict(commits[-1][4])
    last.update(docs)
    msg = ('Documentation, tools and REPRODUCE.md\n\nNo law text changes: README, LICENSE, SOURCES.md, REPRODUCE.md, '
           'corpus.json, acts.csv and the tools.\n\nKind: documentation\nIn-force: ' + today + '\n').encode('utf-8')
    commits.append((COMMITTER[0], COMMITTER[1], today, msg, last))
    prepare(repo)
    git(repo, 'fast-import', '--quiet', '--done', inp=stream(commits, tags) + b'done\n')
    git(repo, 'checkout', '-q', '-f', 'main')
    return git(repo, 'rev-parse', 'HEAD').strip(), acts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--today', required=True, help='documentation commit day: the data retrieval day')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--wip', action='store_true', help='README says "building" (for the wip branch only)')
    ap.add_argument('--verify-rebuild', action='store_true',
                    help='build again in a temporary folder and compare HEAD with --repo (does not touch --repo)')
    args = ap.parse_args()
    dt.date.fromisoformat(args.today)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.verify_rebuild:
        want = git(Path(args.repo), 'rev-parse', 'HEAD').strip()
        with tempfile.TemporaryDirectory() as td:
            got, _ = build(Path(td) / 'r', True, args.today, args.wip)
        print('rebuild', got, 'repo', want, 'IDENTICAL' if got == want else 'DIFFERENT')
        raise SystemExit(0 if got == want else 1)
    head, acts = build(Path(args.repo), args.offline, args.today, args.wip)
    for a in acts:
        v = a['version']
        print(a['tag'], a['in_force'], len(v['items']), 'provisions')
    print('main', head)


if __name__ == '__main__':
    main()

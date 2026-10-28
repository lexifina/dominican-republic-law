"""Checks the built repository against the official PDFs (read from the builder's cache, so it runs offline).

    python -X utf8 check_repo.py --repo DIR [--record]

1. Every law commit (one per tag): the files under constitucion/ equal, byte for byte, the files rendered from that
   version's official PDF (build.files_of over parse.constitution).
2. Independently of the build's parser and PDF reader: the letters and digits (casefolded, everything else removed) of
   each version, read from the RAW PDF by pypdf (a different PDF library from the PyMuPDF the build uses), page headers
   ("-N-" and the rule of underscores) dropped, from after "PREÁMBULO" up to "DADA Y PROCLAMADA", equal the letters and
   digits of the repository's files at that commit in reading order (preamble, then each provision preceded by the
   headings estructura.md gives it).
3. Each commit's author, e-mail, In-force trailer and tag are as listed in build.ACTS; the last commit is the
   documentation and changes no law file; 0 merges; dates never go backwards and none is after the documentation day;
   no CR in any message or law file.
Blobs are read through `git ls-tree` + `git cat-file --batch`.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402

NOT_ALNUM = re.compile(r'[\W_]+')


def alnum(s: str) -> str:
    return NOT_ALNUM.sub('', s.casefold())


def git(repo, *args) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout


def blobs(repo, commit, folder):
    names = [n for n in git(repo, 'ls-tree', '-r', '--name-only', commit, folder + '/').split('\n') if n]
    p = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, input=''.join(f'{commit}:{n}\n' for n in names).encode(),
                       capture_output=True)
    out, buf, i = {}, p.stdout, 0
    for n in names:
        j = buf.index(b'\n', i)
        size = int(buf[i:j].split()[2])
        out[n.split('/', 1)[1]] = buf[j + 1:j + 1 + size].decode('utf-8')
        i = j + 1 + size + 1
    return out


def reading_order(files: dict) -> str:
    heads = {}
    for line in files['estructura.md'].splitlines():
        m = re.fullmatch(r'(.*) \[([a-z0-9-]+\.md)\]', line)
        heads.setdefault(m.group(2), []).append(m.group(1))

    def key(n):
        if n.startswith('articulo-'):
            return (0, int(n[9:12]))
        if n.startswith('transitoria-'):
            return (1, int(n[12:14]))
        return (2, 0)
    parts = [files['preambulo.md']]
    for n in sorted((n for n in files if n not in ('preambulo.md', 'estructura.md')), key=key):
        parts += heads.get(n, [])
        parts.append(files[n])
    return '\n'.join(parts)


def raw_pdf_alnum(pdf: Path) -> str:
    """Independent reader: pypdf text of every page, headers dropped, between PREÁMBULO and DADA Y PROCLAMADA."""
    import pypdf
    keep = []
    for page in pypdf.PdfReader(str(pdf)).pages:
        for line in (page.extract_text() or '').split('\n'):
            s = line.strip()
            if re.fullmatch(r'-\s*\d+\s*-', s) or re.fullmatch(r'_{10,}', s):
                continue
            keep.append(line)
    a = alnum('\n'.join(keep))
    i = a.index(alnum('PREÁMBULO')) + len(alnum('PREÁMBULO'))
    j = a.index(alnum('DADA Y PROCLAMADA'), i)
    return a[i:j]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--record', action='store_true')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    repo = a.repo
    acts = B.load(offline=True)
    rows = [l.split('\t') for l in git(repo, 'log', '--reverse', '--first-parent', '--format=%H%x09%an%x09%ae%x09%ct%x09'
                                       '%(trailers:key=In-force,valueonly,separator=)', 'main').splitlines()]
    problems = []
    if len(rows) != len(acts) + 1 or rows[-1][1] != 'Lexifina':
        problems.append(f'{len(rows)} commits; expected {len(acts)} law commits and the documentation commit')
    if git(repo, 'rev-list', '--merges', '--count', 'main').strip() != '0':
        problems.append('merge commits on main')
    times = [int(r[3]) for r in rows]
    if times != sorted(times) or max(times) != times[-1]:
        problems.append('commit dates go backwards or after the documentation commit')
    msgs = subprocess.run(['git', 'log', '--format=%B', 'main'], cwd=repo, capture_output=True).stdout
    if b'\r' in msgs:
        problems.append('CR in a commit message')
    files_checked, alnum_checked, prev = 0, [], None
    for (h, au, em, ct, inf), act in zip(rows, acts):
        tag = git(repo, 'rev-parse', act['tag'] + '^{commit}').strip()
        if tag != h:
            problems.append(f'{act["tag"]} does not point at its commit')
        if (au, em, inf.strip()) != (act['author'], act['email'], act['in_force']):
            problems.append(f'{act["tag"]}: author/In-force {au} {em} {inf}')
        got = blobs(repo, h, B.FOLDER)
        want = B.files_of(act['version'])
        for n in sorted(set(got) | set(want)):
            files_checked += 1
            if got.get(n) != want.get(n):
                problems.append(f'{act["tag"]}: {n} differs from the official text')
            if '\r' in got.get(n, ''):
                problems.append(f'{act["tag"]}: CR in {n}')
        off = raw_pdf_alnum(act['pdf'])
        rep = alnum(reading_order(got))
        if off != rep:
            k = next((i for i, (x, y) in enumerate(zip(off, rep)) if x != y), min(len(off), len(rep)))
            problems.append(f'{act["tag"]}: letters/digits differ at {k}: {off[k - 40:k + 40]!r} vs {rep[k - 40:k + 40]!r}')
        alnum_checked.append(f'{act["tag"]} {len(off)} letters and digits equal')
        prev = got
    doc = blobs(repo, rows[-1][0], B.FOLDER)
    if doc != prev:
        problems.append('the documentation commit changes law files')
    summary = (f'{len(acts)} versions: {files_checked} files compared byte for byte with the official texts, '
               f'{sum(1 for p in problems if "differs from" in p)} mismatches; independent pypdf letters-and-digits '
               f'check ({"; ".join(alnum_checked)}); 0 merges, dates in order, no CRs unless listed; '
               f'{len(problems)} problems')
    print(summary)
    for p in problems:
        print('PROBLEM', p)
    if a.record:
        vp = HERE / 'verification.json'
        rec = json.loads(vp.read_text(encoding='utf-8')) if vp.exists() else {}
        rec['check'] = {'summary': summary, 'problems': problems}
        vp.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8',
                      newline='\n')
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()

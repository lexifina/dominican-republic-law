"""Functional smoke test of the built Dominican Republic repository: the things a reader does with it work.
Standard library only.

    python -X utf8 scripts/dominican-republic-law/test_repo.py --repo ../dominican-republic-law [--record]
    python -X utf8 tools/test_repo.py                   # from inside the repository

It asserts that:
1. `git blame` on article 124 names the 2010 text before 2015 and the 2015 reform after it, and on article 81 the
   2024 reform now;
2. tools/in_force_on.py gives article 124 and article 81 before and after each reform, each equal to the file at that
   day's tag, gives a deleted transitory provision only before 2024, prints the whole text in reading order, and
   refuses a day before the record;
3. `git log --follow` on article 124 lists its texts in the order they took effect;
4. every tag resolves to a commit, every commit has an ISO `In-force:` trailer, and every trailer block parses;
5. no commit is authored by Lexifina except the documentation commit (the last one), and every law author uses an
   `.invalid` address;
6. the corpus.json citation rule finds the provisions that cite article 124 with `git grep -E`;
7. every git or tool command in the README's table runs and prints something.
With --record the result is written to verification.json next to this script (for REPRODUCE.md).
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAW = re.compile(r'^(Constitución de 2010|Reforma constitucional de (2015|2024))$')
F124 = 'constitucion/articulo-124.md'
F81 = 'constitucion/articulo-081.md'


def default_repo() -> Path:
    if (HERE.parent / '.git').exists():
        return HERE.parent
    return HERE.parents[2] / 'dominican-republic-law'


class Smoke:
    def __init__(self, repo: Path):
        self.repo = repo
        self.results = []

    def git(self, *args):
        out = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
        if out.returncode:
            raise AssertionError(f'git {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout

    def tool(self, *args, ok=True):
        out = subprocess.run([sys.executable, '-X', 'utf8', 'tools/in_force_on.py', *args], cwd=self.repo,
                             capture_output=True, text=True, encoding='utf-8')
        if ok and out.returncode:
            raise AssertionError(f'in_force_on {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout if ok else out

    def check(self, name, fn):
        try:
            detail = fn() or ''
            self.results.append((name, True, detail))
            print(f'PASS {name}: {detail}')
        except AssertionError as exc:
            self.results.append((name, False, str(exc)))
            print(f'FAIL {name}: {exc}')

    def authors(self, rev, path):
        return {l[7:] for l in self.git('blame', '--line-porcelain', rev, '--', path).splitlines()
                if l.startswith('author ')}

    def blame(self):
        a = self.authors('constitucion/2010', F124)
        b = self.authors('reforma/2015', F124)
        c = self.authors('main', F81)
        assert a == {'Constitución de 2010'}, f'2010: {a}'
        assert b == {'Reforma constitucional de 2015'}, f'2015: {b}'
        assert 'Reforma constitucional de 2024' in c and all(LAW.match(x) for x in c), f'main art. 81: {c}'
        return f'{F124}: {a.pop()} then {b.pop()}; {F81} on main: {", ".join(sorted(c))}'

    def on_date(self):
        done = []
        for tag, path, before, after in [('reforma/2015', F124, '2015-06-12', '2015-06-13'),
                                         ('reforma/2024', F81, '2024-10-26', '2024-10-27'),
                                         ('reforma/2015', 'constitucion/transitoria-20.md', '2015-06-12', '2015-06-13')]:
            name = path.split('/')[1]
            a = self.tool(before, 'constitucion', name, ok=False)
            b = self.tool(after, 'constitucion', name)
            assert b == self.git('show', f'{tag}:{path}'), f'{after} is not {path} at {tag}'
            if name == 'transitoria-20.md':
                assert a.returncode != 0 and 'was not in the text' in a.stderr, 'transitoria-20 before 2015'
            else:
                assert a.returncode == 0 and a.stdout == self.git('show', f'{tag}~1:{path}') and a.stdout != b, \
                    f'{before} is not {path} before {tag}'
            done.append(f'{name} {before} -> {after}')
        gone = self.tool('2024-10-27', 'constitucion', 'transitoria-20', ok=False)
        assert gone.returncode != 0, 'transitoria-20 still printed after 2024'
        whole = self.tool('2012-01-01', 'constitucion')
        assert whole.startswith('PREÁMBULO') and 'Artículo 277.-' in whole and 'Disposición final:' in whole
        assert whole.index('Artículo 1.-') < whole.index('Artículo 277.-') < whole.index('Primera:'), 'order'
        early = self.tool('2010-01-25', 'constitucion', '1', ok=False)
        assert early.returncode != 0 and 'not in the record' in early.stderr, 'a day before the record must fail'
        return '; '.join(done) + '; transitoria-20 gone after 2024; whole text in reading order; 2010-01-25 refused'

    def follow(self):
        out = self.git('log', '--follow', '--format=%an%x09%(trailers:key=In-force,valueonly,separator=)', 'main', '--',
                       F124)
        rows = [l.split('\t') for l in out.splitlines() if l]
        days = [d.strip() for _, d in rows]
        assert len(rows) >= 2, f'{len(rows)} commits'
        assert days == sorted(days, reverse=True), f'not in date order {days}'
        assert all(LAW.match(a) for a, _ in rows), f'authors {[a for a, _ in rows]}'
        return f'{F124}: ' + ', '.join(f'{a} {d}' for a, d in rows)

    def tags_and_trailers(self):
        tags = self.git('tag').split()
        assert len(tags) == 3, f'tags {tags}'
        for t in tags:
            self.git('rev-parse', '--verify', '-q', f'{t}^{{commit}}')
        rows = self.git('log', '--format=%H%x09%an%x09%(trailers:key=In-force,valueonly,separator=)', 'main').splitlines()
        bad = [r for r in rows if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', r.split('\t')[2].strip())]
        assert not bad, f'missing or malformed In-force {bad[:2]}'
        for h in [r.split('\t')[0] for r in rows]:
            msg = subprocess.run(['git', 'log', '-1', '--format=%B', h], cwd=self.repo, capture_output=True).stdout
            parsed = subprocess.run(['git', 'interpret-trailers', '--parse'], input=msg, capture_output=True).stdout
            assert b'In-force:' in parsed and b'Kind:' in parsed, f'{h[:10]}: trailer block does not parse'
        return f'{len(tags)} tags resolve; {len(rows)} commits carry In-force; every trailer block parses'

    def lexifina(self):
        rows = self.git('log', '--format=%H%x09%an%x09%ae%x09%cn', 'main').splitlines()
        by_lex = [r for r in rows if r.split('\t')[1] == 'Lexifina']
        assert len(by_lex) == 1 and by_lex[0] == rows[0], f'{len(by_lex)} commits by Lexifina'
        assert all(r.split('\t')[3] == 'Lexifina' for r in rows), 'a committer other than Lexifina'
        assert all(r.split('\t')[2].endswith('.invalid') for r in rows[1:]), 'a law author without .invalid'
        return f'only the documentation commit {rows[0][:10]} is by Lexifina; {len(rows) - 1} law commits'

    def citation(self):
        c = json.loads((self.repo / 'corpus.json').read_text(encoding='utf-8'))['citation']
        m = re.fullmatch(c['file'], F124)
        assert m and m.group(2) == '124', 'file rule does not match article 124'
        pat = c['cites'].replace('{n}', m.group(2))
        hits = sorted({l.split(':', 2)[1] for l in self.git('grep', '-n', '-E', pat, 'main', '--', 'constitucion')
                       .splitlines() if l})
        assert 'constitucion/articulo-268.md' in hits, f'article 268 (2024) cites article 124: {hits}'
        assert all(re.search(pat, self.git('show', f'main:{h}')) for h in hits)
        return f'{pat!r} finds {len(hits)} files: {", ".join(h.split("/")[1] for h in hits)}'

    def readme(self):
        text = (self.repo / 'README.md').read_text(encoding='utf-8')
        table = text[text.index('## The questions'):text.index('PowerShell splits')]
        cmds = [c.replace('\\|', '|') for c in re.findall(r'`([^`]+)`', table) if c.startswith(('git ', 'python '))]
        assert len(cmds) >= 10, f'only {len(cmds)} commands found'
        for c in cmds:
            args = shlex.split(c)
            if args[0] == 'python':
                args[0:1] = [sys.executable, '-X', 'utf8']
            out = subprocess.run(args, cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
            assert out.returncode == 0, f'{c}: exit {out.returncode} {out.stderr.strip()[:200]}'
            assert out.stdout.strip(), f'{c}: printed nothing'
        return f'{len(cmds)} README commands ran and printed output'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=None)
    ap.add_argument('--record', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    s = Smoke(Path(args.repo) if args.repo else default_repo())
    s.check('blame names the texts', s.blame)
    s.check('text before and after each reform', s.on_date)
    s.check('log --follow in date order', s.follow)
    s.check('tags resolve, In-force on every commit', s.tags_and_trailers)
    s.check('only the documentation commit is by Lexifina', s.lexifina)
    s.check('citation rule works with git grep -E', s.citation)
    s.check('README commands run', s.readme)
    ok = all(r[1] for r in s.results)
    print(f'{sum(r[1] for r in s.results)}/{len(s.results)} passed')
    if args.record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['smoke'] = {'passed': sum(r[1] for r in s.results), 'total': len(s.results),
                        'results': [{'test': n, 'ok': o, 'detail': d} for n, o, d in s.results]}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8',
                     newline='\n')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()

"""Prints the Constitution of the Dominican Republic, or one provision of it, as it stood on a given day, from this
repository.

    python tools/in_force_on.py 2020-01-01 constitucion/articulo-124.md   # article 124 on 1 January 2020
    python tools/in_force_on.py 2020-01-01 constitucion 124               # the same
    python tools/in_force_on.py 2020-01-01 constitucion transitoria-20    # a transitory provision
    python tools/in_force_on.py 2020-01-01 constitucion                   # the whole text, in reading order

Each commit carries the day its text took effect in an `In-force:` trailer. The text in force on a day is the last
commit on or before it, read by that trailer (not by commit time, so the reader's time zone does not matter).
Standard library only.
"""
import datetime as dt
import re
import subprocess
import sys

FOLDER = 'constitucion'


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8', check=True).stdout


def commit_on(day: str) -> tuple:
    out = git('log', '--first-parent', '--format=%H%x09%(trailers:key=In-force,valueonly,separator=)%x09%(trailers:'
              'key=Kind,valueonly,separator=)', 'main')
    for line in out.splitlines():
        h, d, kind = (line.split('\t') + ['', ''])[:3]
        if kind.strip() == 'documentation':
            continue
        if d.strip() and d.strip() <= day:
            return h, d.strip()
    return '', ''


def fname(key: str) -> str:
    key = key.split('/')[-1]
    if key.isdigit():
        return f'articulo-{int(key):03d}.md'
    return key if key.endswith('.md') else key + '.md'


def order(name: str) -> tuple:
    for i, (pre, n) in enumerate((('articulo-', 3), ('transitoria-', 2))):
        if name.startswith(pre):
            return (i, int(name[len(pre):len(pre) + n]))
    return (2, 0)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    day = sys.argv[1]
    dt.date.fromisoformat(day)
    target = sys.argv[2].rstrip('/')
    one = sys.argv[3] if len(sys.argv) > 3 else (target.split('/', 1)[1] if '/' in target else '')
    c, since = commit_on(day)
    if not c:
        sys.exit(f'{FOLDER} is not in the record on {day} (the record starts on 2010-01-26).')
    if one:
        name = fname(one)
        try:
            sys.stdout.write(git('show', f'{c}:{FOLDER}/{name}'))
        except subprocess.CalledProcessError:
            sys.exit(f'{FOLDER}/{name} was not in the text in force on {day} (text in force since {since}).')
        return
    names = [n.split('/', 1)[1] for n in git('ls-tree', '-r', '--name-only', c, FOLDER + '/').split('\n') if n]
    text = blobs(c, names)
    heads = {}
    for line in text['estructura.md'].splitlines():
        m = re.fullmatch(r'(.*) \[([a-z0-9-]+\.md)\]', line)
        if m:
            heads.setdefault(m.group(2), []).append(m.group(1))
    sys.stdout.write('PREÁMBULO\n' + text['preambulo.md'])
    for n in sorted((n for n in names if order(n)[0] < 2 or n == 'disposicion-final.md'), key=order):
        for h in heads.get(n, []):
            sys.stdout.write(h + '\n')
        sys.stdout.write(text[n])


def blobs(commit: str, names: list) -> dict:
    """Every file in one `git cat-file --batch` call (one process, not one per file)."""
    p = subprocess.run(['git', 'cat-file', '--batch'], input=''.join(f'{commit}:{FOLDER}/{n}\n' for n in names).encode(),
                       capture_output=True, check=True)
    out, buf, i = {}, p.stdout, 0
    for n in names:
        j = buf.index(b'\n', i)
        size = int(buf[i:j].split()[2])
        out[n] = buf[j + 1:j + 1 + size].decode('utf-8')
        i = j + 1 + size + 1
    return out


if __name__ == '__main__':
    main()

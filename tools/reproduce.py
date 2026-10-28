"""Writes the repository's documentation: README.md, LICENSE, SOURCES.md, REPRODUCE.md, corpus.json, acts.csv,
.gitattributes and the tools. Called by build.py; deterministic (no clock, no network). verification.json (written by
check_repo.py and test_repo.py with --record) is read when it exists, so the second build carries the results of the
checks on the first."""
import json
import subprocess
from pathlib import Path

TOOLS = ('build.py', 'fetch.py', 'parse.py', 'reproduce.py', 'check_repo.py', 'test_repo.py', 'in_force_on.py')
CORPUS = 'do/national/acts'


def blob(p: Path) -> str:
    return subprocess.run(['git', 'hash-object', '--no-filters', str(p)], capture_output=True,
                          text=True).stdout.strip()


def docs(acts, day: str, here: Path, wip: bool = False) -> dict:
    out = {}
    ver = {}
    vp = here / 'verification.json'
    if vp.exists():
        ver = json.loads(vp.read_text(encoding='utf-8'))
    first, last = acts[0]['in_force'], acts[-1]['in_force']
    corpus = {
        'corpus': CORPUS,
        'name': 'Dominican law: the Constitution (2010, reformed 2015 and 2024)',
        'label': 'Dominican Republic',
        'language': 'es',
        'acts': [a['title'] for a in acts],
        'history_from': first,
        'record_to': day,
        'record_note': (f'From the Constitution proclaimed on 26 January 2010 (in force {first}) to the reform '
                        f'proclaimed on 27 October 2024 (in force {last}); the Consultoría Jurídica del Poder '
                        f'Ejecutivo lists no later constitution on {day}, the day the data was retrieved and checked.'),
        'history': 'in-force',
        'in_force_trailer': 'In-force',
        'has_future_branch': False,
        'checked_on': day,
        'built': day,
        'dates': {'commit': 'in-force', 'other_trailers': ['Proclaimed', 'Published', 'In-force-basis'],
                  'time': '12:00 America/Santo_Domingo (UTC-4; no summer time in the record)'},
        'scope': {
            'trailer': 'Applies',
            'when_absent': 'this corpus records no scope notes (no commit carries Applies:); the absence is not a '
                           'statement that the change reaches every case',
            'default_reach': {
                'rule': 'non-retroactivity: "La ley sólo dispone y se aplica para lo porvenir" (Constitución, art. 110)',
                'meaning': 'a law applies to the future only; it reaches back only when favourable to a person on '
                           'trial or serving a sentence, and never to alter legal certainty arising from situations '
                           'established under earlier law',
                'authority': 'Constitución de la República Dominicana (2010, 2015, 2024), artículo 110 '
                             '(Irretroactividad de la ley)',
                'decided_here': False}},
        'tool': 'tools/in_force_on.py',
        'citation': {'file': '(constitucion)/articulo-0*([0-9]+)\\.md',
                     'cites': '([Aa]rtículo|[Aa]rtículos|[Aa]rt\\.) {n}([^0-9]|$)'},
    }
    out['corpus.json'] = json.dumps(corpus, indent=2, ensure_ascii=False) + '\n'
    rows = ['tag,author,kind,proclaimed,in_force,provisions,source_url,source_sha256']
    for a in acts:
        rows.append(','.join('"' + str(x).replace('"', '""') + '"' for x in [
            a['tag'], a['author'], a['kind'], a['list_date'], a['in_force'], len(a['version']['items']),
            'https://www.consultoria.gov.do' + a['entry']['url'], a['sha256']]))
    out['acts.csv'] = '\n'.join(rows) + '\n'
    out['.gitattributes'] = '* text eol=lf\n'

    out['LICENSE'] = (
        'Source of the legal texts: Consultoría Jurídica del Poder Ejecutivo (CJPE), República Dominicana,\n'
        'publisher of the Gaceta Oficial: https://www.consultoria.gov.do/consultas/constituciones\n\n'
        f'Terms of use (https://www.consultoria.gov.do/terminos, checked {day}), section 4 "Propiedad intelectual y\n'
        'reutilización": "Los textos legales, decretos, resoluciones y gacetas publicadas en este portal son documentos\n'
        'de dominio público. Las marcas, emblemas institucionales y el diseño gráfico del portal pertenecen al Estado\n'
        'Dominicano y están protegidos por las leyes de propiedad intelectual." No emblem or design of the portal is\n'
        'reproduced here. Section 3 forbids "el uso de robots, scripts automatizados o técnicas de extracción no\n'
        'autorizada (scraping) que degraden el rendimiento de los servicios"; this build made a handful of single\n'
        'requests (see REPRODUCE.md). The repository is private until the user decides otherwise.\n\n'
        'Only the printed Gaceta Oficial is authoritative.\n\n'
        'Attribution for the legal texts: "Textos: Consultoría Jurídica del Poder Ejecutivo, República Dominicana,\n'
        'https://www.consultoria.gov.do/".\n\n'
        'The history (commits and commit messages), the tables and the tools are dedicated to the public domain under\n'
        'CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/legalcode\n')

    out['SOURCES.md'] = f'''# Sources

| Source | Use | Status ({day}) |
| --- | --- | --- |
| [Consultoría Jurídica del Poder Ejecutivo: Colección de constituciones](https://www.consultoria.gov.do/consultas/constituciones) | the list (`/api/settings`, `coleccion_constituciones`) and the PDFs of 2010, 2015 and 2024 | used |
| The same collection, 2002 | image scan, no text layer | not used |
| The same collection, 1844 to 1994 | OCR scans (Adobe Paper Capture) with recognition errors | not used |
| [Consultoría: Consulta de legislación](https://www.consultoria.gov.do/consultas) (`POST /api/consultas/search`) | acts as enacted (the reform laws) | Cloudflare challenge; not used |
| Gaceta Oficial (print) | authoritative | not online as consolidated text |

## Legal basis for reuse

- The CJPE terms of use, section 4: "Los textos legales, decretos, resoluciones y gacetas publicadas en este portal son
  documentos de dominio público." (https://www.consultoria.gov.do/terminos)
- The copyright law's exclusion for official texts (Ley n.º 65-00 sobre Derecho de Autor) was not read for this record:
  the site's legislation search is behind a Cloudflare challenge, and no other official copy was fetched.

## robots.txt

`https://www.consultoria.gov.do/robots.txt` ({day}): `User-Agent: *`, `Allow: /`, `Disallow:` `/oficina-virtual/dashboard/`,
`/oficina-virtual/dashboard/*`, `/api/auth/`, `/api/admin/`. No rule names ClaudeBot, Claude-Web, anthropic-ai or GPTBot.
'''

    ok = ''
    if ver:
        c, s = ver.get('check', {}), ver.get('smoke', {})
        ok = (f'- check_repo.py: {c.get("summary", "not recorded")}\n'
              f'- test_repo.py: {s.get("passed", "?")}/{s.get("total", "?")} passed\n')
        if ver.get('rebuild'):
            ok += f'- rebuild: {ver["rebuild"]}\n'
    table = '\n'.join(f'| `{a["tag"]}` | {a["author"]} | {a["kind"]} | {a["in_force"]} | '
                      f'{sum(1 for x in a["version"]["items"] if x[0].startswith("articulo-"))} | '
                      f'{sum(1 for x in a["version"]["items"] if x[0].startswith("transitoria-"))} |' for a in acts)
    status = ('**Status: building. Work in progress on the `wip` branch; not final.**\n\n') if wip else ''
    out['README.md'] = f'''# The Constitution of the Dominican Republic, change by change

{status}The Constitution of the Dominican Republic as a git repository, in Spanish, from the Constitution proclaimed on
26 January 2010 through the reforms of 2015 and 2024. Each proclaimed text is one commit, credited to it and dated the
day it took effect, at noon in Santo Domingo. Source: the official texts published by the Consultoría Jurídica del Poder
Ejecutivo (consultoria.gov.do), which publishes the Gaceta Oficial.

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did article 124 (presidential election) say on 1 January 2015? | `python tools/in_force_on.py 2015-01-01 constitucion 124` |
| ... and on 1 January 2020, after the 2015 reform? | `python tools/in_force_on.py 2020-01-01 constitucion 124` |
| ... and today? | `python tools/in_force_on.py {day} constitucion 124` |
| The whole Constitution as it stood on 1 January 2012 | `python tools/in_force_on.py 2012-01-01 constitucion` |
| Which text wrote each line of article 81? | `git blame main -- constitucion/articulo-081.md` |
| Every change to article 124, with its text and day | `git log --follow --format="%an %(trailers:key=In-force,valueonly,separator=)" main -- constitucion/articulo-124.md` |
| Exactly what the 2024 reform changed in article 81, word by word | `git show --word-diff reforma/2024 -- constitucion/articulo-081.md` |
| Everything one reform changed | `git show --stat reforma/2024` |
| The texts, with their in-force days | `git log --format="%an, in force %(trailers:key=In-force,valueonly,separator=)" main` |
| One tag per text | `git tag --list` |
| Which provisions cite article 124? | `git grep -n -E "[Aa]rtículo 124([^0-9]\|$)" main -- constitucion` |

PowerShell splits `git show $(...):path`; use `$r = git rev-list -1 reforma/2015; git show "$($r):constitucion/articulo-124.md"`.
For a date, prefer `tools/in_force_on.py`, which reads the `In-force:` trailer; `git rev-list --before=DATE` compares
commit times in your own time zone and flips at noon on the day itself (use `--before="DATE 23:59:59 -0400"`).

## The texts

| Tag | Author | Kind | In force | Articles | Transitory provisions |
| --- | --- | --- | --- | --- | --- |
{table}

See [`acts.csv`](acts.csv). The Consultoría lists no constitution after 27 October 2024 (checked {day}).

## The dates, and which one we use

Each text says in its Disposición final that it "entrará en vigencia a partir de su proclamación por la Asamblea
Nacional", and its closing paragraph ("DADA Y PROCLAMADA ... hoy día ...") gives the proclamation day. **Commits are
dated that day**, at noon in Santo Domingo (UTC-4). The proclamation day is also in the `Proclaimed:` trailer, and how
the in-force day was read is in `In-force-basis:`. The 2010 text was printed in Gaceta Oficial n.º 10561 the same day
(`Published:`); the 2015 and 2024 PDFs carry no Gaceta number, so none is given.

## What "author" means

The author of a commit is the proclaimed text (`Reforma constitucional de 2015`, address
`reforma-2015@consultoria.invalid`), so `git blame` names it. The committer is always `Lexifina`. Only the documentation
commit is authored by Lexifina.

## Read this before comparing versions

- **The first version is a baseline.** The 2010 Constitution replaced the Constitution of 2002, which the Consultoría
  publishes only as an image scan; earlier constitutions (1844 to 1994) are OCR scans. So the record starts in 2010 and
  every line of 2010 is credited to the 2010 text (`Kind: baseline`).
- **Each reform is the whole proclaimed text.** The Asamblea Nacional Revisora proclaims the complete reformed
  Constitution, and each commit is that text. Besides the reformed provisions, the 2015 text differs from 2010 in 8
  articles, and 2024 from 2015 in 6, only in spelling, capitalisation, punctuation or agreement (for example "27 de
  Febrero" / "27 de febrero" in article 35, which 2015 changed and 2024 changed back). No reform announces these; they are
  credited to the proclaimed text and listed apart in each commit message.
- **2024 replaced the transitory provisions.** The 20 transitory provisions of 2015 gave way to 10 new ones, so
  `transitoria-01.md` to `transitoria-10.md` hold different provisions before and after 2024, and 11 to 20 are deleted.
- **Blame credits whole lines**: one line is one paragraph. Use `--word-diff` for the words.

## How it is checked

`tools/check_repo.py` reads every version back from git and compares it with the official PDF, file by file and byte
for byte, and again as a stream of letters and digits read from the PDF by a second, independent extractor (pypdf, not
the PyMuPDF parser the build uses). `tools/test_repo.py` checks that the commands above work. See
[`REPRODUCE.md`](REPRODUCE.md).
{ok}
## Files

`constitucion/articulo-NNN.md` is one article, `transitoria-NN.md` one transitory provision (numbered from its ordinal,
"Primera" = 01) and `disposicion-final.md` the final provision; one line per paragraph, exactly as printed, including
the article number and title ("Artículo 124.- Elección presidencial. ..."). `preambulo.md` is the preamble and
`estructura.md` the titles, chapters and sections, each with the file it opens.

## What it does not show

- The constitutions before 2010 (1844 to 2002); the image and OCR scans are not used.
- The reform laws themselves (the "ley de declaratoria de necesidad de la reforma"), which the site's search hides
  behind a challenge; the changes are read from the proclaimed texts.
- Rulings of the Tribunal Constitucional and laws that change how the Constitution works without changing its words.
  Words unchanged does not mean law unchanged.

## How it is built

`tools/build.py --repo DIR --today {day}` (see REPRODUCE.md). No AI wrote any legal text and no model runs at build time.

## Licence

The Consultoría's terms say the legal texts are in the public domain (section 4). The repository is private. See
[`LICENSE`](LICENSE). Tools, history and tables: CC0.
'''

    cache = here / 'cache'
    src_rows = '\n'.join(f'- {a["tag"]}: `https://www.consultoria.gov.do{a["entry"]["url"]}` ("{a["entry"]["title"]}", '
                         f'{a["entry"]["date"]}), cached as `{a["id"]}.pdf`, sha256 `{a["sha256"]}`' for a in acts)
    import fetch
    settings_sha = fetch.sha256(cache / 'settings.json')
    blobs = '\n'.join(f'- `{n}`: `{blob(here / n)}`' for n in TOOLS)
    out['REPRODUCE.md'] = f'''# Reproduce

Data retrieved {day}. The build is deterministic: the same data gives the same commit hashes.

## Sources and requests

The Consultoría Jurídica del Poder Ejecutivo (https://www.consultoria.gov.do), publisher of the Gaceta Oficial. Its
"Colección de constituciones" page reads its list from `GET /api/settings` (field `coleccion_constituciones`: id, title,
date and `/uploads/...pdf` of each official text). The build reads:
- `https://www.consultoria.gov.do/api/settings`, cached as `settings.json`, sha256 `{settings_sha}` (the list changes
  when the site's settings change; the build stops unless the three entries still have the dates it was written for);
{src_rows}

**Fetch rate:** one request at a time, a pause of at least 2 seconds between requests, curl with `--compressed` and a
User-Agent; 4 requests for the data. Before the build, the gate checks and exploration made about 20 further requests to
consultoria.gov.do, one at a time: robots.txt, the home, constitutions, consultations and terms pages, three JavaScript
chunks (to find `/api/settings`), `/api/consultas/document-types`, four PDFs looked at and not used (1844, 1966, 1994,
2002), and two `POST /api/consultas/search` requests, both answered with a Cloudflare challenge (not retried and not got
round). All answers are cached in `cache/` (git-ignored) and never fetched twice; `--offline` uses the cache only.

## Steps

1. `python -X utf8 tools/build.py --repo <dir> --today {day}` (online once; then add `--offline`).
2. `python -X utf8 tools/check_repo.py --repo <dir> --record` and `python -X utf8 tools/test_repo.py --repo <dir> --record`.
3. Build again (the documentation then carries the results of step 2), then
   `python -X utf8 tools/build.py --repo <dir> --today {day} --offline --verify-rebuild`.
4. `python scripts/global-law/check_corpus.py <dir>` (in the lexifina repo).

Tool versions: Python 3.12, PyMuPDF 2.0 (`pymupdf`, the build's PDF reader), pypdf 6.21 (the check's independent
reader), git 2.46 (fast-import), curl (Windows). Builder blob hashes (`git hash-object`):
{blobs}

## Method

- `parse.paragraphs`: every text line of every page (PyMuPDF), minus the page header (the "-N-" page number and the rule
  under it). A whitespace-only line ends a paragraph (the PDFs are Word exports with an empty paragraph between
  paragraphs); a line that starts a provision or list item after a short line also starts one; across a page break a
  paragraph continues only when the last line of the page reaches the right margin or the next line starts in lower
  case. Lines of a paragraph are joined with one space; U+00A0 becomes a space; soft hyphens and zero-width characters
  are removed. The PDFs have no end-of-line hyphenation.
- `parse.constitution`: from `PREÁMBULO` up to `DADA Y PROCLAMADA`. "Artículo N.-" opens an article, "Primera:" ...
  "Vigésima:" a transitory provision, "Disposición final:" the final provision; TÍTULO / CAPÍTULO / SECCIÓN lines and
  their titles are headings (`estructura.md`). The build stops on duplicate or out-of-order numbers.
- In-force day: the proclamation day; the build stops unless the "DADA Y PROCLAMADA" paragraph gives exactly the day
  in `build.ACTS` and the Disposición final says the text takes effect on proclamation.
- Each reform commit: the build stops unless the changed files are exactly the ones listed in `build.ACTS` as changed
  in substance or in wording only (that split was read by hand from word diffs).
- Commit dates: noon, UTC-4 (no clock change in the Dominican Republic since December 2000), via git fast-import;
  messages are bytes with LF only.

## Decisions by hand, and AI

No model wrote legal text or ran at build time. The code was written by Claude Code with Claude Opus 5.5
(`claude-opus-5-5`), which also ran the gate checks (Cuba, Haiti and Puerto Rico failed; see the lexifina triage
notes) and read the in-force rule. Decisions by hand:
- the record starts in 2010: the 2002 text is an image scan and older texts are OCR scans with recognition errors;
- the whole proclaimed text of each reform is credited to that reform, including the wording-only differences, which
  are listed apart in each commit message;
- no second act: the Consultoría's legislation database holds acts as enacted only (no consolidations), and its
  search is behind a Cloudflare challenge.

## Verification record

{ok or '(not yet recorded)'}'''

    for n in TOOLS:
        out[f'tools/{n}'] = (here / n).read_bytes().replace(b'\r\n', b'\n')
    return out

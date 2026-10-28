# The Constitution of the Dominican Republic, change by change

The Constitution of the Dominican Republic as a git repository, in Spanish, from the Constitution proclaimed on
26 January 2010 through the reforms of 2015 and 2024. Each proclaimed text is one commit, credited to it and dated the
day it took effect, at noon in Santo Domingo. Source: the official texts published by the Consultoría Jurídica del Poder
Ejecutivo (consultoria.gov.do), which publishes the Gaceta Oficial.

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did article 124 (presidential election) say on 1 January 2015? | `python tools/in_force_on.py 2015-01-01 constitucion 124` |
| ... and on 1 January 2020, after the 2015 reform? | `python tools/in_force_on.py 2020-01-01 constitucion 124` |
| ... and today? | `python tools/in_force_on.py 2026-10-28 constitucion 124` |
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
| `constitucion/2010` | Constitución de 2010 | baseline | 2010-01-26 | 277 | 19 |
| `reforma/2015` | Reforma constitucional de 2015 | reform | 2015-06-13 | 277 | 20 |
| `reforma/2024` | Reforma constitucional de 2024 | reform | 2024-10-27 | 278 | 10 |

See [`acts.csv`](acts.csv). The Consultoría lists no constitution after 27 October 2024 (checked 2026-10-28).

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
- check_repo.py: 3 versions: 890 files compared byte for byte with the official texts, 0 mismatches; independent pypdf letters-and-digits check (constitucion/2010 147566 letters and digits equal; reforma/2015 147935 letters and digits equal; reforma/2024 147786 letters and digits equal); 0 merges, dates in order, no CRs unless listed; 0 problems
- test_repo.py: 7/7 passed

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

`tools/build.py --repo DIR --today 2026-10-28` (see REPRODUCE.md). No AI wrote any legal text and no model runs at build time.

## Licence

The Consultoría's terms say the legal texts are in the public domain (section 4). The repository is private. See
[`LICENSE`](LICENSE). Tools, history and tables: CC0.

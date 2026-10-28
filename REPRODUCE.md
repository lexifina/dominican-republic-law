# Reproduce

Data retrieved 2026-10-28. The build is deterministic: the same data gives the same commit hashes.

## Sources and requests

The Consultoría Jurídica del Poder Ejecutivo (https://www.consultoria.gov.do), publisher of the Gaceta Oficial. Its
"Colección de constituciones" page reads its list from `GET /api/settings` (field `coleccion_constituciones`: id, title,
date and `/uploads/...pdf` of each official text). The build reads:
- `https://www.consultoria.gov.do/api/settings`, cached as `settings.json`, sha256 `f66baa97cea37449e5be5e184ae77a7cfd6fa38449f076df0bfa4aebbcbcbde6` (the list changes
  when the site's settings change; the build stops unless the three entries still have the dates it was written for);
- constitucion/2010: `https://www.consultoria.gov.do/uploads/1786127675672-863979729.pdf` ("Constitución 2010", 26 de enero de 2010), cached as `2010.pdf`, sha256 `7946d51ac77f2e38f04761640feb9dadbc5d337d202f0c73e1a5f16c8f1b3b82`
- reforma/2015: `https://www.consultoria.gov.do/uploads/1786127563508-283061414.pdf` ("Constitución 2015", 13 de junio de 2015), cached as `2015.pdf`, sha256 `b094363254d6d045a7d9ab99a9ef150f52943de8f284146a461c7e9f566a4bce`
- reforma/2024: `https://www.consultoria.gov.do/uploads/1786127298458-819263307.pdf` ("Constitución 2024", 27 de octubre de 2024), cached as `2024.pdf`, sha256 `0f4da013601cbb9dda0cd6ec7695611180ec0d1af51550041ed67875f56dcaa3`

**Fetch rate:** one request at a time, a pause of at least 2 seconds between requests, curl with `--compressed` and a
User-Agent; 4 requests for the data. Before the build, the gate checks and exploration made about 20 further requests to
consultoria.gov.do, one at a time: robots.txt, the home, constitutions, consultations and terms pages, three JavaScript
chunks (to find `/api/settings`), `/api/consultas/document-types`, four PDFs looked at and not used (1844, 1966, 1994,
round). All answers are cached in `cache/` (git-ignored) and never fetched twice; `--offline` uses the cache only.

## Steps

1. `python -X utf8 tools/build.py --repo <dir> --today 2026-10-28` (online once; then add `--offline`).
2. `python -X utf8 tools/check_repo.py --repo <dir> --record` and `python -X utf8 tools/test_repo.py --repo <dir> --record`.
3. Build again (the documentation then carries the results of step 2), then
   `python -X utf8 tools/build.py --repo <dir> --today 2026-10-28 --offline --verify-rebuild`.
4. `python scripts/global-law/check_corpus.py <dir>` (in the lexifina repo).

Tool versions: Python 3.12, PyMuPDF 2.0 (`pymupdf`, the build's PDF reader), pypdf 6.21 (the check's independent
reader), git 2.46 (fast-import), curl (Windows). Builder blob hashes (`git hash-object`):
- `build.py`: `7d32634e126938af1c39c2b21a4f0367c32eeffa`
- `fetch.py`: `49fd8b88f7f93daa169322e00fb95787a8a029ec`
- `parse.py`: `5fac9abe1942e84b285ee47ff19c472f8ebfc27e`
- `reproduce.py`: `57688721dff52b5a2bbdb266b913433614af231c`
- `check_repo.py`: `d2b4c41e22547e183cad7594d023408462c179f4`
- `test_repo.py`: `a91f9185d14b195168d4e54f592f0400e172620a`
- `in_force_on.py`: `b10b73c285863303f584580e0a264c3eeac202e2`

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

## Verification record

- check_repo.py: 3 versions: 890 files compared byte for byte with the official texts, 0 mismatches; independent pypdf letters-and-digits check (constitucion/2010 147566 letters and digits equal; reforma/2015 147935 letters and digits equal; reforma/2024 147786 letters and digits equal); 0 merges, dates in order, no CRs unless listed; 0 problems
- test_repo.py: 7/7 passed

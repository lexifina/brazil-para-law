# Pará: law history in git

The law of the State of Pará (Estado do Pará) (Brazil) as a git history: one file per Artigo, one paragraph per line, so `git blame`, `git log` and `git diff` work line by line. The text is Portuguese, the only official language.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

| Folder | Act | Versions |
| --- | --- | ---: |
| `constituicao/` | Constituição do Estado do Pará (5 October 1989), text in force | 1 |
| `lc-<year>-<number>/` | Leis Complementares (142 of the 208 in the Banco de Leis) | 1 each |

The Constituição and every Lei Complementar whose PDF carries alteration notes are given **only as their text in force**, credited to the Assembleia Legislativa as the oldest version available: the wordings in between are not reconstructed yet, so no earlier version is shown rather than a wrong one. A Lei Complementar with no alteration note is given **as enacted**, credited to itself. Left out (66): Leis Complementares the PDF marks as revoked, those a later Lei Complementar alters or revokes without a note in their own PDF (the compiled PDFs are not always brought up to date), those taking effect on another day than their publication, those whose PDF names no Diário Oficial date (most from 1990-1996) or a date that does not fit the act's own date, and one whose table the second PDF reader reads in a different order. Ordinary Leis, decrees and the Emendas Constitucionais as acts are not included yet.

## Source

[Banco de Leis da ALEPA](https://bancodeleis.alepa.pa.gov.br), published by the Assembleia Legislativa do Estado do Pará (ALEPA). Each version names the page it was taken from and that page's sha256, in `data/versions.json`.

## Dates

The Constituição's text in force, and each altered Lei Complementar's, is dated by the latest date among the alterations the Assembleia's notes cite ("* Inciso III alterado pela Emenda Constitucional nº 24, de 05/05/2004, publicada no DOE Nº 30.190, de 12/05/2004"); "* Ver" and veto notes do not date a version. An unaltered Lei Complementar is dated by the Diário Oficial do Estado its PDF names under the signature (it takes effect on its publication, as its last article says). Commits are at noon in Belém.

## How it is built

Lexifina reads the sources listed here and records each act's dated versions, and the laws that made each change, in one corpus file. `tools/build.py` writes this repository from that file, and the same corpus always gives the same commit hashes; `REPRODUCE.md` gives the details and the checks. A model (Claude) wrote Lexifina's code; it wrote no legal text, and no model runs when the history is built.

Every text is the Assembleia's PDF (Assessoria Técnica), read from its text layer. In it the text in force is printed in black, the alteration notes in blue and each earlier wording, after "* A redação anterior continha o seguinte teor:", in red; runs of "x" separate successive earlier wordings. The text in force leaves out every coloured line and fragment, those separators, lines starting "*" (publication and veto notes, the notice that the text does not replace the Diário Oficial) and the letterhead. One file per Art.; articles of the Constituição's Ato das Disposições Constitucionais Transitórias are `adt-*`. Headings of the Títulos, Capítulos and Seções stand above the first article under them; `000-titulo.md` holds the title, the ementa and the preamble or enacting formula. Paragraphs are rebuilt from the PDF's line layout; tables are one line per PDF line.

## How it is checked

Every version is read back from git on the day it took effect (`tools/check_repo.py`) and must match the corpus; an independent letters-and-digits comparison of every version against the source page must show no difference. Results are in `REPRODUCE.md`.

## What "author" means

The author of each commit is the law that made the text, or, for a consolidated text, the publisher, with an e-mail address that cannot exist; the committer is always Lexifina.

## Limits

Not a complete history: an altered act starts at its text in force. The text is not the official version: only the Diário Oficial do Estado is authoritative. Whether a Lei Complementar was altered is judged from its own PDF's notes and from the other Leis Complementares in the Banco de Leis; ordinary laws and Emendas Constitucionais are not checked. Text after the last article (place, date, signatures, the Diário Oficial line) stays in the last article's file. Line breaks inside a paragraph that runs across a page are joined by layout rules and may in rare cases join two paragraphs.

## Licence

See [LICENSE](LICENSE): Brazilian law texts are not protected by copyright (Lei 9.610/1998, art. 8, IV). Fonte: Banco de Leis da ALEPA, Assembleia Legislativa do Estado do Pará (ALEPA).

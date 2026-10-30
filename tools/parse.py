"""Builds corpus.d parts for Pará from the retrieved ALEPA Banco de Leis PDFs (no network). Private (never published).

    python -X utf8 parse.py --today YYYY-MM-DD [--only constituicao|lc] [--list]

The Constituição do Estado do Pará is one PDF compiled by the Assessoria Técnica of the Assembleia Legislativa
(Word, text layer). The text in force is printed in black; each alteration is marked by a note in blue ("* Inciso III
alterado pela Emenda Constitucional nº 24, de 05/05/2004, publicada no DOE Nº 30.190, de 12/05/2004.") and each earlier
wording is printed in red after "* A redação anterior continha o seguinte teor:"; runs of x ("xxxxxxxxxx") separate
successive earlier wordings. The text in force is the black text without those separators and without lines starting
"*" (the publisher's notes). It is given as one version, credited to the publisher, dated by the latest date the
alteration notes cite.

A Lei Complementar PDF is the act as published. It is given as enacted only when no Lei Complementar listed after it
cites it (by number and year or date) in its text, and it shows no alteration notes or coloured text.
"""
import argparse, json, re, sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import units_of, write_part, sha, norm, dates_in  # noqa: E402

CACHE = HERE / '.cache'
BASE = 'https://bancodeleis.alepa.pa.gov.br/'
CON_URL = BASE + 'arquivos/especificas/c_estaduallei__84635.pdf'
SITE = 'https://bancodeleis.alepa.pa.gov.br/index.php'
SEP = re.compile(r'^[xX]{6,}$')
LETTERHEAD = re.compile(r'^([-_]{10,}|ASSEMBLEIA LEGISLATIVA [-–] ASSESSORIA TÉCNICA)$')
MARK = re.compile(r'^(Art\.|Artigo|§|Parágrafo|[IVXLC]+\s*[-–]|[a-z]\)|\d+\)|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE)')


def black(c):
    return all(((c >> k) & 255) <= 0x40 for k in (0, 8, 16))


def raw(url):
    p = CACHE / 'raw' / sha(url.encode())
    return p.read_bytes() if p.exists() else None


def read(b, split_inline=False):
    """PDF bytes -> (lines [(kind, text)], kept-out lines [text], notes [text] (the non-black "*" notes), coloured)."""
    d = pymupdf.open(stream=b, filetype='pdf')
    rows = []  # (page, y0, x0, x1, text, is_black, coloured part of a mixed line)
    for pno, page in enumerate(d):
        for blk in page.get_text('dict')['blocks']:
            for l in blk.get('lines', []):
                sp = [s for s in l['spans'] if s['text'].strip()]
                if not sp:
                    continue
                cols = {black(s['color']) for s in sp}
                if len(cols) > 1:  # an inline note in colour inside a black line: the black spans are the text
                    kt = norm(''.join(s['text'] for s in l['spans'] if black(s['color']) or not s['text'].strip()))
                    ct = [norm(s['text']) for s in l['spans'] if not black(s['color']) and s['text'].strip()]
                    rows.append((pno, l['bbox'][1], l['bbox'][0], l['bbox'][2], kt, True, ct))
                    continue
                t = ''.join(s['text'] for s in l['spans'])
                rows.append((pno, l['bbox'][1], l['bbox'][0], l['bbox'][2], norm(t), cols.pop(), None))
    kept, aside, notes = [], [], []
    for r in rows:
        t = r[4]
        if r[6]:
            aside.extend(r[6])  # its coloured fragments (they may come before or after the black ones)
            notes.extend(r[6])
            if not t:
                continue
        if not r[5]:
            aside.append(t)
            if t.startswith('*'):
                notes.append(t)
            elif notes and not t.startswith(('“', '"')) and aside[-2:-1] == [notes[-1]]:
                notes[-1] += ' ' + t  # a note's wrapped second line
            continue
        if t.startswith('*') or SEP.match(t) or LETTERHEAD.match(t):
            aside.append(t)
            if t.startswith('*'):
                notes.append(t)
            continue
        kept.append(r)
    right = max((r[3] for r in kept), default=0)
    paras, prev = [], None
    for r in kept:
        pno, y, x0, x1, t = r[:5]
        centred = x0 > 140 and abs((x0 + x1) / 2 - 328) < 40
        new = (prev is None or centred or prev[6] or MARK.match(t) or x0 > prev[2] + 20 or
               (pno == prev[0] and y - prev[1] > 20) or (pno != prev[0] and prev[3] < right - 40))
        if new:
            paras.append(['h2' if centred else 'p', t])
        else:
            paras[-1][1] += ' ' + t
        prev = (pno, y, 85 if not centred else x0, x1, t, None, centred)
    if split_inline:  # an article or a sole paragraph printed on the same line as the end of the one before
        paras = [[k, x] for k, t in paras
                 for x in re.split(r'(?<=[:.;]) (?=(?:Art\. ?\d+[º°o]?\.? |Parágrafo único\. ))', t)]
    # the transitional act's heading is printed on two centred lines
    out = []
    for kind, t in paras:
        if out and out[-1][0] == 'h2' and kind == 'h2' and re.match(r'(?i)^ATOS? DAS DISPOSI[ÇC][ÕO]ES$', out[-1][1]):
            out[-1] = ('h2', out[-1][1] + ' ' + t)
            continue
        out.append((kind, t))
    return out, aside, notes, any(not r[5] for r in rows)


COUNTRY = {
    'code': 'BR-PA', 'name': 'Pará', 'slug': 'brazil-para', 'lang': 'pt', 'tz': 'America/Belem',
    'future_branch': 'futuro',
    'publisher': {'name': 'Assembleia Legislativa do Estado do Pará (Banco de Leis)',
                  'email': 'bancodeleis@alepa.pa.gov.br.invalid'},
    'default_in_force_rule': {
        'text': 'Decreto-Lei 4.657/1942 (LINDB) art. 1: unless it says otherwise, a law takes effect 45 days after its '
                'official publication. Pará laws almost always say "Esta Lei entra em vigor na data de sua '
                'publicação"; this record dates the Constituição\'s text in force by the latest alteration its notes '
                'cite.',
        'source': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm'},
    'licence_note': 'Texts: Banco de Leis, Assembleia Legislativa do Estado do Pará, bancodeleis.alepa.pa.gov.br. '
                    'Lei 9.610/1998 art. 8 IV: the texts of laws and other official acts are not protected by '
                    'copyright. Non-official text: only the Diário Oficial do Estado is authoritative.',
}
DECISIONS = [
    'The Constituição do Estado do Pará (promulgated 5 October 1989) is the Assembleia Legislativa\'s compiled text (PDF '
    'of the Assessoria Técnica). It is given only as its text in force, credited to the publisher as the oldest version '
    'available and dated by the latest date its alteration notes cite. The wordings in between are not reconstructed, '
    'so no earlier version is given rather than a wrong one.',
    'In the compiled PDF the text in force is printed in black (one passage in dark grey); the publisher\'s alteration '
    'notes ("* Inciso III alterado pela Emenda Constitucional nº 24, de 05/05/2004, publicada no DOE ...") are in blue '
    'and each earlier wording, after "* A redação anterior continha o seguinte teor:", in red. The text in force leaves '
    'out every coloured line, the runs of "x" that separate successive earlier wordings, lines starting "*" (the '
    'publication notes under the preamble) and the letterhead "ASSEMBLEIA LEGISLATIVA - ASSESSORIA TÉCNICA". "* Ver" '
    'notes do not date a version.',
    'One file per Art. (articles of the Ato das Disposições Constitucionais Transitórias as adt-*); headings of the '
    'Títulos, Capítulos and Seções stand above the first article under them; "000-titulo" holds the title and the '
    'preamble. Text after the last article (place, date, signatures) stays with the last article. Paragraphs are rebuilt '
    'from the PDF\'s line layout (a blank line, a centred line, an indent or a new Art./§/inciso/alínea starts one).',
]
AI = ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used as legal "
      "text or dates: every word comes from the ALEPA Banco de Leis PDFs."]


def is_alteration(n):
    return not re.match(r'^\*\s*(Ver\b|Vide|Veja|Obs|Nota|Publicad)', n, re.I)


def constituicao(today):
    b = raw(CON_URL)
    lines, aside, notes, _ = read(b)
    alter = sorted(d for n in notes if is_alteration(n) for d in dates_in(n) if '1989-10-05' < d <= today)
    units = units_of(lines)
    law_key = 'constituicao-1989'
    laws = {law_key: {'label': 'Constituição do Estado do Pará', 'title': 'Constituição do Estado do Pará',
                      'kind': 'law', 'enacted': '1989-10-05', 'published': '1989-10-06', 'url': CON_URL,
                      'temporary_until': None, 'restores': None, 'note': None}}
    v = {'from': alter[-1], 'source_url': CON_URL, 'sha256': sha(b), 'units': units,
         'note': (f'Text in force as compiled by the Assessoria Técnica of the Assembleia Legislativa do Pará; the '
                  f'Constituição was altered on {len(set(alter))} date(s) its notes cite, the latest {alter[-1]}.')}
    act = {'slug': 'constituicao', 'short': 'CE-PA', 'title': 'Constituição do Estado do Pará', 'url': CON_URL,
           'first_law': None, 'earlier_laws': [law_key], 'versions': [v]}
    return act, laws, alter


def part(name, acts, laws, today, decisions=DECISIONS):
    c = {'country': COUNTRY,
         'sources': [{'name': 'Banco de Leis da Assembleia Legislativa do Estado do Pará (ALEPA): the PDF of each act',
                      'url': SITE, 'retrieved': today, 'licence': COUNTRY['licence_note'],
                      'notes': f'{len(acts)} acts in this part.'}],
         'laws': laws, 'acts': acts, 'applies': [], 'decisions': decisions, 'ai_use': AI}
    return write_part(HERE / 'corpus.d', name, c)


LC_DECISIONS = [
    'Leis Complementares: the PDF of each act in the Banco de Leis of the Assembleia Legislativa (Assessoria Técnica), '
    'the act as published with the Assembleia\'s notes. An act whose PDF shows no alteration note, that no later Lei '
    'Complementar in the Banco de Leis cites next to words of alteration or repeal ("altera", "acrescenta", "revoga", '
    '"passa a vigorar", ...), whose final article says it takes effect on its publication ("entra em vigor na data de '
    'sua publicação"), is given as enacted, credited to itself and dated by the Diário Oficial do Estado the PDF names '
    'under the signature ("DOE Nº 36.729, DE 12/08/2026"). An act whose PDF carries alteration notes ("*Redação do '
    'Inciso II alterada pela Lei Complementar nº 205, de 29 de abril de 2026, publicada no DOE ...") is given only as '
    'its text in force, credited to the publisher and dated by the latest date those notes cite, provided every later '
    'Lei Complementar that cites it with words of alteration or repeal is named in its notes. Left out: acts the PDF '
    'marks as revoked ("Legislação REVOGADA pela ..."), acts touched by a later Lei Complementar their notes do not '
    'name, acts taking effect on another day, acts with no Diário Oficial date, and scanned PDFs.',
    'The text in force leaves out every line and fragment printed in colour (the Assembleia\'s notes in blue, earlier '
    'wordings in red, inline notes such as "(Redação dada pela Lei Complementar nº 149, de 2022)"), lines starting "*" '
    '(notes on vetoes and the notice "Este texto não substitui o publicado no Diário Oficial do Estado do Pará") and '
    'the letterhead. Veto notes do not date a version. Ordinary laws and Emendas Constitucionais that might bear on a '
    'Lei Complementar are not checked.',
    'One file per Art.; "000-titulo" holds the title, the ementa and the enacting formula. Text after the last article '
    '(place, date, signatures, the Diário Oficial line) stays with the last article. Tables are one line per PDF line. '
    'Paragraphs are rebuilt from the PDF\'s line layout.',
]
ALTER = re.compile(r'(?i)alterad|acrescid|acrescentad|inserid|inclu[ií]d|revogad|reda[çc][ãa]o|renumerad|suprimid|'
                   r'modificad|nova reda')
TOUCH = re.compile(r'(?i)\baltera|acresc|revoga|passa(?:m)? a vigorar|nova reda|inclu[ií]|suprim|modific|renumer')
# left out after check_letters.py: the second reader orders this act's table cells differently
LEFT_OUT = {90: 'a table read in a different order by the second PDF reader'}
MONTHS = 'janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro'.split()


def doe_date(lines):
    """The Diário Oficial date under the signature ('DOE Nº 36.729, DE 12/08/2026.', 'DOE Nº 34.815, DE 29.12.2021 -
    EDIÇÃO EXTRA', 'DOE Nº 36.582, DE 01 DE ABRIL DE 2026')."""
    for _, l in reversed(lines[-6:]):
        if not re.match(r'(?i)^DOE\b', l):
            continue
        m = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', l)
        if m:
            return f'{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
        m = re.search(r'(?i)(\d{1,2})[º°]?\s+DE\s+([A-ZÇa-zç]+)\s+DE\s+(\d{4})', l)
        if m and m.group(2).lower() in MONTHS:
            return f'{int(m.group(3)):04d}-{MONTHS.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}'
    return None


def lc_records(today):
    idx = json.loads((CACHE / 'lc-index.json').read_text(encoding='utf-8'))
    recs = []
    for a in idx:
        b = raw(a['pdf']) if a['pdf'] else None
        r = {'n': int(a['numero']), 'y': a['ano'], 'pdf': a['pdf'], 'ementa': norm(a['ementa']), 'b': b}
        if b is None:
            r['why'] = 'no PDF' if not a['pdf'] else 'not fetched'
        elif not b.startswith(b'%PDF'):
            r['why'] = 'not a PDF'
        else:
            try:
                r['lines'], r['aside'], r['notes'], _ = read(b, split_inline=True)
            except Exception as e:  # noqa: BLE001
                r['why'] = f'unreadable: {e}'[:120]
            else:
                r['text'] = ' '.join(l for _, l in r['lines'])
                if len(r['text']) < 200:
                    r['why'] = 'no text layer (scanned)'
        recs.append(r)
    recs.sort(key=lambda r: r['n'])
    for r in recs:
        if 'why' in r:
            continue
        notes = [n for n in r['notes'] if not re.search(r'(?i)n[ãa]o substitui o (texto )?publicado', n)]
        alts = [n for n in notes if ALTER.search(n) and not re.search(r'(?i)vetad|veto', n)]
        cite = re.compile(rf'(?i)Lei Complementar(?: Estadual)?\s*n[º°o.]*\s*0*{r["n"]}(?!\d)(?:/(?:{r["y"]}|{r["y"][2:]})\b|,?\s*de\s[^.;]{{0,30}}?{r["y"]}\b)')
        hits = []
        for s in recs:
            if s['n'] <= r['n'] or 'text' not in s:
                continue
            for m in cite.finditer(s['text']):
                win = s['text'][max(0, m.start() - 250):m.end() + 150]
                if TOUCH.search(win) or TOUCH.search(s['ementa']) and cite.search(s['ementa']):
                    hits.append(s['n'])
                    break
        named = {int(x) for n in notes for x in re.findall(r'(?i)Lei Complementar(?: Estadual)?\s*n[º°o.]*\s*0*(\d+)', n)}
        unnamed = [h for h in hits if h not in named]
        published = doe_date(r['lines'])
        vig = re.findall(r'(?i)entra(?:rá)? em vigor[^.;]{0,60}', r['text'])
        if r['n'] in LEFT_OUT:
            r['why'] = LEFT_OUT[r['n']]
        elif any(re.search(r'(?i)legisla[çc][ãa]o\s+revogada|lei complementar\s+revogada|revogada (integralmente|totalmente)', n) for n in notes):
            r['why'] = 'revoked (its PDF says so)'
        elif unnamed:
            r['why'] = f'touched later by LC {unnamed[0]}, which its notes do not name'
        elif not published:
            r['why'] = 'no Diário Oficial date'
        elif alts:
            dts = sorted(d for n in alts for d in dates_in(n) if published < d <= today)
            if not dts:
                r['why'] = 'altered, no dated note'
            else:
                r['from'], r['altered'] = dts[-1], len(set(dts))
        elif not vig or 'data de sua publica' not in vig[-1] and 'data da publica' not in vig[-1]:
            r['why'] = 'takes effect otherwise than on publication: ' + (vig[-1][:60] if vig else 'no clause')
        else:
            r['from'] = published
        if 'why' not in r:
            r['published'] = published
            m = re.search(r'(?i)LEI COMPLEMENTAR\s+N[º°o.]*\s*[\d.]+,?\s+DE\s+(\d{1,2})[º°]?\s+(?:DE\s+)?([A-ZÇa-zç]+)\s+DE\s+(\d{4})',
                          r['text'][:200])
            r['enacted'] = (f'{int(m.group(3)):04d}-{MONTHS.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}'
                            if m and m.group(2).lower() in MONTHS else None)
            import datetime as dt
            if not r['enacted']:
                r['why'] = 'no date in its title'
            elif not 0 <= (dt.date.fromisoformat(published) - dt.date.fromisoformat(r['enacted'])).days <= 120:
                r['why'] = f'Diário Oficial date {published} does not fit the date in its title {r["enacted"]}'
            elif r['from'] > today:
                r['why'] = f'takes effect {r["from"]}, after retrieval'
    return recs


def lc_act(r):
    key = f'lc-{r["y"]}-{r["n"]:03d}'
    label = f'Lei Complementar nº {r["n"]}, de {r["y"]}'
    laws = {key: {'label': label, 'title': r['ementa'] or label, 'kind': 'law', 'enacted': r['enacted'],
                  'published': r['published'], 'url': r['pdf'], 'temporary_until': None, 'restores': None,
                  'note': None}}
    units = units_of(r['lines'], adt=False)
    altered = 'altered' in r
    v = {'from': r['from'], 'source_url': r['pdf'], 'sha256': sha(r['b']), 'units': units}
    if altered:
        v['note'] = (f'Text in force as compiled by the Assessoria Técnica of the Assembleia Legislativa do Pará; '
                     f'{label} was altered on {r["altered"]} date(s) its notes cite, the latest {r["from"]}.')
    else:
        v['note'] = f'As published in the Diário Oficial do Estado of {r["published"]}; in force on its publication.'
    em = r['ementa']
    act = {'slug': key, 'short': f'LC {r["n"]}/{r["y"]}',
           'title': label + (f' ({em})' if em and len(em) < 160 else ''), 'url': r['pdf'],
           'first_law': None if altered else key, 'earlier_laws': [key] if altered else [], 'versions': [v]}
    return act, laws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--part', type=int, default=0, help='write LC part n (1-based) of --part-size acts that are in')
    ap.add_argument('--part-size', type=int, default=10)
    a = ap.parse_args()
    if a.list or a.part:
        recs = lc_records(a.today)
        ok = [r for r in recs if 'why' not in r]
        if a.list:
            for r in recs:
                print(r['n'], r['y'], r.get('why', f'IN from {r.get("from")}' + (' (altered)' if 'altered' in r else '')))
            import collections
            print(len(ok), 'in of', len(recs), collections.Counter(r.get('why', 'in').split(':')[0].split(',')[0] for r in recs))
        for n in (range(1, (len(ok) + a.part_size - 1) // a.part_size + 1) if a.part == -1 else [a.part] if a.part else []):
            chunk = ok[(n - 1) * a.part_size:n * a.part_size]
            acts, laws = [], {}
            for r in chunk:
                act, l = lc_act(r)
                acts.append(act); laws.update(l)
            print(part(f'20-lc-{n:02d}', acts, laws, a.today, LC_DECISIONS), len(acts), 'acts',
                  [x['slug'] for x in acts][:3], '..')
        return
    if a.only in ('', 'constituicao'):
        act, laws, alter = constituicao(a.today)
        print('constituicao', len(act['versions'][0]['units']), 'units; latest alteration', alter[-1])
        print(part('10-constituicao', [act], laws, a.today))


if __name__ == '__main__':
    main()

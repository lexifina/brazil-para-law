"""Independent letters-and-digits check of a part against the source PDFs, read by a second engine (xpdf/poppler
pdftotext -raw), not by pymupdf, which parse.py uses.

    python -X utf8 check_letters.py [corpus.d/<part>.json ...]

Private. For each version: the PDF's sha256 equals the one recorded; then the PDF's whole text, reduced to letters and
digits, must be exactly the version's units (heading marks left out, in document order) interleaved with the lines
parse.py set aside (coloured notes and earlier wordings, "*" notes, "x" separators, the letterhead), each set-aside
stretch in its own order. Every letter and digit of the source must be accounted for, and every letter and digit of the record
found, in order.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse  # noqa: E402  (only for which lines it set aside)


def ld(s):
    return ''.join(ch for ch in s if ch.isalnum())


def second_reader(path):
    r = subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', str(path), '-'], capture_output=True)
    if r.returncode:
        raise SystemExit('pdftotext failed: ' + r.stderr.decode()[:200])
    return r.stdout.decode('utf-8', 'replace')


def run(S, j, T, t, cap=400):
    n = 0
    while n < cap and j + n < len(S) and t + n < len(T) and S[j + n] == T[t + n]:
        n += 1
    return n


def merge_check(S, U, A):
    """S must be U and A interleaved, each in order. At each character the side (record or set-aside) whose text runs
    on longer from here takes it. Set-aside text may be skipped forward (the two engines may order notes
    differently); record text never may."""
    i = j = k = 0
    gaps, in_a = 0, False
    while j < len(S):
        lu = run(S, j, U, i) if i < len(U) and S[j] == U[i] else 0
        la = run(S, j, A, k) if k < len(A) and S[j] == A[k] else 0
        if lu == 0 and la == 0:
            nk = A.find(S[j:j + 16], k)
            if nk < 0:
                return False, (f'mismatch at source {j}: {S[j - 30:j]!r}>{S[j:j + 60]!r} | record next {U[i:i + 60]!r} '
                               f'| set-aside next {A[k:k + 40]!r}')
            k = nk
            continue
        if lu >= la:
            i += 1; j += 1; in_a = False
        else:
            gaps += not in_a
            k += 1; j += 1; in_a = True
    if i != len(U):
        return False, f'record text left over: {U[i:i + 80]!r}'
    return True, f'{gaps} set-aside stretches'


def main(paths):
    bad = n = 0
    for p in paths:
        for a in json.load(open(p, encoding='utf-8'))['acts']:
            for v in a['versions']:
                path = HERE / '.cache' / 'raw' / hashlib.sha256(v['source_url'].encode()).hexdigest()
                b = path.read_bytes()
                assert hashlib.sha256(b).hexdigest() == v['sha256'], (a['slug'], 'sha256')
                S = ld(second_reader(path))
                U = ''.join(ld(re.sub(r'(?m)^#+ ', '', u['text'])) for u in v['units'].values())
                _, aside, _, _ = parse.read(b, split_inline=a['slug'] != 'constituicao')
                A = ''.join(ld(t) for t in aside)
                ok, msg = merge_check(S, U, A)
                n += 1
                bad += not ok
                print('OK  ' if ok else 'FAIL', a['slug'], v['from'], msg, f'(record {len(U)}, source {len(S)}, set aside {len(A)})')
    print(f'{n} versions checked, {bad} failing')
    return bad


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1:] or sorted(str(p) for p in (HERE / 'corpus.d').glob('*.json'))) else 0)

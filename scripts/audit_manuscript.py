"""Audit anonymous and author manuscript builds for pages, citations, identity, and overflow."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PDF_AUTHOR_MARKERS = [
    'Haoyi Zhang', 'Huaijin Ran', 'Xunzhu Tang',
    'hyeliozhang@gmail.com', 'huaijin003@e.ntu.edu.sg',
    'xunzhu.tang@uni.lu', 'realdanieltang@gmail.com',
]
ORCID_MARKERS = [
    '0009-0009-3693-786X', '0009-0009-2482-2344', '0000-0002-6377-0884',
]


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, errors='replace')


def inspect_pdf(root: Path, stem: str) -> dict:
    pdf = root / f'{stem}.pdf'
    log = (root / f'{stem}.log').read_text(errors='replace')
    info = command('pdfinfo', str(pdf))
    pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1))
    page_text = [command('pdftotext', '-f', str(i), '-l', str(i), '-layout', str(pdf), '-')
                 for i in range(1, pages + 1)]
    references = [i for i, text in enumerate(page_text, 1)
                  if re.search(r'\bReferences\b', text, re.I)]
    appendix = [i for i, text in enumerate(page_text, 1)
                if 'Executable Evidence and Additional Detail' in text]
    hboxes = re.findall(r'Overfull \\hbox \(([-0-9.]+)pt too wide\)', log)
    vboxes = re.findall(r'Overfull \\vbox \(([-0-9.]+)pt too high\)', log)
    undefined = re.findall(r'(?:Citation|Reference).*undefined|There were undefined references', log)
    fonts = command('pdffonts', str(pdf)).splitlines()[2:]
    unembedded = [line for line in fonts if line.split()[5:6] == ['no']]
    return {
        'pages': pages,
        'reference_start_pages': references,
        'appendix_start_pages': appendix,
        'overfull_hboxes_pt': [float(x) for x in hboxes],
        'overfull_vboxes_pt': [float(x) for x in vboxes],
        'undefined_warnings': len(undefined),
        'unembedded_fonts': len(unembedded),
        'text': '\n'.join(page_text),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper', type=Path, default=Path('../paper'))
    args = parser.parse_args()
    root = args.paper.resolve()
    required = ['review.pdf', 'review.tex', 'review.aux', 'review.log',
                'author.pdf', 'author.tex', 'author.aux', 'author.log',
                'manuscript.tex', 'authors.tex', 'references.bib']
    missing_files = [name for name in required if not (root / name).is_file()]
    if missing_files:
        raise FileNotFoundError(', '.join(str(root / name) for name in missing_files))

    bib = (root / 'references.bib').read_text()
    keys = re.findall(r'@\w+\s*\{\s*([^,\s]+)', bib)
    aux = (root / 'review.aux').read_text(errors='replace')
    cited = {key.strip() for group in re.findall(r'\\citation\{([^}]+)\}', aux)
             for key in group.split(',')}
    review = inspect_pdf(root, 'review')
    author = inspect_pdf(root, 'author')
    review_identity_hits = [marker for marker in PDF_AUTHOR_MARKERS + ORCID_MARKERS
                            if marker in review['text']]
    author_identity_missing = [marker for marker in PDF_AUTHOR_MARKERS if marker not in author['text']]
    authors_source = (root / 'authors.tex').read_text(errors='replace')
    author_orcid_source_missing = [marker for marker in ORCID_MARKERS if marker not in authors_source]

    report = {
        'review': {k: v for k, v in review.items() if k != 'text'},
        'author': {k: v for k, v in author.items() if k != 'text'},
        'bibliography_entries': len(keys),
        'distinct_entries': len(set(keys)),
        'cited_entries': len(cited),
        'missing_citations': sorted(cited - set(keys)),
        'unused_entries': sorted(set(keys) - cited),
        'review_identity_hits': review_identity_hits,
        'author_identity_missing': author_identity_missing,
        'author_orcid_source_missing': author_orcid_source_missing,
        'terminal_vbox_note': 'A 1.424pt terminal output-box warning from acmart is accepted only after rendered-page inspection; horizontal overflow is not accepted.',
    }
    ok = (
        review['pages'] <= 12
        and review['reference_start_pages'] == [9]
        and review['appendix_start_pages']
        and author['pages'] <= 12
        and author['reference_start_pages']
        and len(keys) == len(set(keys)) == len(cited) == 64
        and not report['missing_citations']
        and not report['unused_entries']
        and not review['overfull_hboxes_pt']
        and not author['overfull_hboxes_pt']
        and max(review['overfull_vboxes_pt'] or [0]) <= 1.5
        and max(author['overfull_vboxes_pt'] or [0]) <= 1.5
        and not review['undefined_warnings']
        and not author['undefined_warnings']
        and not review['unembedded_fonts']
        and not author['unembedded_fonts']
        and not review_identity_hits
        and not author_identity_missing
        and not author_orcid_source_missing
    )
    report['status'] = 'PASS' if ok else 'FAIL'
    (root / 'manuscript-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

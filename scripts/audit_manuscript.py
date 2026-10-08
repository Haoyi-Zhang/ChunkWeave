"""Check the companion anonymous manuscript with Poppler after compilation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess


def command(*argv: str) -> str:
    return subprocess.check_output(argv, text=True, encoding='utf-8', errors='replace')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper', type=Path, default=Path('../paper'))
    args = parser.parse_args()
    root = args.paper.resolve()
    for name in ('main.pdf', 'main.aux', 'main.log', 'references.bib'):
        if not (root / name).is_file():
            parser.error(f'Missing compiled manuscript input: {root / name}')
    pdf = root / 'main.pdf'
    info = command('pdfinfo', str(pdf))
    pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1))
    page_text = [command('pdftotext', '-f', str(i), '-l', str(i), '-layout', str(pdf), '-')
                 for i in range(1, pages + 1)]
    references = [i for i, text in enumerate(page_text, 1)
                  if re.search(r'(?m)^\s*REFERENCES\s*$|^\s*References\s*$', text)]
    log = (root / 'main.log').read_text(encoding='utf-8', errors='replace')
    keys = re.findall(r'@\w+\s*\{\s*([^,\s]+)', (root / 'references.bib').read_text(encoding='utf-8'))
    cited = {key.strip() for group in re.findall(r'\\citation\{([^}]+)\}',
              (root / 'main.aux').read_text(encoding='utf-8', errors='replace'))
              for key in group.split(',')}
    markers = ('Haoyi Zhang', 'Huaijin Ran', 'Xunzhu Tang',
               'hyeliozhang@gmail.com', 'huaijin003@e.ntu.edu.sg',
               'realdanieltang@gmail.com', 'github.com/Haoyi-Zhang')
    text = '\n'.join(page_text)
    report = {
        'pages': pages,
        'reference_start_pages': references,
        'missing_citations': sorted(cited - set(keys)),
        'duplicate_bib_keys': sorted({key for key in keys if keys.count(key) > 1}),
        'identity_hits': [marker for marker in markers if marker in text],
        'horizontal_overflow': re.findall(r'Overfull \\hbox[^\n]*', log),
        'undefined_references': re.findall(r'(?:Citation|Reference).*undefined|There were undefined references', log),
        'fonts': command('pdffonts', str(pdf)),
        'scope': 'Structural and typographic checks; scientific correctness and rendered-page inspection are separate.',
    }
    ok = (pages <= 12 and references == [9]
          and not any(report[key] for key in ('missing_citations', 'duplicate_bib_keys',
                     'identity_hits', 'horizontal_overflow', 'undefined_references')))
    report['status'] = 'PASS' if ok else 'FAIL'
    print(json.dumps(report, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

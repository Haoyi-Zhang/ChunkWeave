"""Whole-input reference. No calls to the incremental implementation or vendors.

Semantics: WHATWG HTML 9.2.5--9.2.6 and Encoding UTF-8 decode,
consulted 2026-10-03. Only terminated lines are processed. A UTF-8-valid
truncated final block is a separately labelled end-of-input profile.
"""
from __future__ import annotations
import re
from typing import TypedDict

MAX_BYTES = 65_536

class Event(TypedDict):
    type: str
    data: str
    id: str


def evaluate(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError(f'Fixture exceeds {MAX_BYTES} bytes')
    text = raw.decode('utf-8', errors='strict')
    if text.startswith('\ufeff'):
        text = text[1:]
    events: list[Event] = []
    data: list[str] = []
    kind = ''
    id_buffer = ''
    committed_id = ''
    retries: list[int] = []
    # Regex supplies whole terminated lines, with CRLF preferred over CR.
    for match in re.finditer(r'([^\r\n]*)(\r\n|\r|\n)', text):
        line = match.group(1)
        if line == '':
            committed_id = id_buffer
            if data:
                events.append({'type': kind or 'message', 'data': '\n'.join(data),
                               'id': committed_id})
            data = []
            kind = ''
        elif not line.startswith(':'):
            key, separator, value = line.partition(':')
            if not separator:
                value = ''
            elif value.startswith(' '):
                value = value[1:]
            if key == 'data':
                data.append(value)
            elif key == 'event':
                kind = value
            elif key == 'id' and '\x00' not in value:
                id_buffer = value
            elif key == 'retry' and re.fullmatch('[0-9]+', value):
                # Inputs use ordinary bounded retry values, never large integers.
                if len(value) > 6 or int(value) > 60_000:
                    raise ValueError('retry outside declared bounded profile')
                retries.append(int(value))
    return {'events': events, 'retries': retries, 'last_event_id': committed_id}


def slices(raw: bytes, cuts: list[int] | tuple[int, ...]) -> list[bytes]:
    if any(type(x) is not int for x in cuts) or list(cuts) != sorted(set(cuts)) or any(not 0 < x < len(raw) for x in cuts):
        raise ValueError('Cuts must be unique, increasing interior byte offsets')
    endpoints = (0, *cuts, len(raw))
    return [raw[a:b] for a, b in zip(endpoints, endpoints[1:])]

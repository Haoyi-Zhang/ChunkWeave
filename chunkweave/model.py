"""Separately authored scalar-at-a-time model; no regex, codecs, or oracle calls.

The UTF-8 decoder is deliberately strict because only valid bounded bytes enter
this experiment. It is not a general replacement/error-recovery implementation.
"""
from __future__ import annotations

class IncrementalModel:
    def __init__(self) -> None:
        self.need = 0
        self.code = 0
        self.low, self.high = 0x80, 0xBF
        self.first = True
        self.skip_lf = False
        self.line: list[str] = []
        self.data = ''
        self.kind = ''
        self.identifier = ''
        self.committed = ''
        self.events: list[dict] = []
        self.retries: list[int] = []
        self.characters = 0
        self.line_number = 0
        self.epoch = 0
        self.total_bytes = 0

    def feed(self, chunk: bytes) -> str:
        emitted: list[str] = []
        self.total_bytes += len(chunk)
        if self.total_bytes > 65_536:
            raise ValueError('bounded input limit')
        for b in chunk:
            if self.need:
                if not self.low <= b <= self.high:
                    raise UnicodeError('invalid UTF-8 continuation')
                self.code = (self.code << 6) | (b & 0x3F)
                self.need -= 1
                self.low, self.high = 0x80, 0xBF
                if self.need:
                    continue
                char = chr(self.code)
            elif b < 0x80:
                char = chr(b)
            elif 0xC2 <= b <= 0xDF:
                self.need, self.code = 1, b & 0x1F
                continue
            elif 0xE0 <= b <= 0xEF:
                self.need, self.code = 2, b & 0x0F
                self.low = 0xA0 if b == 0xE0 else 0x80
                self.high = 0x9F if b == 0xED else 0xBF
                continue
            elif 0xF0 <= b <= 0xF4:
                self.need, self.code = 3, b & 0x07
                self.low = 0x90 if b == 0xF0 else 0x80
                self.high = 0x8F if b == 0xF4 else 0xBF
                continue
            else:
                raise UnicodeError('invalid UTF-8 lead')
            if self.first:
                self.first = False
                if char == '\ufeff':
                    continue
            self.characters += 1
            emitted.append(char)
            self.consume_char(char)
        return ''.join(emitted)

    def consume_char(self, char: str) -> None:
        if self.skip_lf:
            self.skip_lf = False
            if char == '\n':
                return
        if char == '\r' or char == '\n':
            line = ''.join(self.line)
            self.line.clear()
            self.consume_line(line)
            self.line_number += 1
            self.skip_lf = char == '\r'
        else:
            self.line.append(char)

    def consume_line(self, line: str) -> None:
        if not line:
            self.committed = self.identifier
            if self.data:
                self.events.append({'type': self.kind or 'message',
                                    'data': self.data[:-1], 'id': self.committed})
            self.data = ''
            self.kind = ''
            self.epoch += 1
            return
        if line[0] == ':':
            return
        p = line.find(':')
        key, value = (line, '') if p < 0 else (line[:p], line[p + 1:])
        if value[:1] == ' ':
            value = value[1:]
        if key == 'data':
            self.data += value + '\n'
        elif key == 'event':
            self.kind = value
        elif key == 'id':
            if not any(ord(c) == 0 for c in value):
                self.identifier = value
        elif key == 'retry' and value and all('0' <= c <= '9' for c in value):
            if len(value) > 6:
                raise ValueError('retry outside bounded profile')
            value_as_int = 0
            for digit in value:
                value_as_int = value_as_int * 10 + ord(digit) - 48
                if value_as_int > 60_000:
                    raise ValueError('retry outside bounded profile')
            self.retries.append(value_as_int)

    def finish(self) -> dict:
        if self.need:
            raise UnicodeError('incomplete UTF-8 scalar at EOF')
        # No final line dispatch and no invented blank separator.
        return {'events': self.events, 'retries': self.retries,
                'last_event_id': self.committed}

    def boundary_state(self) -> tuple:
        line = ''.join(self.line)
        if not line:
            phase = 'empty'
        elif line.startswith(':'):
            phase = 'comment'
        elif ':' in line:
            field, value = line.split(':', 1)
            phase = ('value-' + field) if field in ('data', 'event', 'id', 'retry') else 'other'
            if value in ('', ' '):
                phase += '-start'
        elif any(key.startswith(line) for key in ('data', 'event', 'id', 'retry')):
            phase = 'field-prefix'
        else:
            phase = 'other'
        return (self.need, int(self.skip_lf), phase, bool(self.data),
                bool(self.kind), bool(self.identifier))

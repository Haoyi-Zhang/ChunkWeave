"""Bounded-state projection of the correct SSE model for boundary landmarks.

Only callback existence, the first six decoded characters of the current line,
and UTF-8 residual length are retained. No event data or prior events are stored.
This is a reference projection, not a parser that delivers application events.
"""
from __future__ import annotations

class LandmarkProjection:
    __slots__=('need','value','minimum','first','skip_lf','prefix','nonempty',
               'field_name','colon','value_start','digits','digits_ok',
               'has_data','events','retries')
    def __init__(self):
        self.need=0;self.value=0;self.minimum=0;self.first=True;self.skip_lf=False
        self.prefix='';self.nonempty=False;self.field_name='';self.colon=False
        self.value_start=True;self.digits=False;self.digits_ok=True
        self.has_data=False;self.events=0;self.retries=0
    def _end_line(self):
        if not self.nonempty:
            if self.has_data:self.events+=1
            self.has_data=False
        elif self.field_name=='data':self.has_data=True
        elif self.field_name=='retry' and self.digits and self.digits_ok:
            self.retries+=1
        self.prefix='';self.nonempty=False;self.field_name='';self.colon=False
        self.value_start=True;self.digits=False;self.digits_ok=True
    def _char(self,ch:str):
        if self.first:
            self.first=False
            if ch=='\ufeff':return
        if self.skip_lf:
            self.skip_lf=False
            if ch=='\n':return
        if ch in ('\r','\n'):
            self._end_line();self.skip_lf=ch=='\r';return
        self.nonempty=True
        if len(self.prefix)<6:self.prefix+=ch
        if not self.colon:
            if ch==':':self.colon=True
            elif len(self.field_name)<6:self.field_name+=ch
            # A name of >=6 chars cannot equal data/event/id/retry. Preserve the
            # six-char nonmatching sentinel rather than its unbounded suffix.
            return
        if self.value_start:
            self.value_start=False
            if ch==' ':return
        if self.field_name=='retry':
            self.digits=True
            if not '0'<=ch<='9':self.digits_ok=False
    def feed_byte(self,b:int):
        if not 0<=b<=255:raise ValueError('byte outside range')
        if self.need:
            if not 0x80<=b<=0xBF:raise ValueError('invalid UTF-8 continuation')
            self.value=(self.value<<6)|(b&63);self.need-=1
            if self.need:return
            cp=self.value
            if cp<self.minimum or cp>0x10FFFF or 0xD800<=cp<=0xDFFF:
                raise ValueError('invalid UTF-8 scalar')
            self._char(chr(cp));return
        if b<128:self._char(chr(b))
        elif 0xC2<=b<=0xDF:self.need=1;self.value=b&31;self.minimum=0x80
        elif 0xE0<=b<=0xEF:self.need=2;self.value=b&15;self.minimum=0x800
        elif 0xF0<=b<=0xF4:self.need=3;self.value=b&7;self.minimum=0x10000
        else:raise ValueError('invalid UTF-8 leading byte')
    def finish(self):
        if self.need:raise ValueError('truncated UTF-8 scalar')
        # EOF does not supply a missing line terminator or event separator.

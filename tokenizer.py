#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Optional
from token_types import *
from errors import TokenizerError

ESCAPES         = {"n":"\n","t":"\t","r":"\r","\"":"\"","'":"'","\\":"\\","a":"\a","b":"\b","f":"\f","v":"\v","0":"\0"}
KEYWORDS        = {"proc", "func", "struct",
                   "if","else", "elseif", "then", "endif", "end", 
                   "for", "to", "step", "next",
                   "while", "repeat", "until",
                   "switch", "case", "default",
                   "return", "break", "continue", "stop",                    
                   "asm"}
PREPROC         = {".module", ".include", ".define", ".undef", ".ifdef", ".ifndef", ".else", ".endif",
                   ".segment", ".incbin"}
TYPES           = {"byte", "word"}
TYPEMOD         = {"const", "static", "port"}
SINGLE_OPS      = set("+-*/%><[]&|~^!")
TWO_CHAR_OPS    = {"==","!=","<=",">=","&&","||","<<",">>"}
DELIMIN         = {","}
PTR             = set()
SQB             = {"[","]"}

@dataclass
class Token:
    type: str = ""
    value: str = ""
    line: int = 0
    col: int = 0
    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class Tokenizer:
    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.line = 1
        self.col = 1
        self.pline = 1
        self.pcol = 1
        self.sline = 1
        self.scol = 1
        self.length = len(src)
        self.tokenList: list[Token] = []

    def _getTokens(self):
        return self.tokenList

    def _peek(self, offset=0) -> Optional[str]:
        i = self.pos + offset
        if i < self.length:
            return self.src[i]
        return None

    def _advance(self, n=1) -> Optional[str]:
        ch = None
        for _ in range(n):
            self.pline = self.line
            self.pcol = self.col
            if self.pos < self.length:
                ch = self.src[self.pos]
            self.pos += 1
            if self.pos > self.length:
                return None
            if ch == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        if self.pos < self.length:
            return self.src[self.pos]
        return None

    def _process_escape_sequence(self):
        """Process escape sequence and return the character.
        
        Supported escape sequences:
        - \\n, \\t, \\r, \\a, \\f, \\v - standard control chars
        - \\0 - null byte
        - \\" - double quote
        - \\' - single quote
        - \\\\ - backslash
        - \\xHH - hex byte (e.g., \\xFF)
        - \\OOO - octal byte (e.g., \\377 for 255)
        - \\bBBBBBBBB - binary byte (e.g., \\b11111111 for 255)
        
        NOTE: Binary \\b prefix is checked BEFORE \\b backspace escape to allow binary literals
        """
        esc = self._peek()
        if esc is None:
            raise TokenizerError("Unexpected EOF in escape sequence", line=self.line, col=self.col)
        
        # Binary escape: \bBBBBBBBB (1-8 binary digits) - CHECK BEFORE ESCAPES to avoid conflict with \b backspace
        if esc == 'b' and self._peek(1) in ('0', '1'):
            self._advance(1)
            binary_digits = ""
            for _ in range(8):
                c = self._peek()
                if c and c in "01":
                    binary_digits += c
                    self._advance(1)
                else:
                    break
            if not binary_digits:
                raise TokenizerError("Expected binary digit after \\b", line=self.line, col=self.col)
            value = int(binary_digits, 2)
            if value > 255:
                raise TokenizerError(f"Binary escape out of range (0-255): \\b{binary_digits}", line=self.line, col=self.col)
            return chr(value)
        
        # Standard single-character escapes
        if esc in ESCAPES:
            self._advance(1)
            return ESCAPES[esc]
        
        # Hex escape: \xHH (1-2 hex digits)
        if esc == 'x':
            self._advance(1)
            hex_digits = ""
            for _ in range(2):
                c = self._peek()
                if c and c in "0123456789abcdefABCDEF":
                    hex_digits += c
                    self._advance(1)
                else:
                    break
            if not hex_digits:
                raise TokenizerError("Expected hex digit after \\x", line=self.line, col=self.col)
            value = int(hex_digits, 16)
            if value > 255:
                raise TokenizerError(f"Hex escape out of range (0-255): \\x{hex_digits}", line=self.line, col=self.col)
            return chr(value)
        
        # Octal escape: \OOO (1-3 octal digits)
        if esc in "01234567":
            octal_digits = ""
            for _ in range(3):
                c = self._peek()
                if c and c in "01234567":
                    octal_digits += c
                    self._advance(1)
                else:
                    break
            value = int(octal_digits, 8)
            if value > 255:
                raise TokenizerError(f"Octal escape out of range (0-377): \\{octal_digits}", line=self.line, col=self.col)
            return chr(value)
        
        raise TokenizerError(f"Unknown escape sequence: \\{esc}", line=self.line, col=self.col)

    def _emit(self, ttype: str, start_line: int, start_col: int, value: Optional[str] = None):
        if value is None:
            value = ""
        # Keep strings case-sensitive, but uppercase identifiers, keywords and types
        if ttype in (TOK_STRING, TOK_ASM_BLOCK):
            t1 = Token(ttype, value, start_line, start_col)
        else:
            t1 = Token(ttype, value.upper(), start_line, start_col)
        self.tokenList.append(t1)

    def _consume_asm_block(self):
        start_line = self.line
        start_col = self.col
        block_parts: list[str] = []
        while True:
            if self._peek() is None:
                raise TokenizerError("Missing END for ASM block", line=start_line, col=start_col)
            line_start = self.pos
            while self._peek() not in (None, "\n"):
                self._advance()
            line_text = self.src[line_start:self.pos]
            stripped = line_text.strip().upper()
            if stripped == "END":
                if self._peek() == "\n":
                    self._advance()
                break
            block_parts.append(line_text)
            if self._peek() == "\n":
                block_parts.append("\n")
                self._advance()
        self._emit(TOK_ASM_BLOCK, start_line, start_col, "".join(block_parts))

    def tokenize(self):
        self.pos = 0
        self.line = 1
        self.col = 1
        self.sline = 1
        self.scol = 1
        self.pline = 1
        self.pcol = 1

        while True:
            ch = self._peek(0)
            if ch is None:
                self._emit(TOK_EOF, self.pline, self.pcol, "")
                return

            if ch.isspace():
                self._advance()
                continue

            self.sline = self.line
            self.scol = self.col

            # Single-line comment
            if ch == ';':
                self._advance(1)
                while self._peek() not in (None, '\n'):
                    self._advance()
                continue

            # Block comment /* ... */
            if ch == '/' and self._peek(1) == '*':
                self._advance(2)
                while True:
                    if self._peek() is None:
                        raise TokenizerError("Missing */ at EOF", line=self.sline, col=self.scol)
                    if self._peek() == '*' and self._peek(1) == '/':
                        self._advance(2)
                        if self._peek() == '\n':
                            self._advance(1)
                        break
                    self._advance(1)
                continue

            # String literal
            if ch == '"':
                self._advance(1)
                buf: list[str] = []
                while True:
                    c = self._peek()
                    if c is None:
                        raise TokenizerError("Missing end of string", line=self.sline, col=self.scol)
                    if c == '\\':
                        self._advance(1)
                        escaped_char = self._process_escape_sequence()
                        buf.append(escaped_char)
                        continue
                    if c == '"':
                        self._advance(1)
                        break
                    buf.append(c)
                    self._advance(1)
                self._emit(TOK_STRING, self.sline, self.scol, "".join(buf))
                continue

            # $<hex>
            if ch == '$':
                self._advance(1)
                startp = self.pos
                while True:
                    c = self._peek()
                    if c is None or not (c.isdigit() or c.lower() in "abcdef"):
                        break
                    self._advance(1)
                if startp == self.pos:
                    raise TokenizerError("Hexadecimal digit expected", line=self.sline, col=self.scol)
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0x" + text)
                continue

            # %<binary>
            if ch == '%' and self._peek(1) in ('0', '1'):
                self._advance(1)
                startp = self.pos
                while True:
                    c = self._peek()
                    if c is None or c not in '01':
                        break
                    self._advance(1)
                if startp == self.pos:
                    raise TokenizerError("Binary digit expected", line=self.sline, col=self.scol)
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0b" + text)
                continue

            # 0x / 0X
            if ch == '0' and (self._peek(1) in ('x', 'X')):
                startp = self.pos
                ch2 = self._advance(2)
                if ch2 is None or not (ch2.isdigit() or ch2.lower() in 'abcdef'):
                    raise TokenizerError("Hexadecimal digit expected", line=self.sline, col=self.scol)
                while True:
                    c = self._peek()
                    if c is None or not (c.isdigit() or c.lower() in 'abcdef'):
                        break
                    self._advance(1)
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # 0b / 0B
            if ch == '0' and (self._peek(1) in ('b', 'B')):
                startp = self.pos
                ch2 = self._advance(2)
                if ch2 is None or ch2 not in ('0', '1'):
                    raise TokenizerError("Binary digit expected", line=self.sline, col=self.scol)
                while True:
                    c = self._peek()
                    if c is None or c not in ('0', '1'):
                        break
                    self._advance(1)
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # ASCII character literal 'x'
            if ch == '\'':
                self._advance(1)
                c = self._peek()
                if c is None:
                    raise TokenizerError("Unexpected EOF in character literal", line=self.sline, col=self.scol)
                if c == '\\':
                    self._advance(1)
                    escaped_char = self._process_escape_sequence()
                    char_val = ord(escaped_char)
                else:
                    char_val = ord(c)
                    self._advance(1)
                if self._peek() != '\'':
                    raise TokenizerError("Expected closing quote in character literal", line=self.line, col=self.col)
                self._advance(1)
                self._emit(TOK_NUMBER, self.sline, self.scol, str(char_val))
                continue

            # '=' and '=='
            if ch == '=':
                ch2 = self._peek(1)
                if ch2 == '=':
                    self._emit(TOK_OP, self.sline, self.scol, '==')
                    self._advance(2)
                else:
                    self._emit(TOK_EQU, self.sline, self.scol, '')
                    self._advance(1)
                continue

            # decimal number
            if ch.isdigit():
                start = self.pos
                while True:
                    c = self._peek()
                    if c is None or not c.isdigit():
                        break
                    self._advance(1)
                text = self.src[start:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # leading underscore is invalid
            if ch == '_':
                raise TokenizerError("'_' is not allowed as first character", line=self.sline, col=self.scol)

            # Handle preprocessor directives (like .segment, .ifdef)
            if ch == '.' and self._peek() and self._peek().isalpha():
                start = self.pos
                self._advance(1)
                while True:
                    c = self._peek()
                    if c is None or not (c.isdigit() or c.isalpha() or c == '_') or c.isspace():
                        break
                    self._advance(1)
                text = self.src[start:self.pos]
                if text.lower() in PREPROC:
                    self._emit(TOK_PREPROC, self.sline, self.scol, text.upper())
                    continue
                # If it wasn't a recognized preproc directive, treat . as an operator
                # Back up and fall through to operator handling
                self.pos -= len(text) - 1  # Back up to just after the '.'
                # Fall through to single char op handling below
                # This won't work, so we need a different approach
                # For now, emit . as an OP token
                self._emit(TOK_OP, self.sline, self.scol, '.')
                self._advance(1)
                continue

            # identifiers, keywords, types (no longer accepts leading .)
            if ch.isalpha():
                start = self.pos
                self._advance(1)
                while True:
                    c = self._peek()
                    if c is None or not (c.isdigit() or c.isalpha() or c == '_') or c.isspace():
                        break
                    self._advance(1)
                text = self.src[start:self.pos]
                if text.lower() in TYPES:
                    self._emit(TOK_TYPE, self.sline, self.scol, text.upper())
                    continue
                if text.lower() in TYPEMOD:
                    self._emit(TOK_TYPEMOD, self.sline, self.scol, text.upper())
                    continue
                if text.lower() in KEYWORDS:
                    self._emit(TOK_KEYWORD, self.sline, self.scol, text.upper())
                    if text.lower() == 'asm':
                        self._consume_asm_block()
                    continue
                self._emit(TOK_IDENT, self.sline, self.scol, text)
                continue

            # two-char ops
            c1 = ch
            c2 = self._peek(1) or ''
            di = (c1 or '') + (c2 or '')
            if di in TWO_CHAR_OPS:
                self._emit(TOK_OP, self.sline, self.scol, di)
                self._advance(2)
                continue

            # single-char ops and punctuation
            if ch in SINGLE_OPS:
                self._emit(TOK_OP, self.sline, self.scol, ch)
                self._advance(1)
                continue

            if ch == '{':
                self._advance(1)
                self._emit(TOK_LCURLY, self.sline, self.scol, ch)
                continue

            if ch == '}':
                self._advance(1)
                self._emit(TOK_RCURLY, self.sline, self.scol, ch)
                continue

            if ch in DELIMIN:
                self._emit(TOK_DELIM, self.sline, self.scol, ch)
                self._advance(1)
                continue

            if ch in PTR:
                self._advance(1)
                self._emit(TOK_PTR, self.sline, self.scol, ch)
                continue

            if ch in SQB:
                self._advance(1)
                self._emit(TOK_SQB, self.sline, self.scol, ch)
                continue

            if ch == '(':
                self._advance(1)
                self._emit(TOK_LBRACE, self.sline, self.scol, ch)
                continue

            if ch == ')':
                self._advance(1)
                self._emit(TOK_RBRACE, self.sline, self.scol, ch)
                continue

            if ch == '@':
                self._advance(1)
                self._emit(TOK_AT, self.sline, self.scol, ch)
                continue

            if ch == '.':
                self._advance(1)
                self._emit(TOK_OP, self.sline, self.scol, ch)
                continue

            # Unknown char: skip
            self._advance(1)
        return
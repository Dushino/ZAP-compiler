#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Optional
from token_types import *
from errors import TokenizerError

ESCAPES: dict[str, str]         = {"n":"\n","t":"\t","r":"\r","\"":"\"","'":"'","\\":"\\","a":"\a","b":"\b","f":"\f","v":"\v","0":"\0"}
KEYWORDS: set[str]        = {"proc", "func", "struct", "enum",
                   "if","else", "elseif", "end", 
                   "for", "to", "step",
                   "while", "repeat", "until",
                   "switch", "case", "default",
                   "return", "break", "continue",                    
                   "asm"}
PREPROC: set[str]         = {".module", ".include", ".define", ".undef", ".ifdef", ".ifndef", ".else", ".endif",
                   ".error", ".warning", ".info"}
TYPES: set[str]           = {"byte", "word"}
TYPEMOD: set[str]         = {"const", "static"}
SINGLE_OPS: set[str]      = set("+-*/%><[]&|~^!")
TWO_CHAR_OPS: set[str]    = {"==","!=","<=",">=","&&","||","<<",">>"}
DELIMIN: set[str]         = {","}
PTR             = set()
SQB: set[str]             = {"[","]"}

@dataclass
class Token:
    """Simple token container with source position."""
    type: str = ""
    value: str = ""
    line: int = 0
    col: int = 0
    def __repr__(self) -> str:
        """Return a concise debug representation of the token."""
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class Tokenizer:
    def __init__(self, src: str) -> None:
        """Initialize tokenizer state for the given source text."""
        self.src: str = src
        self.pos = 0
        self.line = 1
        self.col = 1
        self.pline = 1
        self.pcol = 1
        self.sline = 1
        self.scol = 1
        self.length: int = len(src)
        self.tokenList: list[Token] = []

    def _getTokens(self) -> list[Token]:
        """Return the collected tokens after tokenization."""
        return self.tokenList

    def _peek(self, offset=0) -> Optional[str]:
        """Peek ahead in the source without consuming characters."""
        i: int = self.pos + offset
        if i < self.length:
            return self.src[i]
        return None

    def _advance(self, n=1) -> Optional[str]:
        """Advance the cursor by n characters while tracking line/column."""
        ch: str | None = None
        for _ in range(n):
            self.pline: int = self.line
            self.pcol: int = self.col
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

    def _process_escape_sequence(self) -> str:
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
        esc: str | None = self._peek()
        if esc is None:
            raise TokenizerError("Unexpected EOF in escape sequence", line=self.line, col=self.col)
        
        # Binary escape: \bBBBBBBBB (1-8 binary digits) - CHECK BEFORE ESCAPES to avoid conflict with \b backspace
        if esc == 'b' and self._peek(1) in ('0', '1'):
            self._advance(1)
            binary_digits: str = ""
            for _ in range(8):
                c: str | None = self._peek()
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
            hex_digits: str = ""
            for _ in range(2):
                c: str | None = self._peek()
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
            octal_digits: str = ""
            for _ in range(3):
                c: str | None = self._peek()
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

    def _emit(self, ttype: str, start_line: int, start_col: int, value: Optional[str] = None) -> None:
        """Create and append a token with normalized casing rules."""
        if value is None:
            value = ""
        # Keep strings case-sensitive, but uppercase identifiers, keywords and types
        if ttype in (TOK_STRING, TOK_ASM_BLOCK):
            t1 = Token(ttype, value, start_line, start_col)
        else:
            t1 = Token(ttype, value.upper(), start_line, start_col)
        self.tokenList.append(t1)

    def _consume_asm_block(self) -> None:
        """Read an inline ASM block until the matching END line."""
        start_line: int = self.line
        start_col: int = self.col
        block_parts: list[str] = []
        while True:
            if self._peek() is None:
                raise TokenizerError("Missing END for ASM block", line=start_line, col=start_col)
            line_start: int = self.pos
            while self._peek() not in (None, "\n"):
                self._advance()
            line_text: str = self.src[line_start:self.pos]
            stripped: str = line_text.strip().upper()
            if stripped == "END":
                if self._peek() == "\n":
                    self._advance()
                break
            block_parts.append(line_text)
            if self._peek() == "\n":
                block_parts.append("\n")
                self._advance()
        self._emit(TOK_ASM_BLOCK, start_line, start_col, "".join(block_parts))

    def tokenize(self) -> None:
        """Tokenize the entire source into a list of tokens."""
        self.pos = 0
        self.line = 1
        self.col = 1
        self.sline = 1
        self.scol = 1
        self.pline = 1
        self.pcol = 1

        while True:
            ch: str | None = self._peek(0)
            if ch is None:
                self._emit(TOK_EOF, self.pline, self.pcol, "")
                return

            if ch.isspace():
                self._advance()
                continue

            self.sline: int = self.line
            self.scol: int = self.col

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
                    c: str | None = self._peek()
                    if c is None:
                        raise TokenizerError("Missing end of string", line=self.sline, col=self.scol)
                    if c == '\\':
                        self._advance(1)
                        escaped_char: str = self._process_escape_sequence()
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
                startp: int = self.pos
                while True:
                    c: str | None = self._peek()
                    if c is None or not (c.isdigit() or c.lower() in "abcdef"):
                        break
                    self._advance(1)
                if startp == self.pos:
                    raise TokenizerError("Hexadecimal digit expected", line=self.sline, col=self.scol)
                text: str = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0x" + text)
                continue

            # %<binary>
            if ch == '%' and self._peek(1) in ('0', '1'):
                self._advance(1)
                startp: int = self.pos
                while True:
                    c: str | None = self._peek()
                    if c is None or c not in '01':
                        break
                    self._advance(1)
                if startp == self.pos:
                    raise TokenizerError("Binary digit expected", line=self.sline, col=self.scol)
                text: str = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0b" + text)
                continue

            # 0x / 0X
            if ch == '0' and (self._peek(1) in ('x', 'X')):
                startp: int = self.pos
                ch2: str | None = self._advance(2)
                if ch2 is None or not (ch2.isdigit() or ch2.lower() in 'abcdef'):
                    raise TokenizerError("Hexadecimal digit expected", line=self.sline, col=self.scol)
                while True:
                    c: str | None = self._peek()
                    if c is None or not (c.isdigit() or c.lower() in 'abcdef'):
                        break
                    self._advance(1)
                text: str = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # 0b / 0B
            if ch == '0' and (self._peek(1) in ('b', 'B')):
                startp: int = self.pos
                ch2: str | None = self._advance(2)
                if ch2 is None or ch2 not in ('0', '1'):
                    raise TokenizerError("Binary digit expected", line=self.sline, col=self.scol)
                while True:
                    c: str | None = self._peek()
                    if c is None or c not in ('0', '1'):
                        break
                    self._advance(1)
                text: str = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # ASCII character literal 'x'
            if ch == '\'':
                self._advance(1)
                c: str | None = self._peek()
                if c is None:
                    raise TokenizerError("Unexpected EOF in character literal", line=self.sline, col=self.scol)
                if c == '\\':
                    self._advance(1)
                    escaped_char: str = self._process_escape_sequence()
                    char_val: int = ord(escaped_char)
                else:
                    char_val: int = ord(c)
                    self._advance(1)
                if self._peek() != '\'':
                    raise TokenizerError("Expected closing quote in character literal", line=self.line, col=self.col)
                self._advance(1)
                self._emit(TOK_NUMBER, self.sline, self.scol, str(char_val))
                continue

            # '=' and '=='
            if ch == '=':
                ch2: str | None = self._peek(1)
                if ch2 == '=':
                    self._emit(TOK_OP, self.sline, self.scol, '==')
                    self._advance(2)
                else:
                    self._emit(TOK_EQU, self.sline, self.scol, '')
                    self._advance(1)
                continue

            # decimal number
            if ch.isdigit():
                start: int = self.pos
                while True:
                    c: str | None = self._peek()
                    if c is None or not c.isdigit():
                        break
                    self._advance(1)
                text: str = self.src[start:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            # leading underscore is invalid
            if ch == '_':
                raise TokenizerError("'_' is not allowed as first character", line=self.sline, col=self.scol)

            # Handle preprocessor directives (like .segment, .ifdef)
            next_ch: str | None = self._peek()
            if ch == '.' and next_ch is not None and next_ch.isalpha():
                start: int = self.pos
                self._advance(1)
                while True:
                    c: str | None = self._peek()
                    if c is None or not (c.isdigit() or c.isalpha() or c == '_') or c.isspace():
                        break
                    self._advance(1)
                text: str = self.src[start:self.pos]
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
                start: int = self.pos
                self._advance(1)
                while True:
                    c: str | None = self._peek()
                    if c is None or not (c.isdigit() or c.isalpha() or c == '_') or c.isspace():
                        break
                    self._advance(1)
                text: str = self.src[start:self.pos]
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

            # Declaration modifiers like #KEEP, #NOEXPORT, #EXPORT
            if ch == '#':
                self._advance(1)
                start: int = self.pos
                nxt: str | None = self._peek()
                if nxt is None or not nxt.isalpha():
                    raise TokenizerError("Expected identifier after '#'", line=self.sline, col=self.scol)
                while True:
                    c: str | None = self._peek()
                    if c is None or not (c.isalpha() or c.isdigit() or c == '_'):
                        break
                    self._advance(1)
                text: str = self.src[start:self.pos]
                # emit as DECLMOD so parser can recognize modifiers attached to PROC/FUNC
                self._emit(TOK_DECLMOD, self.sline, self.scol, text.upper())
                continue

            # two-char ops
            c1: str = ch
            c2: str = self._peek(1) or ''
            di: str = (c1 or '') + (c2 or '')
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

            # Unknown char: report error
            raise TokenizerError(f"Unknown character: {ch}", line=self.sline, col=self.scol)
        return
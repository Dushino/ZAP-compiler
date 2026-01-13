#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Generator, Optional
from token_types import *

# .DEFINE <ident>=<str const>{,<ident>=<str const>}
# .INCLUDE "D1:IOSTUFF.ACT"
# .MODULE adds all its global variables as global to whole project


# <type> POINTER <ident>{=<addr>}|:,<ident>{=<addr>}:|
# <type modifier> <type> <var init>|:,<var init>:|
# TYPE <ident>=[<var decls>]



# must be in lowercase
ESCAPES         = {"n":"\n","t":"\t","r":"\r","\"":"\"","'":"'","\\":"\\"}
KEYWORDS        = {"proc", "func", 
                   "if","else", "elseif", "then", "endif", "end", 
                   "for", "to", "step", "next",
                   "while", "repeat", "until",
                   "switch", "case", "default",
                   "return", "break", "continue", "stop",                    
                   "asm"}
PREPROC         = {".module", ".include", ".define", ".undef", ".ifdef", ".ifndef", ".else", ".endif",
                   ".segment"}
TYPES           = {"byte", "word"}
TYPEMOD         = {"const", "struct"}
SINGLE_OPS      = set("+-*/%><[]&")
TWO_CHAR_OPS    = {"==","!=","<=",">=","&&","||"}
DELIMIN         = {","}
PTR             = {"^"}
SQB             = {"[","]"}



# ---------------------------------------------------------------------------------
@dataclass
class Token:
    type: str       = ""
    value: str      = ""
    line: int       = 0
    col: int        = 0
    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class TokenizerError(Exception):
    pass


class Tokenizer:
    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.line = 1           # current line
        self.col = 1            # current column
        self.pline = 1           # previous line
        self.pcol = 1            # previous column
        self.sline = 1          # token starting line
        self.scol = 1           # token starting column
        self.length = len(src)
        self.tokenList = list()

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
            # Check the character we're leaving (current position)
            if self.pos < self.length:
                ch = self.src[self.pos]
            self.pos += 1
            if self.pos > self.length:
                return None
            # Update line/col based on the character we just passed
            if ch == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            #print(f'Advanced to {self.pos} ({ch}) from {self.pline},{self.pcol} to {self.line},{self.col}')
        # Return the character at the new position (for compatibility)
        if self.pos < self.length:
            return self.src[self.pos]
        return None

    def _emit(self, ttype: str, start_line: int, start_col: int, value: Optional[str] = None): # -> Token:
        if value is None:
            value = ""
        # add token value as uppercase if not string or asm block   
        if ttype in (TOK_STRING, TOK_ASM_BLOCK):
            t1 = Token(ttype, value, start_line, start_col)
        else:
            t1 = Token(ttype, value.upper(), start_line, start_col)    
        self.tokenList.append(t1)
        return 

    def _consume_asm_block(self):
        start_line = self.line
        start_col = self.col

        block_parts = []
        while True:
            if self._peek() is None:
                raise TokenizerError("Missing END for ASM block")

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
        
        cnt = 0
        while True:
            ch = self._peek(0)
            #print(f'ch = {ch}')
            if ch is None:
                # print("--- EOF")
                self._emit(TOK_EOF, self.pline, self.pcol, "")    
                return

            # Skip whitespace
            if ch.isspace():
                self._advance()
                continue

            # START TOKEN
            self.sline = self.line
            self.scol  = self.col

            # Comment till EOL
            if ch == ';':
                self._advance(1)
                start = self.pos
                while self._peek() not in (None, '\n'):
                    self._advance()
                text = self.src[start:self.pos]
                continue
            
            # block comment
            if ch == '/' and self._peek(1) == '*':
                self._advance(2)
                start = self.pos
                cycle = True
                while cycle:
                    if self._peek() is None:
                        # unterminated
                        text = self.src[start:self.pos]
                        print("Missing */ at EOF")
                        exit (1)
                    if self._peek() == '*' and self._peek(1) == '/':
                        text = self.src[start:self.pos]
                        self._advance(2)  # consume */
                        self._advance(1)     
                        cycle = False
                        continue
                    self._advance()
                continue

            if ch == '\"':            
                quote = ch
                ch = self._advance()  # consume opening quote
                if ch is None:
                    raise TokenizerError (f'Premature EOF at {self.sline},{self.scol}')
                start = self.pos
                buf = []
                while True:
                    c = self._peek()
                    if c is None:
                        raise TokenizerError (f'Missing end of string - start at {self.sline},{self.scol}')                
                    if c == '\\':
                        self._advance()
                        esc = self._peek()
                        if esc is None:
                            raise TokenizerError("Unexpected EOF in escape sequence")
                        if esc in ESCAPES:
                            buf.append(ESCAPES[esc])
                        else:
                            raise TokenizerError(f"Unknown escape sequence: \\{esc}")
                        self._advance()
                        continue
                    if c == quote:
                        self._advance()  # consume closing quote
                        break
                    buf.append(c)
                    self._advance()
                self._emit(TOK_STRING, self.sline, self.scol, "".join(buf))    
                print(f'Got string {"".join(buf)}')
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
                    raise TokenizerError("Hexadecimal digit expected")
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0x" + text)
                continue

            # %<binary> - only if followed by 0 or 1
            if ch == '%' and self._peek(1) in ('0', '1'):
                self._advance(1)
                startp = self.pos
                while True:
                    c = self._peek()
                    if c is None or c not in '01':
                        break
                    self._advance(1)
                if startp == self.pos:
                    raise TokenizerError("Binary digit expected")
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, "0b" + text)
                continue

            # 0x / 0X = HEX
            if ch == '0' and (self._peek(1) in ('x','X')):
                startp = self.pos
                ch = self._advance(2) 
                #print(f'- Next ch = {ch}')
                if ch is None or not (ch.isdigit() or ch.lower() in "abcdef"):
                    raise TokenizerError("Hexadecimal digit expected")
                #print("Zatim ok")                
                while True:
                    ch = self._peek()
                    #print(f'Zpracovavam {ch}')
                    if ch is None or not (ch.isdigit() or ch.lower() in "abcdef"):
                        #print("- Konec HEX cisla")
                        break
                    self._advance(1)
                text = self.src[startp:self.pos]                
                #print(f'- jedeme dal, cislo je {text}')
                self._emit(TOK_NUMBER, self.sline, self.scol, text)    
                continue

            # 0b / 0B = binary
            if ch == '0' and (self._peek(1) in ('b','B')):
                startp = self.pos
                ch = self._advance(2)
                if ch is None or ch not in ('0','1'):
                    raise TokenizerError("Binary digit expected")
                while True:
                    ch = self._peek()
                    if ch is None or ch not in ('0','1'):
                        break
                    self._advance(1)
                text = self.src[startp:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue
            
            # ASCII character literal 'x'
            if ch == '\'':
                self._advance(1)  # Skip opening quote
                ch = self._peek()
                if ch is None:
                    raise TokenizerError("Unexpected EOF in character literal")
                
                # Handle escape sequences
                if ch == '\\':
                    self._advance(1)
                    esc = self._peek()
                    if esc is None:
                        raise TokenizerError("Unexpected EOF in escape sequence")
                    if esc in ESCAPES:
                        char_val = ord(ESCAPES[esc])
                    else:
                        raise TokenizerError(f"Unknown escape sequence: \\{esc}")
                    self._advance(1)
                else:
                    char_val = ord(ch)
                    self._advance(1)
                
                # Expect closing quote
                if self._peek() != '\'':
                    raise TokenizerError("Expected closing quote in character literal")
                self._advance(1)  # Skip closing quote
                
                self._emit(TOK_NUMBER, self.sline, self.scol, str(char_val))
                continue

            # =
            if ch == '=':
                ch2 = self._peek(1)
                if ch2 == '=':
                    # ==
                    self._emit(TOK_OP, self.sline, self.scol, "==")
                    self._advance(2)
                else:
                    # single =
                    self._emit(TOK_EQU, self.sline, self.scol, "")
                    self._advance(1)
                continue

            # Decimal numbers
            if ch.isdigit():
                start = self.pos
                while True:
                    ch = self._peek()
                    if ch is None or not ch.isdigit():
                        break
                    ch = self._advance()
                text = self.src[start:self.pos]
                self._emit(TOK_NUMBER, self.sline, self.scol, text)
                continue

            if ch == '_':
                print(f'_ is not allowed as first character at {self.pline}, {self.pcol}')
                exit(1)

            # Identifiers and keywords
            if ch.isalpha() or ch == '.':
                start = self.pos
                t = self._advance()
                while True:
                    ch = self._peek()
                    if ch is None or not (ch.isdigit() or ch.isalpha() or ch == "_") or ch.isspace():
                        break
                    ch = self._advance()                
                text = self.src[start:self.pos]
                #print(f'{text} {PREPROC}')
                if text.lower() in TYPES:
                    #print(f'- TYPE')
                    self._emit(TOK_TYPE, self.sline, self.scol, text.upper())  
                    continue
                if text.lower() in TYPEMOD:
                    #print(f'- TYPEMOD')
                    self._emit(TOK_TYPEMOD, self.sline, self.scol, text.upper())  
                    continue                                
                if text.lower() in KEYWORDS:
                    self._emit(TOK_KEYWORD, self.sline, self.scol, text.upper())
                    if text.lower() == "asm":
                        self._consume_asm_block()
                    continue
                if text.lower() in PREPROC:
                    #print(f'- PREPROC')
                    self._emit(TOK_PREPROC, self.sline, self.scol, text.upper())
                    continue
                #print(f'- IDENT')
                self._emit(TOK_IDENT, self.sline, self.scol, text.upper())
                continue

            # Operators and punctuation
            # try three-char
            c1 = ch
            c2 = self._peek(1) or ""
            di = (c1 or "") + (c2 or "")
            
            if di in TWO_CHAR_OPS:                
                self._emit(TOK_OP, self.sline, self.scol, di)
                self._advance(2)
                continue

            # single-char operators/punct
            if ch in SINGLE_OPS:
                self._emit(TOK_OP, self.sline, self.scol, ch)
                self._advance()
                continue

            if ch == '{':
                self._advance()
                self._emit(TOK_LCURLY, self.sline, self.scol, ch)
                continue

            if ch == '}':
                self._advance()
                self._emit(TOK_RCURLY, self.sline, self.scol, ch)
                continue

            if ch in DELIMIN:
                self._emit(TOK_DELIM, self.sline, self.scol, ch)
                self._advance()
                continue

            if ch in PTR:
                self._advance()
                self._emit(TOK_PTR, self.sline, self.scol, ch)
                continue

            if ch in SQB:
                self._advance()
                self._emit(TOK_SQB, self.sline, self.scol, ch)
                continue
            
            if ch == '(':
                self._advance()
                self._emit(TOK_LBRACE, self.sline, self.scol, ch)
                continue

            if ch == ')':
                self._advance()
                self._emit(TOK_RBRACE, self.sline, self.scol, ch)
                continue

            if ch == '@':
                self._advance()
                self._emit(TOK_AT, self.sline, self.scol, ch)
                continue

            self._advance()                 
        return


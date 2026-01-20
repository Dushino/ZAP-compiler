#!/usr/bin/env python3
"""Debug binary escape"""

from tokenizer import Tokenizer
from token_types import TOK_STRING

code = r'x = "\b00000000"'
print(f"Input code: {code}")
print(f"Raw input: {repr(code)}")

tokenizer = Tokenizer(code)
tokenizer.tokenize()
tokens = tokenizer._getTokens()

for t in tokens:
    if t.type == TOK_STRING:
        print(f"Token type: {t.type}")
        print(f"Token value: {repr(t.value)}")
        print(f"Length: {len(t.value)}")
        for i, ch in enumerate(t.value):
            print(f"  [{i}]: {repr(ch)} (ord {ord(ch)})")

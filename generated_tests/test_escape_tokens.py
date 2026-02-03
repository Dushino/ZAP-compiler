#!/usr/bin/env python3
"""Direct test of escape sequences in tokenizer"""

from tokenizer import Tokenizer

code = r'''
byte magic[] = "\xFF\xAA\x55"
byte ascii[] = "\101\102\103"
byte bits[] = "\b11110000"
byte text[] = "Hello\0World"
byte msg = '\x41'
byte mask = '\b10101010'
'''

print("Testing escape sequences directly in tokenizer...\n")

try:
    tokenizer = Tokenizer(code)
    tokenizer.tokenize()
    tokens = tokenizer._getTokens()
    
    print(f"✓ Successfully tokenized {len(tokens)} tokens\n")
    
    # Find and display string/char tokens with escape sequences
    print("Escape sequence tokens found:")
    for i, token in enumerate(tokens):
        if token.type == "STRING":
            # Display as hex bytes to avoid encoding issues
            hex_repr = " ".join(f"{ord(c):02X}" for c in token.value)
            print(f"  STRING: [{hex_repr}]  (length={len(token.value)})")
        elif token.type == "CHAR":
            print(f"  CHAR:   '{token.value}' (ord={ord(token.value)})")
    
    print("\n✓ All escape sequences tokenized successfully!")
    
except Exception as e:
    from errors import print_exception
    print_exception(e)

from tokenizer import Tokenizer

code = '''byte result @40000 = 0

proc setfont()

    .segment "FONT"
    .incbin "font.fnt"
    .segment "CODE"


end
'''

tokenizer = Tokenizer(code)
tokenizer.tokenize()
tokens = tokenizer._getTokens()
print(f"Total tokens: {len(tokens)}")
for i, token in enumerate(tokens):
    print(f'{i}: {token.type:15} {repr(token.value):20} line {token.line}')

from tokenizer import Tokenizer

code = open('tests/pass/026-struct/026-struct.zap').read()
t = Tokenizer(code)
t.tokenize()
tokens = t._getTokens()

for i, tok in enumerate(tokens[:50]):
    print(f"{i}: {tok.type}({tok.value})")

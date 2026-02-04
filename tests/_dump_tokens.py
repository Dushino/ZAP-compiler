from tokenizer import Tokenizer
s='enum Colors { RED, GREEN, BLUE }\nbyte x = GREEN\nproc main()\nend\n'
print(s)
t=Tokenizer(s)
t.tokenize()
for tok in t._getTokens():
    print(tok)

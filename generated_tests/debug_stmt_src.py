from parser import Parser

with open('p1/src1/p1.act', 'r', encoding='utf-8') as f:
    source = f.read()

p = Parser(source, 'p1/src1/p1.act')
prog = p.parse_program()

print(f'stmt_src entries: {len(prog.debug["stmt_src"])}')
for k, v in list(prog.debug['stmt_src'].items())[:15]:
    fname, line, text = v
    print(f'Line {line}: {text.strip()[:60]}')

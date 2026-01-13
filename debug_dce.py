from compiler_pipeline import compile_program
from parser import Parser

with open('p1/src1/p1.act', 'r', encoding='utf-8') as f:
    source = f.read()

p = Parser(source, 'p1/src1/p1.act')
prog = p.parse_program()

print('BEFORE DCE:')
print(f'stmt_src entries: {len(prog.debug["stmt_src"])}')
for k, v in list(prog.debug['stmt_src'].items()):
    fname, line, text = v
    print(f'  ID {k}: Line {line}: {text.strip()[:50]}')

# Now compile to trigger DCE
result = compile_program(prog)

print('\nAFTER DCE (from program.debug):')
print(f'stmt_src entries: {len(prog.debug["stmt_src"])}')
for k, v in list(prog.debug['stmt_src'].items()):
    fname, line, text = v
    print(f'  ID {k}: Line {line}: {text.strip()[:50]}')

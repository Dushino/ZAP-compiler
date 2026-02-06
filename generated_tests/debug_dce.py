from compiler_pipeline import compile_program
from parser import Parser
import pytest

try:
    with open('p1/src1/p1.act', 'r', encoding='utf-8') as f:
        source = f.read()
except FileNotFoundError:
    pytest.skip("missing test data: p1/src1/p1.act", allow_module_level=True)

p = Parser(source, 'p1/src1/p1.act')
prog = p.parse_program()

print('BEFORE DCE:')
stmt_src_before = (prog.debug or {}).get("stmt_src", {})
print(f'stmt_src entries: {len(stmt_src_before)}')
for k, v in list(stmt_src_before.items()):
    fname, line, text = v
    print(f'  ID {k}: Line {line}: {text.strip()[:50]}')

# Now compile to trigger DCE
result = compile_program(prog)

print('\nAFTER DCE (from program.debug):')
stmt_src_after = (prog.debug or {}).get("stmt_src", {})
print(f'stmt_src entries: {len(stmt_src_after)}')
for k, v in list(stmt_src_after.items()):
    fname, line, text = v
    print(f'  ID {k}: Line {line}: {text.strip()[:50]}')

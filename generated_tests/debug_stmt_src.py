from parser import Parser
import pytest

try:
    with open('p1/src1/p1.act', 'r', encoding='utf-8') as f:
        source = f.read()
except FileNotFoundError:
    pytest.skip("missing test data: p1/src1/p1.act", allow_module_level=True)

p = Parser(source, 'p1/src1/p1.act')
prog = p.parse_program()

stmt_src = (prog.debug or {}).get("stmt_src", {})
print(f'stmt_src entries: {len(stmt_src)}')
for k, v in list(stmt_src.items())[:15]:
    fname, line, text = v
    print(f'Line {line}: {text.strip()[:60]}')

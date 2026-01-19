from parser import Parser
from compiler_pipeline import compile_program

code = open('tests/pass/026-struct/026-struct.zap').read()
p = Parser(code, '026-struct.zap')
ast = p.parse_program()
asm = compile_program(ast)

print("Generated Assembly for tests/pass/026-struct/026-struct.zap")
print("=" * 70)
print(asm)

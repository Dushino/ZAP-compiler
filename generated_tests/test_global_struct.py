#!/usr/bin/env python3

from parser import Parser
from compiler_pipeline import compile_program

code = """
struct Point
    byte x
    byte y
end

Point global_pt

proc main()
    global_pt.x = 1
    global_pt.y = 2
end
"""

parser = Parser(code, "test.zap")
ast = parser.parse_program()
asm = compile_program(ast)

print("Generated Assembly:")
print("=" * 70)
for line in asm.splitlines():
    print(line)

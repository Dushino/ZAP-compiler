#!/usr/bin/env python3

from parser import Parser

code = """
struct Point
    byte x
    byte y
end

Point global_pt

proc main()
end
"""

parser = Parser(code, "test.zap")
ast = parser.parse_program()

print("Program structure:")
print(f"  Declarations: {len(ast.decls)}")
for d in ast.decls:
    print(f"    {d}")

print(f"\n  Procedures: {len(ast.procs)}")
for p in ast.procs:
    print(f"    {p}")

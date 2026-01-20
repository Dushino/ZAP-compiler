#!/usr/bin/env python3
"""Quick validation of all major features"""

from parser import Parser
from compiler_pipeline import compile_program

test_cases = [
    ("Basic byte", "proc main() byte x = 5 end"),
    ("Basic struct", "struct P byte x byte y end proc main() end"),
    ("Struct return", "struct P byte x end func P foo() P p return p end proc main() end"),
    ("Struct param", "struct P byte x end func byte bar(P p) return p.x end proc main() end"),
    ("Struct ptr return", "struct P byte x end func P ^foo() return @P end proc main() end"),
    ("Func in func", "func byte f1(byte x) return x end func byte f2(byte x) return f1(x) end proc main() end"),
]

passed = 0
failed = 0

for name, code in test_cases:
    try:
        parser = Parser(code, f"{name}.zap")
        program = parser.parse_program()
        compile_program(program)
        print(f"✓ {name}")
        passed += 1
    except Exception as e:
        print(f"✗ {name}: {str(e)[:80]}")
        failed += 1

print(f"\nResults: {passed} passed, {failed} failed")

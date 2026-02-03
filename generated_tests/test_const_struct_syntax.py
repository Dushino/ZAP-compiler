#!/usr/bin/env python3
"""Test both const struct declaration syntax forms"""

# Test 1: Inline struct definition with const
test_code_1 = """
proc main()
    const struct Point { byte x; byte y; } p1 = { 10, 20 }
    byte temp
    temp = p1.x
end
"""

# Test 2: Named struct type with const
test_code_2 = """
struct Point
    byte x
    byte y
end

proc main()
    const Point p2 = { 30, 40 }
    byte temp
    temp = p2.x
end
"""

# Test 3: Global const struct with inline definition
test_code_3 = """
const struct GlobalPoint { byte x; byte y; } gp = { 50, 60 }

proc main()
    byte temp
    temp = gp.x
end
"""

# Test 4: Global const struct with named type
test_code_4 = """
struct GlobalRect
    byte x
    byte y
    byte w
    byte h
end

const GlobalRect gr = { 1, 2, 3, 4 }

proc main()
    byte temp
    temp = gr.w
end
"""

from parser import Parser
from compiler_pipeline import compile_program

tests = [
    ("Inline struct with const (local)", test_code_1),
    ("Named struct type with const (local)", test_code_2),
    ("Inline struct with const (global)", test_code_3),
    ("Named struct type with const (global)", test_code_4),
]

for name, code in tests:
    print(f"\nTest: {name}")
    print("-" * 60)
    try:
        parser = Parser(code, "test_const_syntax.zap")
        ast = parser.parse_program()
        print("  [OK] Parsing succeeded")
        
        asm = compile_program(ast)
        print("  [OK] Compilation succeeded")
        
    except Exception as e:
        from errors import print_exception
        print_exception(e, filename=f"<test {name}>")

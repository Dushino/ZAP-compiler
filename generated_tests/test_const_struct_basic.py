#!/usr/bin/env python3
"""Test const struct declarations"""

test_code = """
struct Point
    byte x
    byte y
end

proc main()
    const Point p1 = { 10, 20 }
    p1.x = 5  ; should fail - const!
end
"""

from parser import Parser
from compiler_pipeline import compile_program

try:
    parser = Parser(test_code, "test_const_struct.zap")
    ast = parser.parse_program()
    print("Parsing succeeded")
    
    asm = compile_program(ast)
    print("Compilation succeeded")
    print(asm[:500])
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

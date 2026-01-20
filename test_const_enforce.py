#!/usr/bin/env python3
"""Test const struct enforcement"""

test_code = """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    p.x = 5  ; Should fail - const!
end
"""

from parser import Parser
from compiler_pipeline import compile_program

try:
    parser = Parser(test_code, "test_const_enforce.zap")
    ast = parser.parse_program()
    print("[OK] Parsing succeeded")
    
    asm = compile_program(ast)
    print("[FAIL] Compilation succeeded (should have failed)")
except Exception as e:
    error_msg = str(e)
    if "const" in error_msg.lower():
        print(f"[PASS] Const enforcement works: {e}")
    else:
        print(f"[FAIL] Wrong error: {e}")

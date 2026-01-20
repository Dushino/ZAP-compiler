#!/usr/bin/env python3
"""Test 020-functions compilation"""

from parser import Parser
from compiler_pipeline import compile_program

code = """
func byte doublebb(byte x)
return x * 2
end

proc main()
end
"""

try:
    parser = Parser(code, "test.zap")
    program = parser.parse_program()
    compile_program(program)
    print("✓ Compiles successfully")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

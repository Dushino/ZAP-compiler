#!/usr/bin/env python3
from parser import Parser
from compiler_pipeline import compile_program

code = """byte ^ptr11
proc main()
end"""

try:
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    print("SUCCESS")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""Test the actual 020-functions file"""

from parser import Parser
from compiler_pipeline import compile_program

with open("tests/pass/020-functions/020-functions.zap", "r") as f:
    code = f.read()

try:
    parser = Parser(code, "020-functions.zap")
    program = parser.parse_program()
    result = compile_program(program)
    print("✓ 020-functions.zap compiles successfully")
    print(f"Generated {len(result)} bytes of assembly")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

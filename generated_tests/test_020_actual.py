#!/usr/bin/env python3
"""Test the actual 020-functions file"""

from parser import Parser
from compiler_pipeline import compile_program
import pytest

try:
    with open("tests/pass/020-functions/020-functions.zap", "r") as f:
        code = f.read()
except FileNotFoundError:
    pytest.skip("missing test data: tests/pass/020-functions/020-functions.zap", allow_module_level=True)

try:
    parser = Parser(code, "020-functions.zap")
    program = parser.parse_program()
    result = compile_program(program)
    print("✓ 020-functions.zap compiles successfully")
    print(f"Generated {len(result)} bytes of assembly")
except Exception as e:
    from errors import print_exception
    print_exception(e)

#!/usr/bin/env python3
from parser import Parser

code = """byte ^ptr11
proc main()
end"""

try:
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    print("SUCCESS")
except Exception as e:
    print(f"FAIL: {e}")

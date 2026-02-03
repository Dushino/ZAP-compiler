#!/usr/bin/env python3
"""Debug pointer arithmetic code generation"""

import sys
from parser import Parser
from compiler_pipeline import compile_program

code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[5]
    ^Point ptr
    ptr = @arr[0]
    ptr = ptr + 1
end
"""

try:
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    result = compile_program(ast)
    print(result)
except Exception as e:
        from errors import print_exception
        print_exception(e)

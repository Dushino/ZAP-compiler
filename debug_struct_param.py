#!/usr/bin/env python3
"""Debug struct parameter type checking"""

from parser import Parser
from compiler_pipeline import compile_program

code = """
struct Point
    byte x
    byte y
end

func byte get_x(Point p)
    return p.x
end

proc main()
    Point p = { 5, 10 }
    byte x = get_x(p)
end
"""

try:
    parser = Parser(code, "test.zap")
    program = parser.parse_program()
    print(f"✓ Parsed successfully")
    result = compile_program(program)
    print(f"✓ Compiled successfully")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

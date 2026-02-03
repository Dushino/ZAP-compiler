#!/usr/bin/env python3
"""Debug struct pointer return parsing with instrumentation"""

from parser import Parser
from token_types import *

code = """
struct Point
    byte x
    byte y
end

Point points[10]

func Point ^get_point(byte idx)
    return @points[idx]
end

proc main()
    Point ^ptr = get_point(0)
end
"""

class DebugParser(Parser):
    def parse_assign(self):
        print(f"  parse_assign at pos={self.pos}, cur.type={self.cur.type}, cur.value={self.cur.value}")
        return super().parse_assign()
    
    def parse_declaration(self):
        print(f"  parse_declaration at pos={self.pos}, cur.type={self.cur.type}, cur.value={self.cur.value}")
        return super().parse_declaration()

try:
    parser = DebugParser(code, "test.zap")
    program = parser.parse_program()
    print(f"✓ Parsed successfully")
except Exception as e:
    from errors import print_exception
    print_exception(e)

#!/usr/bin/env python3
"""Debug struct pointer return parsing"""

from parser import Parser

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

try:
    parser = Parser(code, "test.zap")
    program = parser.parse_program()
    print(f"✓ Parsed successfully")
    for proc in program.procs:
        print(f"  - {proc}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3

from parser import Parser

code = """
struct Node
    byte data
    ^Node flink
    ^Node blink
end

proc main()
    Node node
    node.data = 42
end
"""

try:
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    print("SUCCESS: Parsed")
    for item in ast.procs:
        print(f"  {item}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""Debug parse_program"""

from parser import Parser
import traceback

code = """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""

print("Calling parse_program()...")
try:
    parser = Parser(code, "test.zap")
    program = parser.parse_program()
    print(f"✓ Success")
    print(f"  Declarations: {len(program.decls)}")
    print(f"  Procs: {len(program.procs)}")
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()

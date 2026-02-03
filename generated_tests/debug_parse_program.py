#!/usr/bin/env python3
"""Debug parse_program"""

from parser import Parser
from errors import print_exception

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
    from errors import print_exception
    print_exception(e)

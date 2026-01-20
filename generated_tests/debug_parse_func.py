#!/usr/bin/env python3
"""Debug parse_func execution"""

from parser import Parser
from token_types import *
import traceback

code = """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""

parser = Parser(code, "test.zap")

# Do first pass struct collection
temp_pos = parser.pos
temp_cur = parser.cur
while parser.cur.type != TOK_EOF:
    if parser.cur.type == TOK_KEYWORD and parser.cur.value == "STRUCT":
        parser.advance()
        if parser.cur.type == TOK_IDENT:
            parser.struct_names.add(parser.cur.value.upper())
        while parser.cur.type != TOK_EOF and not (parser.cur.type == TOK_KEYWORD and parser.cur.value == "END"):
            parser.advance()
        if parser.cur.type == TOK_KEYWORD:
            parser.advance()
    else:
        parser.advance()

# Reset
parser.pos = temp_pos
parser.cur = temp_cur

# Manually call parse_func
print("Calling parse_func()...")
try:
    func_decl = parser.parse_func()
    print(f"✓ Success: {func_decl.name}")
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()

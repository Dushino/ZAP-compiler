#!/usr/bin/env python3
"""Debug parser reset"""

from parser import Parser
from token_types import *

code = """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""

parser = Parser(code, "test.zap")

print(f"Initial state:")
print(f"  pos = {parser.pos}")
print(f"  cur.type = {parser.cur.type}")
print(f"  cur.value = {parser.cur.value}")

temp_pos = parser.pos
print(f"\nSaved pos = {temp_pos}")

# Do first pass (manually)
print(f"\nFirst pass (advance through all tokens)...")
iteration = 0
while parser.cur.type != TOK_EOF and iteration < 100:
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
    iteration += 1

print(f"After first pass (iteration {iteration}):")
print(f"  pos = {parser.pos}")
print(f"  cur.type = {parser.cur.type}")

# Reset
parser.pos = temp_pos
if parser.pos < len(parser.tokens):
    parser.cur = parser.tokens[parser.pos]

print(f"\nAfter reset:")
print(f"  pos = {parser.pos}")
print(f"  cur.type = {parser.cur.type}")
print(f"  cur.value = {parser.cur.value}")
print(f"  Expected: FUNC")

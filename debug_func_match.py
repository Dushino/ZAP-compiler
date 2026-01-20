#!/usr/bin/env python3
"""Debug why FUNC isn't being matched"""

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

# Manually do first pass
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

# Now second pass - debug each token
print("Second pass:")
iteration = 0
while parser.cur.type != TOK_EOF and iteration < 10:
    cur_type = parser.cur.type
    cur_value = parser.cur.value
    
    print(f"Iteration {iteration}:")
    print(f"  cur.type = {cur_type}")
    print(f"  cur.value = {cur_value}")
    print(f"  TOK_KEYWORD = {TOK_KEYWORD}")
    print(f"  Condition (TOK_KEYWORD, 'FUNC'): {cur_type == TOK_KEYWORD and cur_value == 'FUNC'}")
    print(f"  Condition (TOK_TYPE, TOK_TYPEMOD): {cur_type in (TOK_TYPE, TOK_TYPEMOD)}")
    
    if cur_type == TOK_KEYWORD and cur_value == "STRUCT":
        print("  -> STRUCT")
        parser.advance()
    elif cur_type in (TOK_TYPE, TOK_TYPEMOD):
        print("  -> Declaration")
        break  # Stop here for debugging
    elif cur_type == TOK_IDENT and cur_value.upper() in parser.struct_names:
        print("  -> Struct type declaration")
        break
    elif cur_type == TOK_KEYWORD and cur_value == "PROC":
        print("  -> PROC")
        break
    elif cur_type == TOK_KEYWORD and cur_value == "FUNC":
        print("  -> FUNC")
        break
    elif cur_type == TOK_IDENT:
        print("  -> Skip stray ident")
        parser.advance()
    else:
        print(f"  -> ERROR (no condition matched)")
        break
    
    iteration += 1

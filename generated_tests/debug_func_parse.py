#!/usr/bin/env python3
"""Debug function parsing"""

from parser import Parser

code = """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""

print("PARSING:")
try:
    parser = Parser(code, "test.zap")
    
    # Try first pass scan
    print("Scanning struct names...")
    temp_pos = parser.pos
    temp_cur = parser.cur
    while parser.cur.type != "EOF":
        print(f"  Current: {parser.cur.type} = {parser.cur.value}")
        if parser.cur.type == "KEYWORD" and parser.cur.value == "STRUCT":
            parser.advance()
            if parser.cur.type == "IDENT":
                parser.struct_names.add(parser.cur.value.upper())
            while parser.cur.type != "EOF" and not (parser.cur.type == "KEYWORD" and parser.cur.value == "END"):
                parser.advance()
            if parser.cur.type == "KEYWORD":
                parser.advance()
        else:
            parser.advance()
    
    print(f"  Found struct names: {parser.struct_names}")
    
    # Reset
    parser.pos = temp_pos
    parser.cur = temp_cur
    
    # Now try second pass
    print("\nSecond pass parsing...")
    while parser.cur.type != "EOF":
        print(f"  Position {parser.pos}: {parser.cur.type:15} = {parser.cur.value:20}")
        if parser.cur.type == "KEYWORD" and parser.cur.value == "FUNC":
            print(f"    Found FUNC!")
            break
        parser.advance()
    
except Exception as e:
    from errors import print_exception
    print_exception(e)

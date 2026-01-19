from parser import Parser

code = open('tests/pass/026-struct/026-struct.zap').read()
p = Parser(code, 'test.zap')

# After init
print(f"Initial position: {p.pos}")
print(f"Initial token: {p.cur}")
print(f"Token[0]: {p.tokens[0]}")
print(f"Token[1]: {p.tokens[1]}")

# Now parse
try:
    ast = p.parse_program()
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
    print(f"Current token: {p.cur}")
    print(f"Position: {p.pos}")
    print(f"struct_names: {p.struct_names}")

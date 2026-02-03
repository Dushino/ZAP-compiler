#!/usr/bin/env python3

from parser import Parser
from compiler_pipeline import compile_program

test_code = """
struct Point
    byte x
    byte y
end

proc main()
    Point pt
    word ptr_pt
    byte a
    
    ptr_pt = 1024
    ptr_pt^.x = 50
    a = ptr_pt^.y
end
"""

print("=" * 60)
print("TEST: Pointer Struct Field Access")
print("=" * 60)
print("Source code:\n")
print(test_code)

try:
    # Parse and compile
    parser = Parser(test_code, "Pointer Struct Field Access.zap")
    ast = parser.parse_program()
    asm_output = compile_program(ast)
    
    # Print results
    lines = asm_output.split('\n')
    print("[OK] Parsing succeeded!")
    print("[OK] Compilation succeeded!")
    print(f"[OK] Generated {len(lines)} lines of assembly\n")
    
    print("Generated assembly (first 50 lines):")
    print("-" * 60)
    for i, line in enumerate(lines[:50], 1):
        print(f"{i:3}: {line}")
    
except Exception as e:
    from errors import print_exception
    print_exception(e, filename="Pointer Struct Field Access.zap")

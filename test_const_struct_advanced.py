#!/usr/bin/env python3
"""Test const struct declarations with full features"""

test_code = """
struct Point
    byte x
    byte y
end

struct Rect
    byte x
    byte y
    byte w
    byte h
end

proc main()
    const Point p = { 10, 20 }
    const Rect r = { 5, 10, 100, 50 }
    byte temp
    
    ; Read from const struct
    temp = p.x
    temp = p.y
    temp = r.w
end
"""

from parser import Parser
from compiler_pipeline import compile_program

try:
    parser = Parser(test_code, "test_const_struct_advanced.zap")
    ast = parser.parse_program()
    print("[OK] Parsing succeeded")
    
    asm = compile_program(ast)
    print("[OK] Compilation succeeded")
    
    # Check if const struct data is in BSS or CODE segment
    if "_MAIN_P" in asm:
        print("[OK] Const struct variable allocated")
    else:
        print("[WARN] Const struct variable not found in assembly")
    
    # Print relevant parts
    lines = asm.split('\n')
    in_data = False
    for i, line in enumerate(lines):
        if 'ZEROPAGE' in line or 'CODE' in line or 'BSS' in line or 'DATA' in line:
            in_data = True
        if in_data and i < 100:
            print(line)
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

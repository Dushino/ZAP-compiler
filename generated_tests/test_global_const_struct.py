#!/usr/bin/env python3
"""Test global const structs work properly"""

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

; Global const structs
const Point gp1 = { 10, 20 }
const Point gp2 = { 30, 40 }
const Rect gr = { 5, 10, 100, 50 }

proc main()
    byte temp
    
    ; Read from global const structs
    temp = gp1.x
    temp = gp2.y
    temp = gr.w
end
"""

from parser import Parser
from compiler_pipeline import compile_program

try:
    parser = Parser(test_code, "test_global_const_struct.zap")
    ast = parser.parse_program()
    print("[OK] Parsing succeeded")
    
    asm = compile_program(ast)
    print("[OK] Compilation succeeded")
    
    # Check for const struct variables
    checks = [
        ("_GP1", "Global point 1 allocated"),
        ("_GP2", "Global point 2 allocated"),
        ("_GR", "Global rect allocated"),
        ("LDA #10", "gp1 initialization (x=10)"),
        ("LDA #20", "gp1 initialization (y=20)"),
    ]
    
    for check_str, description in checks:
        if check_str in asm:
            print(f"[OK] {description}")
        else:
            print(f"[WARN] {description} not found")
    
    # Print assembly for inspection
    print("\n" + "="*60)
    print("GENERATED ASSEMBLY:")
    print("="*60)
    lines = asm.split('\n')
    for i, line in enumerate(lines):
        # Print headers and relevant initialization code
        if any(x in line for x in ['segment', '_GP', '_GR', 'LDA #', 'STA _']):
            print(line)
            
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()

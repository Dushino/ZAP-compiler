#!/usr/bin/env python3
"""Verify const struct assembly output is correct"""

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

const Point gp = { 42, 84 }
const Rect gr = { 1, 2, 3, 4 }

proc main()
    const Point lp = { 10, 20 }
    const Rect lr = { 5, 10, 100, 50 }
    byte a, b, c
    
    ; Read from const structs
    a = gp.x
    b = lp.y
    c = gr.w
end
"""

from parser import Parser
from compiler_pipeline import compile_program

print("Compiling const struct assembly verification test...")
print("-" * 70)

try:
    parser = Parser(test_code, "test_asm.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    
    print("Assembly Output (relevant sections):")
    print("=" * 70)
    
    lines = asm.split('\n')
    in_code = False
    for line in lines:
        # Print segment headers
        if '.segment' in line:
            in_code = True
            print(line)
        # Print variable allocations and initialization
        elif any(x in line for x in ['_GP', '_GR', '_LP', '_LR', 'LDA #', 'STA _', 'ARRAY_DATA', '.byte', 'ARR_COPY']):
            if 'End of file' not in line:
                print(line)
    
    print("\n" + "=" * 70)
    print("✓ Assembly generation successful")
    
    # Verify correct patterns
    checks = [
        ("_GP", "Global const Point variable exists"),
        ("_GR", "Global const Rect variable exists"),
        ("LDA #10", "Local const Point initialization (x=10)"),
        ("STA _LP", "Local const Point storage"),
        ("ARRAY_DATA", "Const data section for larger structs"),
    ]
    
    print("\nVerification Checks:")
    print("-" * 70)
    for pattern, description in checks:
        if pattern in asm:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

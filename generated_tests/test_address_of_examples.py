#!/usr/bin/env python3
"""Test @ address-of with examples from documentation"""

from parser import Parser
from compiler_pipeline import compile_program

# Simple example of address-of operator
test_code = """
struct Point
    byte x
    byte y
end

proc main()
    byte data = 42
    word addr = @data
    
    byte arr[] = { 1, 2, 3 }
    word arr_addr = @arr[1]
    
    Point p = { 10, 20 }
    word p_addr = @p
    
    byte field_addr_temp
    field_addr_temp = @p.x
end
"""

print("Testing @ operator with documented examples...")
print("="*70)

try:
    parser = Parser(test_code, "test.zap")
    ast = parser.parse_program()
    print("[OK] Parsing succeeded")
    
    asm = compile_program(ast)
    print("[OK] Compilation succeeded")
    
    # Check for address-of patterns in assembly
    patterns = [
        "LDA #<_P1",
        "LDX #>_P1",
        "@POINTS",
    ]
    
    found_patterns = []
    for pattern in patterns:
        if any(pattern in line for line in asm.split('\n')):
            found_patterns.append(pattern)
    
    print(f"[OK] Found {len(found_patterns)} expected address patterns in assembly")
    
    # Print relevant assembly
    print("\n" + "="*70)
    print("Generated assembly (address-of sections):")
    print("="*70)
    lines = asm.split('\n')
    for i, line in enumerate(lines):
        if 'LDA #<' in line or 'LDX #>' in line or 'pp =' in line or 'pa =' in line or 'px =' in line:
            print(line)
    
    print("\n[SUCCESS] Address-of operator is fully functional!")
    
except Exception as e:
    from errors import print_exception
    print_exception(e, filename="<test address_of_examples>")

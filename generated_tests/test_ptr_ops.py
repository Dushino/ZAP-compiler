#!/usr/bin/env python3
"""Test pointer arithmetic operations"""

from parser import Parser
from compiler_pipeline import compile_program
import re

def test_ptr_arithmetic_ops():
    """Test various pointer arithmetic operations"""
    
    code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[10]
    ^Point ptr
    ptr = @arr[0]
    ptr = ptr + 1
    ptr = ptr + 2
    ptr = ptr + 3
    ptr = ptr - 1
end
"""
    
    try:
        parser = Parser(code, "test_ops.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        # Check for expected additions and subtractions
        # ptr + 1 should add 2 (scale by 2)
        if 'ADC #2' in asm:
            print("[PASS] ptr + 1 correctly adds 2")
        else:
            print("[FAIL] ptr + 1 should add 2")
        
        # ptr + 2 should add 4 (2 * 2)
        if 'ADC #4' in asm:
            print("[PASS] ptr + 2 correctly adds 4")
        else:
            print("[FAIL] ptr + 2 should add 4")
            
        # ptr + 3 should add 6 (3 * 2)
        if 'ADC #6' in asm:
            print("[PASS] ptr + 3 correctly adds 6")
        else:
            print("[FAIL] ptr + 3 should add 6")
        
        # ptr - 1 should subtract 2
        if 'SBC #2' in asm:
            print("[PASS] ptr - 1 correctly subtracts 2")
        else:
            print("[FAIL] ptr - 1 should subtract 2")
            print("Generated assembly (subtraction area):")
            lines = asm.split('\n')
            for i, line in enumerate(lines):
                if 'ptr = ptr - 1' in line:
                    for j in range(i, min(i + 10, len(lines))):
                        print(f"  {lines[j]}")
                    break
        
        print("\n[INFO] Full assembly (ptr arithmetic region):")
        lines = asm.split('\n')
        in_ptr_section = False
        for line in lines:
            if 'ptr = ptr' in line:
                in_ptr_section = True
            if in_ptr_section:
                print(f"  {line}")
                if 'RTS' in line:
                    break
                    
    except Exception as e:
        from errors import print_exception
        print_exception(e)
        from errors import print_exception
        from errors import print_exception
        print_exception(e)

if __name__ == "__main__":
    test_ptr_arithmetic_ops()

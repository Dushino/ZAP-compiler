#!/usr/bin/env python3
"""Comprehensive test for pointer arithmetic with struct sizes"""

from parser import Parser
from compiler_pipeline import compile_program
import re

def test_comprehensive_ptr_arithmetic():
    """Test pointer arithmetic comprehensively"""
    
    print("=" * 70)
    print("COMPREHENSIVE POINTER ARITHMETIC TEST")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: 2-byte struct
    print("\n[TEST 1] Pointer arithmetic with 2-byte struct (Point)")
    code1 = """
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
    ptr = ptr - 1
end
"""
    
    try:
        parser = Parser(code1, "test1.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        checks = [
            ('ADC #2', "ptr + 1 adds 2"),
            ('ADC #4', "ptr + 2 adds 4"),
            ('SBC #2', "ptr - 1 subtracts 2"),
        ]
        
        for expected, desc in checks:
            if expected in asm:
                print(f"  [PASS] {desc}")
                tests_passed += 1
            else:
                print(f"  [FAIL] {desc} - expected '{expected}'")
            tests_total += 1
    except Exception as e:
        from errors import print_exception
        print_exception(e, filename="<test>")
        tests_total += 3
    
    # Test 2: 3-byte struct
    print("\n[TEST 2] Pointer arithmetic with 3-byte struct (Triple)")
    code2 = """
struct Triple
    byte a
    byte b
    byte c
end

proc main()
    Triple arr[10]
    ^Triple ptr
    ptr = @arr[0]
    ptr = ptr + 1
    ptr = ptr + 2
    ptr = ptr - 1
end
"""
    
    try:
        parser = Parser(code2, "test2.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        checks = [
            ('ADC #3', "ptr + 1 adds 3"),
            ('ADC #6', "ptr + 2 adds 6"),
            ('SBC #3', "ptr - 1 subtracts 3"),
        ]
        
        for expected, desc in checks:
            if expected in asm:
                print(f"  [PASS] {desc}")
                tests_passed += 1
            else:
                print(f"  [FAIL] {desc} - expected '{expected}'")
            tests_total += 1
    except Exception as e:
        from errors import print_exception
        print_exception(e, filename="<test>")
        tests_total += 3
    
    # Test 3: 4-byte struct
    print("\n[TEST 3] Pointer arithmetic with 4-byte struct (Quad)")
    code3 = """
struct Quad
    byte a
    byte b
    byte c
    byte d
end

proc main()
    Quad arr[10]
    ^Quad ptr
    ptr = @arr[0]
    ptr = ptr + 1
    ptr = ptr + 3
    ptr = ptr - 2
end
"""
    
    try:
        parser = Parser(code3, "test3.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        checks = [
            ('ADC #4', "ptr + 1 adds 4"),
            ('ADC #12', "ptr + 3 adds 12 (3*4)"),
            ('SBC #8', "ptr - 2 subtracts 8 (2*4)"),
        ]
        
        for expected, desc in checks:
            if expected in asm:
                print(f"  [PASS] {desc}")
                tests_passed += 1
            else:
                print(f"  [FAIL] {desc} - expected '{expected}'")
                # Debug: show what we got
                if 'ADC' in desc or 'SBC' in desc:
                    matches = re.findall(r'(ADC|SBC)\s+#(\d+)', asm)
                    if matches:
                        print(f"         Found operations: {matches}")
            tests_total += 1
    except Exception as e:
        from errors import print_exception
        print_exception(e, filename="<test>")
        tests_total += 3
    
    # Test 4: Pointer to self-referential struct
    print("\n[TEST 4] Pointer arithmetic with self-referential struct (Node)")
    code4 = """
struct Node
    byte data
    ^Node link
end

proc main()
    Node arr[5]
    ^Node ptr
    ptr = @arr[0]
    ptr = ptr + 1
    ptr = ptr - 1
end
"""
    
    try:
        parser = Parser(code4, "test4.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        checks = [
            ('ADC #3', "ptr + 1 adds 3 (1-byte data + 2-byte pointer)"),
            ('SBC #3', "ptr - 1 subtracts 3"),
        ]
        
        for expected, desc in checks:
            if expected in asm:
                print(f"  [PASS] {desc}")
                tests_passed += 1
            else:
                print(f"  [FAIL] {desc} - expected '{expected}'")
            tests_total += 1
    except Exception as e:
            from errors import print_exception
            print_exception(e, filename="<test>")

if __name__ == "__main__":
    success = test_comprehensive_ptr_arithmetic()
    exit(0 if success else 1)

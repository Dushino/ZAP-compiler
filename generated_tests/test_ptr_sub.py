#!/usr/bin/env python3
"""Test pointer arithmetic subtraction"""

from parser import Parser
from compiler_pipeline import compile_program

def test_ptr_sub():
    """Test pointer subtraction with different struct sizes"""
    
    code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[10]
    ^Point ptr
    ptr = @arr[5]
    ptr = ptr - 1
    ptr = ptr - 2
    ptr = ptr - 3
end
"""
    
    try:
        parser = Parser(code, "test_sub.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        # Check for expected subtractions
        print("[TEST] Pointer subtraction with 2-byte struct:")
        lines = asm.split('\n')
        
        sub_tests = [
            ('ptr - 1', 'SBC #2', 'should subtract 2'),
            ('ptr - 2', 'SBC #4', 'should subtract 4'),
            ('ptr - 3', 'SBC #6', 'should subtract 6'),
        ]
        
        for desc, expected, msg in sub_tests:
            found = expected in asm
            status = "[PASS]" if found else "[FAIL]"
            print(f"  {status} {desc} {msg}: {expected}")
            
    except Exception as e:
        from errors import print_exception
        print_exception(e)

if __name__ == "__main__":
    test_ptr_sub()

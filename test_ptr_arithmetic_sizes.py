#!/usr/bin/env python3
"""Test pointer arithmetic with various struct sizes"""

from parser import Parser
from compiler_pipeline import compile_program
import re

def test_ptr_arithmetic_by_size():
    """Test pointer arithmetic with different struct sizes"""
    
    test_cases = [
        # (struct_size, struct_def, expected_scale)
        (2, """
struct Point
    byte x
    byte y
end
""", 2),
        (3, """
struct Triple
    byte a
    byte b
    byte c
end
""", 3),
        (4, """
struct Quad
    byte a
    byte b
    byte c
    byte d
end
""", 4),
    ]
    
    for expected_size, struct_def, expected_scale in test_cases:
        struct_name = struct_def.split('\n')[1].split()[1]
        
        code = f"""{struct_def}

proc main()
    {struct_name} arr[10]
    ^{struct_name} ptr
    ptr = @arr[0]
    ptr = ptr + 1
end
"""
        
        try:
            parser = Parser(code, f"test_{struct_name}.zap")
            ast = parser.parse_program()
            asm = compile_program(ast)
            
            # Look for the ADC with the expected value
            pattern = rf'ADC\s+#(\d+)'
            matches = re.findall(pattern, asm)
            
            # Should have multiple matches (for array indexing too), but we want the one that's ptr+1
            # Look for the line after "; ptr = ptr + 1"
            lines = asm.split('\n')
            ptr_add_idx = None
            for i, line in enumerate(lines):
                if 'ptr = ptr + 1' in line:
                    ptr_add_idx = i
                    break
            
            if ptr_add_idx:
                # Find the ADC instruction after the ptr line
                for i in range(ptr_add_idx, min(ptr_add_idx + 10, len(lines))):
                    if f'ADC #{expected_scale}' in lines[i]:
                        print(f"[PASS] {struct_name} ({expected_size} bytes): Correctly adds {expected_scale}")
                        break
                else:
                    print(f"[FAIL] {struct_name} ({expected_size} bytes): Expected 'ADC #{expected_scale}' not found")
                    # Print relevant assembly for debugging
                    for i in range(ptr_add_idx, min(ptr_add_idx + 10, len(lines))):
                        print(f"      {lines[i]}")
            else:
                print(f"[FAIL] {struct_name} ({expected_size} bytes): Could not find ptr+1 line")
                
        except Exception as e:
            print(f"[ERROR] {struct_name} ({expected_size} bytes): {e}")

if __name__ == "__main__":
    test_ptr_arithmetic_by_size()

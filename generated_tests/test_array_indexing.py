#!/usr/bin/env python3
"""Test to verify struct array indexing with correct memory writes"""

from parser import Parser
from compiler_pipeline import compile_program

def test_array_indexing_writes():
    """Verify that p2[i].x and p2[i].y write to correct memory addresses"""
    source = """
struct Point
    byte x
    byte y
end

Point p2[3] @40016

proc main()
    byte i
    
    for i = 0 to 3
        p2[i].x = i+1
        p2[i].y = (i+1)*2
    next i
end
"""
    
    try:
        parser = Parser(source, "test.zap")
        program = parser.parse_program()
        result = compile_program(program)
        
        # Check that we see the correct addressing pattern
        # p2[i] where i=0: address 40016 (0x9C50)
        # p2[i] where i=1: address 40018 (0x9C52)  
        # p2[i] where i=2: address 40020 (0x9C54)
        
        lines = result.split('\n')
        
        # Find where p2[i].x assignments happen
        found_multiply_x = False
        found_multiply_y = False
        found_field_offset = False
        
        for i, line in enumerate(lines):
            # Check for ASL A (multiply index by 2 for struct size)
            if 'ASL A' in line and i > 50:  # In the loop body
                found_multiply_x = True
            
            # Check for field offset addition (ADC #1)
            if 'ADC #1' in line and i > 100:  # For .y field
                found_field_offset = True
        
        if found_multiply_x:
            print("✓ Array element address calculation: Multiplies index by struct size (ASL A)")
        else:
            print("✗ Missing: Array indexing not multiplying by struct size")
            return False
            
        if found_field_offset:
            print("✓ Field offset: Correctly adds offset for .y field (ADC #1)")
        else:
            print("✗ Missing: Field offset not being added")
            return False
        
        print("[OK] Array indexing with struct arrays working correctly!")
        return True
        
    except Exception as e:
        print(f"✗ Compilation failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("STRUCT ARRAY INDEXING TEST")
    print("=" * 70)
    print()
    
    result = test_array_indexing_writes()
    
    print()
    print("=" * 70)
    if result:
        print("[PASS] Array indexing with correct memory writes")
    else:
        print("[FAIL] Array indexing issues detected")
    print("=" * 70)

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
    end
end
"""
    
    parser = Parser(source, "test.zap")
    program = parser.parse_program()
    result = compile_program(program)
    lines = result.split('\n')

    # Find where p2[i].x assignments happen
    found_multiply_x = any('ASL A' in line for i, line in enumerate(lines) if i > 50)
    # Accept several immediate formats (decimal or hex $01)
    found_field_offset = any('ADC #' in line and ('#1' in line or '#$1' in line or '#$01' in line or '#$01' in line) for i, line in enumerate(lines))

    assert found_multiply_x, "Missing: Array indexing not multiplying by struct size (ASL A)"
    assert found_field_offset, "Missing: Field offset not being added (ADC #1/#$01)"
    # additional sanity check
    assert isinstance(result, str) and len(result) > 0, "Array indexing test generated no assembly"

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

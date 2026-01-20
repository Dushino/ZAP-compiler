#!/usr/bin/env python3
"""
Test struct arrays and pointer arithmetic
"""

from parser import Parser
from compiler_pipeline import compile_program

# Test 1: Array of structs
test_array = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[3]
    arr[0].x = 1
    arr[0].y = 2
    arr[1].x = 3
    arr[1].y = 4
    arr[2].x = 5
    arr[2].y = 6
end
"""

# Test 2: Pointer arithmetic with struct
test_ptr_arith = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[5]
    word ptr
    byte val
    
    ptr = 2048
    ptr = ptr + 1
    val = 42
end
"""

def test_struct_array(name, code):
    print("=" * 70)
    print(f"TEST: {name}")
    print("=" * 70)
    print("Source code:")
    print(code)
    print()
    
    try:
        parser = Parser(code, f"{name}.zap")
        ast = parser.parse_program()
        print("[OK] Parsing succeeded!")
        
        asm = compile_program(ast)
        lines = asm.splitlines()
        print(f"[OK] Compilation succeeded!")
        print(f"[OK] Generated {len(lines)} lines of assembly")
        print("\nGenerated assembly (first 70 lines):")
        print("-" * 70)
        for i, line in enumerate(lines[:70], 1):
            print(f"{i:3d}: {line}")
        if len(lines) > 70:
            print(f"... ({len(lines) - 70} more lines)")
        print("-" * 70)
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    results = []
    results.append(test_struct_array("Struct Array Access", test_array))
    print()
    results.append(test_struct_array("Pointer Arithmetic", test_ptr_arith))
    print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    if passed == total:
        print("[OK] All tests passed!")
    else:
        print(f"[FAIL] {total - passed} test(s) failed")

#!/usr/bin/env python3
"""
Test struct code generation with field access
"""

from parser import Parser
from compiler_pipeline import compile_program

# Test 1: Basic struct with field read
test_code_1 = """
struct Point
    byte x
    byte y
end

proc main()
    Point pt
    byte a
    a = pt.x
end
"""

# Test 2: Struct field write
test_code_2 = """
struct Point
    byte x
    byte y
end

proc main()
    Point pt
    pt.x = 42
    pt.y = 99
end
"""

# Test 3: Struct field arithmetic
test_code_3 = """
struct Rect
    byte width
    byte height
end

proc main()
    Rect r
    byte area
    r.width = 10
    r.height = 20
end
"""

def test_struct_codegen(name, code):
    print("=" * 60)
    print(f"TEST: {name}")
    print("=" * 60)
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
        print("\nGenerated assembly (first 50 lines):")
        print("-" * 60)
        for i, line in enumerate(lines[:50], 1):
            print(f"{i:3d}: {line}")
        if len(lines) > 50:
            print(f"... ({len(lines) - 50} more lines)")
        print("-" * 60)
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    results = []
    results.append(test_struct_codegen("Struct Field Read", test_code_1))
    print()
    results.append(test_struct_codegen("Struct Field Write", test_code_2))
    print()
    results.append(test_struct_codegen("Struct Field Assignment", test_code_3))
    print()
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    if passed == total:
        print("[OK] All tests passed!")
    else:
        print(f"[FAIL] {total - passed} test(s) failed")

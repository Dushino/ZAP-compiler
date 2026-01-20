#!/usr/bin/env python3
"""Test @ address-of operator"""

from parser import Parser
from compiler_pipeline import compile_program

test_cases = [
    ("Address of byte variable", """
proc main()
    byte b = 42
    word ptr
    ptr = @b
end
"""),
    
    ("Address of word variable", """
proc main()
    word w = 1000
    word ptr
    ptr = @w
end
"""),
    
    ("Address of array element", """
proc main()
    byte arr[] = { 1, 2, 3, 4, 5 }
    word ptr
    ptr = @arr[0]
    ptr = @arr[2]
end
"""),
    
    ("Address of struct variable", """
struct Point
    byte x
    byte y
end

proc main()
    Point p = { 10, 20 }
    word ptr
    ptr = @p
end
"""),
    
    ("Address of struct field", """
struct Point
    byte x
    byte y
end

proc main()
    Point p = { 10, 20 }
    byte ^ptr_to_field
    ptr_to_field = @p.x
end
"""),
    
    ("Assign address to pointer variable", """
proc main()
    byte data = 100
    byte ^ptr
    ptr = @data
end
"""),
    
    ("Global variable address", """
byte global_data = 50

proc main()
    word ptr
    ptr = @global_data
end
"""),
    
    ("Global array element address", """
byte arr[] = { 10, 20, 30 }

proc main()
    word ptr
    ptr = @arr[1]
end
"""),
    
    ("Address of multiple variables", """
proc main()
    byte a = 1
    byte b = 2
    word ptr_a, ptr_b
    ptr_a = @a
    ptr_b = @b
end
"""),
]

print("="*70)
print("ADDRESS-OF OPERATOR (@) TEST SUITE")
print("="*70)

passed = 0
failed = 0
failed_tests = []

for name, code in test_cases:
    try:
        parser = Parser(code, "test.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        print(f"[PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {name}")
        print(f"       Error: {str(e)[:100]}")
        failed += 1
        failed_tests.append((name, str(e)))

print("\n" + "="*70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("="*70)

if failed > 0:
    print("\nFailed tests:")
    for name, error in failed_tests:
        print(f"  - {name}")
else:
    print("\nAll tests PASSED!")

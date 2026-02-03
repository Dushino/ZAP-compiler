#!/usr/bin/env python3
"""Test CONST enforcement for all types - modifications should be blocked"""

from parser import Parser
from compiler_pipeline import compile_program

enforcement_tests = [
    ("Block const byte modification", """
proc main()
    const byte b = 42
    b = 50
end
""", True),  # should fail
    
    ("Block const word modification", """
proc main()
    const word w = 1000
    w = 2000
end
""", True),  # should fail
    
    ("Block const byte array element modification", """
proc main()
    const byte arr[] = { 1, 2, 3 }
    arr[0] = 99
end
""", True),  # should fail
    
    ("Block const word array element modification", """
proc main()
    const word arr[] = { 100, 200 }
    arr[1] = 999
end
""", True),  # should fail
    
    ("Allow non-const byte array modification", """
proc main()
    byte arr[] = { 1, 2, 3 }
    arr[0] = 99
end
""", False),  # should succeed
    
    ("Allow non-const word array modification", """
proc main()
    word arr[] = { 100, 200 }
    arr[1] = 999
end
""", False),  # should succeed
    
    ("Block const struct field modification", """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    p.x = 50
end
""", True),  # should fail
    
    ("Block global const byte modification", """
const byte GB = 100

proc main()
    GB = 50
end
""", True),  # should fail
    
    ("Block global const struct field modification", """
struct Point
    byte x
    byte y
end

const Point GP = { 50, 60 }

proc main()
    GP.x = 100
end
""", True),  # should fail
    
    ("Allow reading const values", """
proc main()
    const byte b = 42
    byte temp
    temp = b
end
""", False),  # should succeed
    
    ("Allow reading const array elements", """
proc main()
    const byte arr[] = { 1, 2, 3 }
    byte temp
    temp = arr[1]
end
""", False),  # should succeed
    
    ("Allow reading const struct fields", """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
    byte temp
    temp = p.x
end
""", False),  # should succeed
]

print("="*70)
print("CONST ENFORCEMENT TEST - ALL TYPES")
print("="*70)

passed = 0
failed = 0
failed_tests = []

for name, code, should_fail in enforcement_tests:
    try:
        parser = Parser(code, "test.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        
        if should_fail:
            print(f"[FAIL] {name} - should have failed but succeeded")
            failed += 1
            failed_tests.append((name, "Expected error but compilation succeeded"))
        else:
            print(f"[PASS] {name}")
            passed += 1
    except Exception as e:
        if should_fail:
            print(f"[PASS] {name} - correctly rejected")
            passed += 1
        else:
            print(f"[FAIL] {name} - should have succeeded but failed")
            from errors import print_exception
            print_exception(e)
            failed += 1
            failed_tests.append((name, str(e)))

print("\n" + "="*70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(enforcement_tests)} tests")
print("="*70)

if failed > 0:
    print("\nFailed tests:")
    for name, error in failed_tests:
        print(f"  - {name}")

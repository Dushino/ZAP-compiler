#!/usr/bin/env python3
"""Test CONST support for all variable types"""

from parser import Parser
from compiler_pipeline import compile_program
import sys

test_cases = [
    ("Const byte", """
proc main()
    const byte b = 42
end
"""),
    
    ("Const word", """
proc main()
    const word w = 1000
end
"""),
    
    ("Const byte pointer", """
proc main()
    const byte ^ptr = $2000
end
"""),
    
    ("Const word pointer", """
proc main()
    const word ^ptr = $3000
end
"""),
    
    ("Const byte array", """
proc main()
    const byte arr[] = { 1, 2, 3, 4, 5 }
end
"""),
    
    ("Const word array", """
proc main()
    const word arr[] = { 100, 200, 300 }
end
"""),
    
    ("Const struct", """
struct Point
    byte x
    byte y
end

proc main()
    const Point p = { 10, 20 }
end
"""),
    
    ("Const struct array", """
struct Point
    byte x
    byte y
end

proc main()
    const Point arr[] = { {1,2}, {3,4} }
end
"""),
    
    ("Global const byte", """
const byte GB = 100

proc main()
end
"""),
    
    ("Global const word", """
const word GW = 5000

proc main()
end
"""),
    
    ("Global const byte pointer", """
const byte ^GP = $4000

proc main()
end
"""),
    
    ("Global const byte array", """
const byte GA[] = "Hello"

proc main()
end
"""),
    
    ("Global const struct", """
struct Point
    byte x
    byte y
end

const Point GP = { 50, 60 }

proc main()
end
"""),
]

print("="*70)
print("CONST SUPPORT TEST - ALL VARIABLE TYPES")
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
        from errors import print_exception
        print_exception(e, filename=f"<test {name}>")
        failed += 1
        failed_tests.append((name, str(e)))

print("\n" + "="*70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("="*70)

if failed > 0:
    print("\nFailed tests:")
    for name, error in failed_tests:
        print(f"  - {name}")
        print(f"<testcase {name}>:1:1: error: {error[:100]}...", file=sys.stderr)

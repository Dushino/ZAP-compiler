#!/usr/bin/env python3
"""Comprehensive verification of function features"""

from parser import Parser
from compiler_pipeline import compile_program

print("=" * 70)
print("COMPREHENSIVE FUNCTION FEATURES VERIFICATION")
print("=" * 70)

tests = [
    ("Basic function", """
func byte add_one(byte x)
    return x + 1
end

proc main()
    byte result = add_one(5)
end
"""),
    
    ("Struct in function", """
struct Point
    byte x
    byte y
end

func Point make_point(byte x, byte y)
    Point p = { x, y }
    return p
end

proc main()
    Point p = make_point(10, 20)
end
"""),
    
    ("Struct parameter", """
struct Point
    byte x
    byte y
end

func byte get_x(Point p)
    return p.x
end

proc main()
    Point p = { 5, 10 }
    byte x = get_x(p)
end
"""),
    
    ("Pointer function", """
byte data[3] = { 1, 2, 3 }

func byte ^get_data()
    return @data
end

proc main()
    byte ^ptr = get_data()
end
"""),
    
    ("Struct pointer function", """
struct Point
    byte x
    byte y
end

Point points[5]

func Point ^get_point(byte idx)
    return @points[idx]
end

proc main()
    Point ^ptr = get_point(0)
end
"""),
    
    ("Function calls function", """
func byte double(byte x)
    return x * 2
end

func byte quad(byte x)
    return double(double(x))
end

proc main()
    byte result = quad(5)
end
"""),
    
    ("Multiple parameters", """
func byte max(byte a, byte b, byte c)
    if a > b then
        if a > c then
            return a
        endif
    endif
    if b > c then
        return b
    endif
    return c
end

proc main()
    byte m = max(3, 8, 5)
end
"""),
]

passed = 0
failed = 0
errors = []

for name, code in tests:
    try:
        parser = Parser(code, f"{name}.zap")
        program = parser.parse_program()
        compile_program(program)
        print(f"✓ {name}")
        passed += 1
    except Exception as e:
        error_msg = str(e)[:100]
        print(f"✗ {name}: {error_msg}")
        errors.append((name, error_msg))
        failed += 1

print()
print("=" * 70)
print(f"RESULTS: {passed}/{len(tests)} tests passed")
print("=" * 70)

if failed > 0:
    print("\nErrors:")
    for name, error in errors:
        print(f"  - {name}: {error}")
else:
    print("\n🎉 ALL TESTS PASSED!")

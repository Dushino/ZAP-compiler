#!/usr/bin/env python3
"""
Test function features to identify what's missing
"""

from parser import Parser
from compiler_pipeline import compile_program

def test_case(name, code, should_fail=False):
    """Test a single case"""
    try:
        parser = Parser(code, f"{name}.zap")
        program = parser.parse_program()
        result = compile_program(program)
        
        if should_fail:
            print(f"✗ {name}: FAIL (expected error but compiled)")
            return False
        else:
            print(f"✓ {name}: PASS")
            return True
    except Exception as e:
        if should_fail:
            print(f"✓ {name}: PASS (correctly failed)")
            return True
        else:
            error_str = str(e)[:150]
            print(f"✗ {name}: FAIL - {error_str}")
            return False

tests = [
    # Basic function tests
    ("1. Function return byte", """
func byte add_one(byte x)
    return x + 1
end

func byte unused()
    return 0
end

proc main()
    byte result = add_one(5)
end
""", False),

    ("2. Function return word", """
func word combine(byte low, byte high)
    return low
end

proc main()
    word result = combine(10, 20)
end
""", False),

    ("3. Function with multiple params", """
func byte max(byte a, byte b)
    if a > b then
        return a
    endif
    return b
end

proc main()
    byte result = max(10, 20)
end
""", False),

    # Struct return types
    ("4. Function return struct", """
struct Point
    byte x
    byte y
end

func Point create_point(byte x, byte y)
    Point p = { x, y }
    return p
end

proc main()
    Point p = create_point(5, 10)
end
""", False),

    # Struct parameters
    ("5. Function with struct parameter", """
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
""", False),

    # Pointer return types
    ("6. Function return pointer", """
byte data[] = { 1, 2, 3 }

func byte ^get_data()
    return @data
end

proc main()
    byte ^ptr = get_data()
end
""", False),

    # Struct pointer return
    ("7. Function return struct pointer", """
struct Point
    byte x
    byte y
end

Point points[10]

func Point ^get_point(byte idx)
    return @points[idx]
end

proc main()
    Point ^ptr = get_point(0)
end
""", False),

    # Function calling function
    ("8. Function calling function", """
func byte double(byte x)
    return x * 2
end

func byte quad(byte x)
    byte d = double(x)
    return double(d)
end

proc main()
    byte result = quad(5)
end
""", False),
]

print("=" * 70)
print("FUNCTION FEATURES TEST SUITE")
print("=" * 70)
print()

passed = 0
failed = 0

for name, code, should_fail in tests:
    success = test_case(name, code, should_fail)
    if success:
        passed += 1
    else:
        failed += 1

print()
print("=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 70)

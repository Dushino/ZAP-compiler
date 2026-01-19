#!/usr/bin/env python3
"""Comprehensive test suite for struct features"""

from parser import Parser
from compiler_pipeline import compile_program

def test_1_direct_struct():
    """Test direct struct instance field access and modification"""
    source = """
struct Point
    byte x
    byte y
end

proc main()
    Point p
    p.x = 10
    p.y = 20
end
"""
    try:
        parser = Parser(source, "Test1.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 1 (Direct Struct): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 1 (Direct Struct): FAIL - {e}")
        return False

def test_2_struct_array():
    """Test struct array with field access"""
    source = """
struct Rect
    byte width
    byte height
end

proc main()
    Rect rects[5]
    rects[0].width = 100
    rects[0].height = 200
    rects[4].width = 50
    rects[4].height = 75
end
"""
    try:
        parser = Parser(source, "Test2.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 2 (Struct Array): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 2 (Struct Array): FAIL - {e}")
        return False

def test_3_global_struct():
    """Test global struct instance with fixed address"""
    source = """
struct Config
    byte mode
    byte flags
end

Config cfg @40000

proc main()
    cfg.mode = 1
    cfg.flags = 0xFF
end
"""
    try:
        parser = Parser(source, "Test3.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 3 (Global Struct): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 3 (Global Struct): FAIL - {e}")
        return False

def test_4_const_array_size():
    """Test struct array with const size"""
    source = """
struct Point
    byte x
    byte y
end

const byte NUM_POINTS = 10

proc main()
    Point points[NUM_POINTS]
    points[0].x = 1
    points[9].y = 2
end
"""
    try:
        parser = Parser(source, "Test4.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 4 (Const Array Size): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 4 (Const Array Size): FAIL - {e}")
        return False

def test_5_multiple_struct_types():
    """Test multiple different struct types"""
    source = """
struct Position
    byte x
    byte y
end

struct Color
    byte r
    byte g
    byte b
end

proc main()
    Position pos
    Color col
    pos.x = 100
    col.r = 255
end
"""
    try:
        parser = Parser(source, "Test5.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 5 (Multiple Struct Types): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 5 (Multiple Struct Types): FAIL - {e}")
        return False

def test_6_struct_in_loop():
    """Test struct field access in a loop"""
    source = """
struct Data
    byte value
    byte counter
end

proc main()
    Data items[3]
    byte i
    
    for i = 0 to 3
        items[i].value = i
        items[i].counter = 0
    next i
end
"""
    try:
        parser = Parser(source, "Test6.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 6 (Struct in Loop): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 6 (Struct in Loop): FAIL - {e}")
        return False

def test_7_word_sized_struct():
    """Test struct with word-sized fields"""
    source = """
struct WordPair
    word low
    word high
end

proc main()
    WordPair wp
    wp.low = 1000
    wp.high = 2000
end
"""
    try:
        parser = Parser(source, "Test7.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 7 (Word-Sized Struct): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 7 (Word-Sized Struct): FAIL - {e}")
        return False

def test_8_mixed_struct_fields():
    """Test struct with mixed byte/word fields"""
    source = """
struct Mixed
    byte b1
    word w1
    byte b2
end

proc main()
    Mixed m
    m.b1 = 100
    m.w1 = 5000
    m.b2 = 50
end
"""
    try:
        parser = Parser(source, "Test8.zap")
        program = parser.parse_program()
        result = compile_program(program)
        print("✓ Test 8 (Mixed Struct Fields): PASS")
        return True
    except Exception as e:
        print(f"✗ Test 8 (Mixed Struct Fields): FAIL - {e}")
        return False

def main():
    print("=" * 70)
    print("COMPREHENSIVE STRUCT FEATURE TEST SUITE")
    print("=" * 70)
    print()
    
    tests = [
        test_1_direct_struct,
        test_2_struct_array,
        test_3_global_struct,
        test_4_const_array_size,
        test_5_multiple_struct_types,
        test_6_struct_in_loop,
        test_7_word_sized_struct,
        test_8_mixed_struct_fields,
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    if passed == total:
        print("✓ ALL TESTS PASSED!")
    else:
        print(f"✗ {total - passed} test(s) failed")
    print("=" * 70)

if __name__ == "__main__":
    main()

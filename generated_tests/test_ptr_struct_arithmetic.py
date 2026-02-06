#!/usr/bin/env python3
"""Test pointer arithmetic with struct sizes"""

from parser import Parser
from compiler_pipeline import compile_program
import re

def test_ptr_struct_basic():
    """Test basic pointer to struct and arithmetic"""
    code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[5]
    ^Point ptr
    ptr = @arr[0]
    arr[0].x = 10
    
    ptr = ptr + 1
    arr[1].x = 20
end
"""
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    # Basic sanity checks
    assert isinstance(asm, str) and len(asm) > 0, "No assembly generated for basic pointer struct"

def test_ptr_arithmetic():
    """Test pointer arithmetic with structs"""
    code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[3]
    ^Point ptr
    ptr = @arr[0]
    ptr = ptr + 1
    ptr = ptr + 1
end
"""
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    # Verify some arithmetic/shift ops are emitted (best-effort check)
    assert any(k in asm for k in ("ASL", "LSL", "CLC", "ADC")), "Pointer arithmetic did not generate expected operations"

def test_ptr_struct_member():
    """Test pointer as struct member"""
    code = """
struct Node
    byte value
    ^Node link
end

proc main()
    Node n1
    Node n2
    
    n1.value = 10
    n1.link = @n2
    n2.value = 20
end
"""
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    # Check for Node symbol allocation (approximate)
    assert ("_MAIN_N1:" in asm and "_MAIN_N2:" in asm) or ("_MAIN_N1" in asm and "_MAIN_N2" in asm), "Expected Node allocations not found"

def test_self_referential():
    """Test self-referential struct (pointer to same type)"""
    code = """
struct Node
    byte data
    ^Node flink
    ^Node blink
end

proc main()
    Node node
    node.data = 42
    node.flink = @node
    node.blink = @node
end
"""
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    asm = compile_program(ast)
    assert isinstance(asm, str) and len(asm) > 0, "No assembly generated for self-referential struct"



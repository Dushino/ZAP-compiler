#!/usr/bin/env python3
"""Test array of pointers can be dereferenced"""

from parser import Parser
from compiler_pipeline import compile_program
from errors import SemanticError


def test_array_of_pointers_deref():
    code = """
byte ^arr[2]
proc main()
    arr[0]^ = 1
end
"""
    try:
        parser = Parser(code, "test_arr_ptr.zap")
        ast = parser.parse_program()
        asm = compile_program(ast)
        print("[PASS] Array-of-pointers element dereference compiled successfully")
    except SemanticError as e:
        print("[FAIL] SemanticError:", e.message)
    except Exception as e:
        from errors import print_exception
        print_exception(e)


if __name__ == "__main__":
    test_array_of_pointers_deref()

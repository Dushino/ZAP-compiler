#!/usr/bin/env python3
"""Debug pointer arithmetic to understand use_inc_opt"""

import sys
from parser import Parser

code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[5]
    ^Point ptr
    ptr = @arr[0]
    ptr = ptr + 1
end
"""

try:
    parser = Parser(code, "test.zap")
    ast = parser.parse_program()
    
    # Find the main procedure (skip structs)
    main_proc = None
    for item in ast.procs:
        if hasattr(item, 'name') and item.name == 'MAIN':
            main_proc = item
            break
    
    if not main_proc:
        print("Could not find MAIN procedure")
        sys.exit(1)
    
    for i, stmt in enumerate(main_proc.body):
        print(f"  Statement {i}: {type(stmt).__name__}")
        print(f"    Stmt: {stmt}")
        print(f"    Dir: {[x for x in dir(stmt) if not x.startswith('_')]}")
        if i == 1:  # The ptr = ptr + 1 statement
            print("  ---DEEP DIVE INTO STMT 1---")
            print(f"    target: {stmt.target}")
            print(f"    value: {stmt.value}")
            print(f"    value type: {type(stmt.value).__name__}")
            expr = stmt.value
            print(f"    expr.left: {expr.left}")
            print(f"    expr.right: {expr.right}")
            print(f"    expr.right type: {type(expr.right).__name__}")
            if hasattr(expr.right, 'value'):
                print(f"    expr.right.value: {expr.right.value}")
                    
except Exception as e:
    from errors import print_exception
    print_exception(e, filename='test.zap')

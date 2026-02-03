#!/usr/bin/env python3
"""
Test struct parsing and semantic analysis
"""

from parser import Parser
from compiler_pipeline import compile_program

test_code = """
struct Point
    byte x
    byte y
end

struct Rect
    byte top
    byte left
    byte width
    byte height
end

byte global_var = 10

proc main()
end
"""

print("=" * 60)
print("STRUCT PARSING TEST")
print("=" * 60)

try:
    # Parse
    parser = Parser(test_code, "test_struct.zap")
    ast = parser.parse_program()
    print("✓ Parsing succeeded!")
    print(f"✓ Parsed {len(ast.decls)} declarations")
    print(f"✓ Parsed {len(ast.procs)} procedures/structs")
    
    # Show what was parsed
    for proc in ast.procs:
        print(f"  - {type(proc).__name__}: {getattr(proc, 'name', 'unnamed')}")
        if hasattr(proc, 'fields'):
            for field in proc.fields:
                print(f"    - {field.name}: {field.type}")
    
    print("\n" + "=" * 60)
    print("STRUCT SEMANTIC ANALYSIS TEST")
    print("=" * 60)
    
    # Compile (semantic analysis)
    try:
        asm = compile_program(ast)
        print("✓ Compilation succeeded!")
        print(f"✓ Generated {len(asm.splitlines())} lines of assembly")
    except Exception as e:
        from errors import print_exception
        print_exception(e)
        
except Exception as e:
    from errors import print_exception
    print_exception(e)


from parser import Parser
from compiler_pipeline import compile_program
from sema_expr import ExprTypeChecker

code = """
struct Point
    byte x
    byte y
end

proc main()
    Point arr[3]
    arr[0].x = 1
end
"""

parser = Parser(code, "test.zap")
ast = parser.parse_program()

print("Parsed successfully")
print(f"Structs defined: {parser.struct_names}")
print(f"Global symbols: {list(ast.decls)}")

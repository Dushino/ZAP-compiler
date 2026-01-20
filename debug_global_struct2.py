#!/usr/bin/env python3

from parser import Parser
from compiler_pipeline import compile_program
from sema import DeclarationAnalyzer, StructAnalyzer
from symbols import SymbolTable, StructRegistry
from ast_nodes import StructDef

code = """
struct Point
    byte x
    byte y
end

Point global_pt

proc main()
    global_pt.x = 1
    global_pt.y = 2
end
"""

parser = Parser(code, "test.zap")
ast = parser.parse_program()

print("=" * 70)
print("PARSING RESULTS:")
print(f"Declarations: {len(ast.decls)}")
for d in ast.decls:
    print(f"  {d}")

print(f"\nProcedures: {len(ast.procs)}")
for p in ast.procs:
    print(f"  {p}")

# Now test semantic analysis
print("\n" + "=" * 70)
print("SEMANTIC ANALYSIS:")

global_symtab = SymbolTable()
struct_registry = StructRegistry()

# Analyze structs first
struct_an = StructAnalyzer(struct_registry)
for item in ast.procs:
    if isinstance(item, StructDef):
        struct_an.analyze(item)
        print(f"Registered struct: {item.name}")

# Analyze declarations
print(f"\nAnalyzing {len(ast.decls)} global declarations...")
decl_an = DeclarationAnalyzer(global_symtab, struct_registry)
for d in ast.decls:
    print(f"  Analyzing: {d}")
    decl_an.analyze(d)

print(f"\nGlobal symbol table after declarations:")
for name, sym in global_symtab._symbols.items():
    print(f"  {name}: {sym}")

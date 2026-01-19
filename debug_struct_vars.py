#!/usr/bin/env python3
"""Debug struct variable registration"""

from parser import Parser
from sema import DeclarationAnalyzer
from symbols import SymbolTable, StructRegistry
from sema_proc import ProcAnalyzer
from symbols import ProcTable

code = '''
struct Point
    byte x
    byte y
end

proc main()
    Point pt
end
'''

# Parse
parser = Parser(code, 'test.zap')
ast = parser.parse_program()
print("Parsed successfully")

# Create struct registry and analyze structs
struct_registry = StructRegistry()
from sema import StructAnalyzer
struct_an = StructAnalyzer(struct_registry)
for item in ast.procs:
    from ast_nodes import StructDef
    if isinstance(item, StructDef):
        struct_an.analyze(item)

print(f"Registered structs: {list(struct_registry._structs.keys())}")

# Analyze procedures
global_symtab = SymbolTable()
proc_table = ProcTable()
proc_an = ProcAnalyzer(proc_table, struct_registry=struct_registry)

from ast_nodes import ProcDecl
for item in ast.procs:
    if isinstance(item, ProcDecl):
        proc_an.analyze_decl(item)
        analyzed = proc_an.analyze_proc(item, global_symtab)
        print(f"Procedure {item.name}:")
        print(f"  Locals: {[sym.name for sym in analyzed.locals]}")
        try:
            pt_sym = analyzed.symtab.lookup('PT')
            print(f"  PT lookup: Found - {pt_sym}")
        except KeyError:
            print(f"  PT lookup: Not found")

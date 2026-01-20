#!/usr/bin/env python3

from parser import Parser
from compiler_pipeline import compile_program
from sema import DeclarationAnalyzer, StructAnalyzer
from sema_proc import ProcAnalyzer
from symbols import SymbolTable, StructRegistry, ProcTable, ScopedSymbolTable
from ast_nodes import StructDef, ProcDecl

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

# Setup
global_symtab = SymbolTable()
proc_table = ProcTable()
struct_registry = StructRegistry()

# Analyze structs
struct_an = StructAnalyzer(struct_registry)
for item in ast.procs:
    if isinstance(item, StructDef):
        struct_an.analyze(item)

# Analyze global declarations
decl_an = DeclarationAnalyzer(global_symtab, struct_registry)
for d in ast.decls:
    decl_an.analyze(d)

print("Global symbol table:")
for name, sym in global_symtab._symbols.items():
    print(f"  {name}: {sym.type}")

# Analyze procedures
proc_an = ProcAnalyzer(proc_table, struct_registry=struct_registry)

# First pass: register proc signatures
for p in ast.procs:
    if isinstance(p, ProcDecl):
        proc_an.analyze_decl(p)

# Analyze main proc
main_proc = next((p for p in ast.procs if isinstance(p, ProcDecl) and p.name == 'MAIN'), None)
if main_proc:
    analyzed_main = proc_an.analyze_proc(main_proc, global_symtab)
    
    print(f"\nMain procedure symbol table type: {type(analyzed_main.symtab)}")
    print(f"Is ScopedSymbolTable: {isinstance(analyzed_main.symtab, ScopedSymbolTable)}")
    
    if isinstance(analyzed_main.symtab, ScopedSymbolTable):
        print(f"  Parent symtab: {type(analyzed_main.symtab.parent)}")
        print(f"  Local symtab: {type(analyzed_main.symtab.local)}")
        
        # Try to lookup global_pt
        try:
            sym = analyzed_main.symtab.lookup('GLOBAL_PT')
            print(f"\n✅ Successfully looked up GLOBAL_PT: {sym.type}")
        except KeyError as e:
            print(f"\n❌ Failed to lookup GLOBAL_PT: {e}")

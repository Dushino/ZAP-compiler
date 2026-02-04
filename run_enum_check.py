from parser import Parser
from sema import EnumAnalyzer, DeclarationAnalyzer
from symbols import SymbolTable
from ast_nodes import EnumDecl

s='enum Colors { RED, GREEN, BLUE }\nbyte x = GREEN\nproc main()\nend\n'
print('Parsing...')
p=Parser(s)
prog=p.parse_program()
print('Parsed decls:', [type(d).__name__ for d in prog.decls])

symtab = SymbolTable()
enum_an = EnumAnalyzer(symtab)
decl_an = DeclarationAnalyzer(symtab)
# analyze enums
for d in prog.decls:
    if isinstance(d, EnumDecl):
        print('Analyzing enum', d.name)
        enum_an.analyze(d)
# analyze decls
for d in prog.decls:
    if isinstance(d, EnumDecl):
        continue
    print('Analyzing decl', type(d).__name__)
    decl_an.analyze(d)

print('Symbols:')
for name, sym in symtab._symbols.items():
    print(name, sym.const_value)
print('OK')
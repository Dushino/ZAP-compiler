from parser import Parser
from sema import EnumAnalyzer
from sema import DeclarationAnalyzer
from symbols import SymbolTable
from ast_nodes import EnumDecl


def analyze_program(src):
    p = Parser(src, filename='<test>')
    prog = p.parse_program()
    symtab = SymbolTable()
    enum_an = EnumAnalyzer(symtab)
    decl_an = DeclarationAnalyzer(symtab)
    # Run enum analyzer
    for d in prog.decls:
        if isinstance(d, EnumDecl):
            enum_an.analyze(d)
    # Run declarations
    for d in prog.decls:
        if isinstance(d, EnumDecl):
            continue
        decl_an.analyze(d)
    return symtab

src = 'enum Colors { RED, GREEN, BLUE }\nbyte x = GREEN\nproc main()\nend\n'
s = analyze_program(src)
print('RED=', s._symbols['RED'].const_value)
print('GREEN=', s._symbols['GREEN'].const_value)
print('BLUE=', s._symbols['BLUE'].const_value)
print('x exists:', 'x' in s._symbols)
print('OK')

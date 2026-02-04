import pytest
from parser import Parser
from sema import EnumAnalyzer
from sema import DeclarationAnalyzer
from symbols import SymbolTable
from errors import SemanticError
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


def test_enum_basic():
    src = 'enum Colors { RED, GREEN, BLUE }\nproc main()\nend\n'
    symtab = analyze_program(src)
    assert 'RED' in symtab._symbols
    assert symtab._symbols['RED'].const_value == 0
    assert symtab._symbols['GREEN'].const_value == 1
    assert symtab._symbols['BLUE'].const_value == 2


def test_enum_explicit_and_auto():
    src = 'enum Flags { A = 1, B, C = 4, D }\nproc main()\nend\n'
    symtab = analyze_program(src)
    assert symtab._symbols['A'].const_value == 1
    assert symtab._symbols['B'].const_value == 2
    assert symtab._symbols['C'].const_value == 4
    assert symtab._symbols['D'].const_value == 5


def test_enum_overflow():
    src = 'enum byte Big { V = 256 }\nproc main()\nend\n'
    with pytest.raises(SemanticError):
        analyze_program(src)


def test_enum_duplicate_member():
    src = 'enum E { A, A }\nproc main()\nend\n'
    with pytest.raises(SemanticError):
        analyze_program(src)


def test_enum_used_in_initializer():
    src = 'enum Colors { RED, GREEN }\nbyte x = GREEN\nproc main()\nend\n'
    symtab = analyze_program(src)
    assert 'GREEN' in symtab._symbols
    # declaration analyzer should accept using enum const in initializer
    assert symtab._symbols['x'].const_value is None  # x is not const
    # ensure GREEN value is available
    assert symtab._symbols['GREEN'].const_value == 1

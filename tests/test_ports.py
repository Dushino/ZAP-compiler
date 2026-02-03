import os
from parser import Parser
from compiler_pipeline import compile_program
from sema import SemanticError


def test_decl_modifier_port_parsed():
    src = 'byte x #PORT @$D200\nbyte y #PORT #RD @$D201\n'
    p = Parser(src, filename='<test>')
    prog = p.parse_program()
    decls = prog.decls
    assert any(getattr(d, 'is_port', False) for d in decls)
    # check RD/WR flags
    for d in decls:
        if d.declarators[0].name.upper() == 'Y':
            assert d.port_rd is True and d.port_wr is False


def test_port_requires_address():
    src = 'byte P #PORT\n'
    try:
        compile_program(Parser(src, filename='<test>').parse_program())
        assert False, "Expected SemanticError for PORT without @"
    except SemanticError as e:
        assert 'requires address' in e.message.lower() or 'requires address' in str(e).lower()


def test_port_cannot_be_const():
    src = 'const byte P #PORT @$D200\n'
    try:
        compile_program(Parser(src, filename='<test>').parse_program())
        assert False, "Expected SemanticError for CONST PORT"
    except SemanticError:
        pass


def test_port_cannot_be_static_local():
    src = 'proc p()\n    STATIC byte X #PORT @$D200\nend\n'
    try:
        compile_program(Parser(src, filename='<test>').parse_program())
        assert False, "Expected SemanticError for STATIC PORT"
    except SemanticError:
        pass


def test_rd_wr_enforcement():
    src = '.module "m"\nbyte DATA #PORT #RD @$D200\nproc writer()\n    DATA = 5\nend\nproc MAIN()\nend\n'
    try:
        compile_program(Parser(src, filename='<test>').parse_program())
        assert False, "Expected SemanticError for writing to #RD-only port"
    except SemanticError:
        pass

    # #WR only - read should fail
    src2 = 'byte DATA2 #PORT #WR @$D210\nproc reader()\n    byte a = DATA2\nend\nproc MAIN()\nend\n'
    try:
        compile_program(Parser(src2, filename='<test>').parse_program())
        assert False, "Expected SemanticError for reading from #WR-only port"
    except SemanticError:
        pass

    # #RD without #PORT is an error
    src3 = 'byte BAD @$D300 #RD\n'
    try:
        compile_program(Parser(src3, filename='<test>').parse_program())
        assert False, "Expected SemanticError for #RD without #PORT"
    except SemanticError:
        pass


def test_rd_write_ok_when_both_or_unspecified():
    # No RD/WR specified -> both allowed
    src = 'byte P #PORT @$D200\nproc p()\n    byte a = P\n    P = 1\nend\n'
    compile_program(Parser(src, filename='<test>').parse_program())

    # Both RD and WR specified explicitly
    src2 = 'byte Q #PORT #RD #WR @$D201\nproc p2()\n    byte a = Q\n    Q = 3\nend\n'
    compile_program(Parser(src2, filename='<test>').parse_program())

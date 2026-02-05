from parser import Parser
from symbols import SymbolTable
from sema import StructAnalyzer, DeclarationAnalyzer
from symbols import StructRegistry
from ast_nodes import StructDef

src = open('tests/pass/130-struct-field-pass/130-struct-field-pass.zap','r', encoding='utf-8').read()
parser = Parser(src, filename='test.zap')
program = parser.parse_program()
struct_reg = StructRegistry()
str_an = StructAnalyzer(struct_reg)
for item in program.decls:
    if isinstance(item, StructDef):
        str_an.analyze(item)
# Build global symtab
symtab = SymbolTable()
decl_an = DeclarationAnalyzer(symtab, struct_reg)
for item in program.decls:
    if not isinstance(item, StructDef):
        decl_an.analyze(item)
# print VIA1 symbol
try:
    s = symtab.lookup('VIA1')
    print('VIA1:', s.name, 'is_port', s.is_port, 'port_rd', s.port_rd, 'port_wr', s.port_wr)
    # print struct field infos
    si = s.type.struct_info
    print('Struct defaults:', si.is_port_default, si.port_rd_default, si.port_wr_default)
    for f in si.fields:
        print('Field:', f.name, 'port_rd', f.port_rd, 'port_wr', f.port_wr)
except Exception as e:
    print('lookup error', e)

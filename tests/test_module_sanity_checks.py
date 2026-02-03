import os
from module_system import ModuleSystem
from compiler import compile_file
from errors import SemanticError


def test_module_name_must_be_quoted(tmp_path):
    p = tmp_path / "badmod.zap"
    p.write_text('.module m\nbyte a\n')
    ms = ModuleSystem(base_path=os.getcwd())
    try:
        ms.build_program(str(p))
        assert False, "Expected exception for unquoted module name"
    except SemanticError as e:
        assert "module name must be enclosed" in e.message.lower()


def test_proc_main_not_allowed_in_module(tmp_path):
    p = tmp_path / "m.zap"
    p.write_text('.module "m"\nproc main()\nend\n')
    ms = ModuleSystem(base_path=os.getcwd())
    try:
        ms.build_program(str(p))
        assert False, "Expected exception for PROC MAIN in module"
    except SemanticError as e:
        assert "main" in e.message.lower()


def test_duplicate_module_name_detected(tmp_path):
    a = tmp_path / "a.zap"
    b = tmp_path / "b.zap"
    main = tmp_path / "main.zap"
    a.write_text('.module "dup"\nbyte a\n')
    b.write_text('.module "dup"\nbyte b\n')
    main.write_text('.include "a.zap"\n.include "b.zap"\n')
    ms = ModuleSystem(base_path=os.getcwd())
    try:
        ms.build_program(str(main))
        assert False, "Expected exception for duplicate module name"
    except SemanticError as e:
        assert "duplicate module name" in e.message.lower()

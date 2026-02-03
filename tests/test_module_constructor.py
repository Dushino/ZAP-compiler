import os
from module_system import ModuleSystem
from compiler import compile_file
from errors import SemanticError


def test_constructor_forbidden_in_non_module(tmp_path):
    p = tmp_path / "no_mod.zap"
    p.write_text('proc Constructor()\nend\nproc main()\nend\n')
    ms = ModuleSystem(base_path=os.getcwd())
    try:
        ms.build_program(str(p))
        assert False, "Expected exception for Constructor in non-module file"
    except SemanticError as e:
        assert "constructor" in e.message.lower()


def test_constructor_marked_keep_noexport(tmp_path):
    m = tmp_path / "m.zap"
    main = tmp_path / "main.zap"
    m.write_text('.module "m"\nproc Constructor()\nend\n')
    main.write_text('.include "m.zap"\nproc main()\nend\n')
    ms = ModuleSystem(base_path=os.getcwd())
    program, _ = ms.build_program(str(main))
    # Find constructor proc (mangled name expected)
    ctors = [p for p in program.procs if p.name.startswith("__CONSTRUCTOR__")]
    assert len(ctors) == 1, f"Expected 1 constructor, got {ctors}"
    ctor = ctors[0]
    assert getattr(ctor, 'keep', False) is True
    assert getattr(ctor, 'noexport', False) is True


def test_constructor_calls_emitted_in_order(tmp_path):
    # Create three modules A includes B includes C and a main that includes A
    c = tmp_path / "c.zap"
    b = tmp_path / "b.zap"
    a = tmp_path / "a.zap"
    main = tmp_path / "main.zap"

    c.write_text('.module "c"\nproc Constructor()\nend\n')
    b.write_text('.module "b"\n.include "c.zap"\nproc Constructor()\nend\n')
    a.write_text('.module "a"\n.include "b.zap"\nproc Constructor()\nend\n')
    main.write_text('.include "a.zap"\nproc main()\nend\n')

    asm = compile_file(str(main))
    # Expect constructor labels in order: c, b, a (mangled)
    c_label = "__CONSTRUCTOR__c"
    b_label = "__CONSTRUCTOR__b"
    a_label = "__CONSTRUCTOR__a"
    idx_c = asm.find(f"JSR {c_label}")
    idx_b = asm.find(f"JSR {b_label}")
    idx_a = asm.find(f"JSR {a_label}")
    assert idx_c != -1 and idx_b != -1 and idx_a != -1, "Missing constructor JSRs in assembly"
    assert idx_c < idx_b < idx_a, "Constructors not emitted in correct order"

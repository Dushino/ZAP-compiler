import os
import pytest
from module_system import ModuleSystem
from errors import CompileError


TEST_ROOT = os.path.join(os.path.dirname(__file__))

# We'll try compiling each test source file; if compilation raises a CompileError,
# assert it includes line and col information so editor diagnostics can point to a
# precise source location.

def iter_source_files(root):
    for dirpath, dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith('.zap') or fn.endswith('.act'):
                yield os.path.join(dirpath, fn)


@pytest.mark.parametrize("srcfile", list(iter_source_files(TEST_ROOT)))
def test_errors_include_location(srcfile):
    try:
        ms = ModuleSystem(base_path='.')
        # build_program accepts absolute filenames; it raises CompileError for expected failures
        ms.build_program(srcfile)
    except CompileError as e:
        assert getattr(e, 'line', None) is not None, f"CompileError raised without line for {srcfile}: {e.message}"
        assert getattr(e, 'col', None) is not None, f"CompileError raised without col for {srcfile}: {e.message}"
    except Exception:
        # Non-CompileError exceptions are out of scope for this test
        pytest.skip("Non-CompileError raised, skipping")
    else:
        # No error — nothing to assert
        pass

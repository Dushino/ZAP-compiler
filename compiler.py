from errors import CompileError, print_error
from parser import Parser
from compiler_pipeline import compile_program
import compiler_pipeline as cp
from module_system import ModuleSystem
from preprocessor import Preprocessor
import os
import sys
from typing import Optional, Set

def compile_source(src: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None) -> str:
    # Strip UTF-8 BOM if present
    if src.startswith('\ufeff'):
        src = src[1:]

    try:
        # Apply preprocessor
        preprocessor = Preprocessor(predefined_symbols)
        src = preprocessor.process(src)
        
        parser = Parser(src, filename="<input.zap>")
        program = parser.parse_program()
        return compile_program(program, target_6502=target_6502, command_line=command_line)

    except CompileError as e:
        if e.line is not None:
            print_error(src, e.line, e.col, e.message)
        else:
            print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)


def compile_file(filepath: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None) -> str:
    """Compile a file with module support"""
    try:
        # Get base directory for resolving includes
        base_dir = os.path.dirname(os.path.abspath(filepath))
        
        # Create module system
        module_sys = ModuleSystem(base_dir, predefined_symbols=predefined_symbols)
        
        # Build program with all dependencies
        program = module_sys.build_program(filepath)
        
        # Compile the complete program
        return compile_program(program, target_6502=target_6502, command_line=command_line)
    
    except CompileError as e:
        # Prefer attached source text (e.g., preprocessed/cleaned) if available
        src = getattr(e, "source_text", None)
        if src is None:
            # Fallback: read original file
            try:
                with open(filepath, encoding='utf-8-sig') as f:
                    src = f.read()
            except Exception:
                src = None
        if e.line is not None and src is not None:
            print_error(src, e.line, e.col, e.message)
        else:
            print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import sys
    
    command_line = " ".join([sys.executable] + sys.argv)
    args = sys.argv[1:]
    target_6502 = False
    out_file = None
    enable_peepholes = False
    predefined_symbols = set()

    # Simple CLI parsing to support -6502, -o <file>, and -D <symbol>
    i = 0
    src_file = None
    while i < len(args):
        a = args[i]
        if a == "-6502":
            target_6502 = True
            i += 1
            continue
        if a == "--peepholes":
            enable_peepholes = True
            i += 1
            continue
        if a == "-o":
            if i + 1 >= len(args):
                print("Error: -o requires an output filename")
                print("Usage: python compiler.py [-6502] [--peepholes] [-D <symbol>] [-o <output.s>] <source.act>")
                sys.exit(1)
            out_file = args[i + 1]
            i += 2
            continue
        if a == "-D":
            if i + 1 >= len(args):
                print("Error: -D requires a symbol name")
                print("Usage: python compiler.py [-6502] [--peepholes] [-D <symbol>] [-o <output.s>] <source.act>")
                sys.exit(1)
            predefined_symbols.add(args[i + 1].upper())
            i += 2
            continue
        # First non-option is the source file
        if src_file is None:
            src_file = a
        else:
            # Ignore extra args for now
            pass
        i += 1

    if src_file is None:
        print("Usage: python compiler.py [-6502] [--peepholes] [-D <symbol>] [-o <output.s>] <source.act>")
        sys.exit(1)

    # Configure peephole optimizations toggle in pipeline
    cp.DISABLE_PEEPHOLE_OPTIMIZATIONS = not enable_peepholes

    # Compile program
    output = compile_file(
        src_file,
        target_6502=target_6502,
        predefined_symbols=predefined_symbols,
        command_line=command_line,
    )

    # Write to file if requested, else print to stdout
    if out_file:
        # Ensure parent directory exists (Makefile creates it; be safe here too)
        out_dir = os.path.dirname(os.path.abspath(out_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


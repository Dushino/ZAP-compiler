from errors import CompileError, print_error, print_exception
from parser import Parser
from compiler_pipeline import compile_program
from module_system import ModuleSystem
from preprocessor import Preprocessor
import os
import sys
from typing import Optional, Set, List

def compile_source(src: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None) -> str:
    # Strip UTF-8 BOM if present
    if src.startswith('\ufeff'):
        src = src[1:]

    try:
        # Apply preprocessor
        preprocessor = Preprocessor(predefined_symbols)
        src, defined_symbols = preprocessor.process(src)
        
        parser = Parser(src, filename="<input.zap>")
        program = parser.parse_program()
        return compile_program(program, target_6502=target_6502, command_line=command_line, defined_symbols=defined_symbols)

    except CompileError as e:
        if e.line is not None:
            # Prefer attached source text if provided
            src_text = e.source_text or src
            fname = getattr(e, "filename", None) or getattr(parser, "filename", None)
            print_error(src_text, e.line, e.col, e.message, filename=fname, severity="error")
        else:
            print_exception(e, filename=getattr(parser, "filename", None))
        sys.exit(1)


def compile_file(filepath: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None, include_dirs: Optional[List[str]] = None) -> str:
    """Compile a file with module support"""
    try:
        # Get base directory for resolving includes
        base_dir = os.path.dirname(os.path.abspath(filepath))
        
        # Create module system with include directories
        module_sys = ModuleSystem(base_dir, predefined_symbols=predefined_symbols, include_dirs=include_dirs or [])
        
        # Build program with all dependencies
        program, defined_symbols = module_sys.build_program(filepath)
        
        # Compile the complete program
        return compile_program(program, target_6502=target_6502, command_line=command_line, defined_symbols=defined_symbols)
    
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
            fname = getattr(e, "filename", None) or filepath
            print_error(src, e.line, e.col, e.message, filename=fname, severity="error")
        else:
            print_exception(e, filename=filepath)
        sys.exit(1)


if __name__ == "__main__":
    try:
        import sys
        
        command_line = " ".join([sys.executable] + sys.argv)
        args = sys.argv[1:]
        target_6502 = False
        out_file = None
        predefined_symbols = set()
        include_dirs = []

        # Simple CLI parsing to support -6502, -o <file>, -D <symbol>, and -I <directory>
        i = 0
        src_file = None
        while i < len(args):
            a = args[i]
            if a == "-6502":
                target_6502 = True
                i += 1
                continue
            if a == "-o":
                if i + 1 >= len(args):
                    print("<cli>:1:1: error: -o requires an output filename", file=sys.stderr)
                    print("Usage: zapc [-6502] [-D <symbol>] [-I <directory>] [-o <output.s>] <source.act>")
                    sys.exit(1)
                out_file = args[i + 1]
                i += 2
                continue
            if a == "-D":
                if i + 1 >= len(args):
                    print("<cli>:1:1: error: -D requires a symbol name", file=sys.stderr)
                    print("Usage: zapc [-6502] [-D <symbol>] [-I <directory>] [-o <output.s>] <source.act>")
                    sys.exit(1)
                predefined_symbols.add(args[i + 1].upper())
                i += 2
                continue
            if a == "-I":
                if i + 1 >= len(args):
                    print("<cli>:1:1: error: -I requires a directory path", file=sys.stderr)
                    print("Usage: zapc [-6502] [-D <symbol>] [-I <directory>] [-o <output.s>] <source.act>")
                    sys.exit(1)
                include_dirs.append(args[i + 1])
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
            print("Usage: zapc [-6502] [-D <symbol>] [-I <directory>] [-o <output.s>] <source.act>")
            sys.exit(1)

        if target_6502:
            predefined_symbols.add("6502")
        else:
            predefined_symbols.add("65C02")

        # Compile program
        output = compile_file(
            src_file,
            target_6502=target_6502,
            predefined_symbols=predefined_symbols,
            command_line=command_line,
            include_dirs=include_dirs,
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
    except Exception as e:
        # Catch unexpected exceptions and print a single-line error without traceback
        from errors import print_exception
        print_exception(e, filename=src_file if 'src_file' in locals() else None)
        sys.exit(1)


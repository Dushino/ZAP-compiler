from errors import CompileError, print_error, print_exception
from parser import Parser
from compiler_pipeline import compile_program
from module_system import ModuleSystem
from preprocessor import Preprocessor
import os
import os
import sys
from version import __version__
from typing import Optional, Set, List

def compile_source(src: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None, enable_peephole: bool = False) -> str:
    """Compile ZAP source text to assembly output."""
    # Strip UTF-8 BOM if present
    if src.startswith('\ufeff'):
        src = src[1:]

    # Ensure parser filename is defined even if exceptions occur before parser construction
    parser_filename = None

    try:
        # Apply preprocessor
        preprocessor = Preprocessor(predefined_symbols)
        src, defined_symbols = preprocessor.process(src)
        
        parser = Parser(src, filename="<input.zap>")
        parser_filename = getattr(parser, "filename", None)
        program = parser.parse_program()
        return compile_program(program, target_6502=target_6502, command_line=command_line, defined_symbols=defined_symbols, enable_peephole=enable_peephole)

    except CompileError as e:
        if e.line is not None:
            # Prefer attached source text if provided
            src_text = e.source_text or src
            # Prefer filename attached to the error; otherwise fall back to the parser if available
            fname = getattr(e, "filename", None) or parser_filename
            print_error(src_text, e.line, e.col, e.message, filename=fname, severity="error")
        else:
            print_exception(e, filename=parser_filename)
        sys.exit(1)
        return ""


def compile_file(filepath: str, *, target_6502: bool = False, predefined_symbols: Optional[Set[str]] = None, command_line: Optional[str] = None, include_dirs: Optional[List[str]] = None, enable_peephole: bool = False) -> str:
    """Compile a source file with module resolution enabled."""
    try:
        # Get base directory for resolving includes
        base_dir = os.path.dirname(os.path.abspath(filepath))
        
        # Create module system with include directories
        module_sys = ModuleSystem(base_dir, predefined_symbols=predefined_symbols, include_dirs=include_dirs or [])
        
        # Build program with all dependencies
        program, defined_symbols = module_sys.build_program(filepath)
        
        # Compile the complete program
        return compile_program(program, target_6502=target_6502, command_line=command_line, defined_symbols=defined_symbols, enable_peephole=enable_peephole)
    
    except CompileError as e:
        # If we have the parsed/linked program available, attempt to remap the
        # error (which carries cleaned-source line numbers) back to the original
        # source file/line using per-file mappings collected by ModuleSystem.
        try:
            program_local = locals().get("program")
            dbg = program_local.debug if program_local and getattr(program_local, 'debug', None) else {}
            file_lines = dbg.get('file_lines', {}) or {}
            per_file_stmt_pos = dbg.get('per_file_stmt_pos', {}) or {}
            orig_map_per_file = dbg.get('orig_line_map_per_file', {}) or {}
            orig_src_per_file = dbg.get('orig_source_lines_per_file', {}) or {}

            mapped = False
            # If error already names a file and mapping exists, remap
            if getattr(e, 'filename', None) and getattr(e, 'line', None) and e.filename in orig_map_per_file:
                omap = orig_map_per_file.get(e.filename)
                ln = getattr(e, 'line', None)
                # Ensure ln and omap are valid before indexing
                if ln is not None and omap is not None and 1 <= ln <= len(omap):
                    e.line = omap[ln - 1]
                    e.source_text = "\n".join(orig_src_per_file.get(e.filename, []))
                    mapped = True

                # Try to find a file whose cleaned source contains a matching stmt position
                if not mapped and (getattr(e, 'line', None) is not None):
                    clen = getattr(e, 'line', None)
                    ccol = getattr(e, 'col', None)
                    for fname, positions in per_file_stmt_pos.items():
                        for (pln, pcol, _text) in positions:
                            # Ensure cleaned line is valid before comparing
                            if clen is not None and pln == clen and (ccol is None or pcol == ccol):
                                omap = orig_map_per_file.get(fname)
                                # Ensure we have an original-map to index into
                                if omap is not None and clen is not None and 1 <= clen <= len(omap):
                                    e.line = omap[clen - 1]
                                    e.filename = fname
                                    e.source_text = "\n".join(orig_src_per_file.get(fname, []))
                                else:
                                    e.filename = fname
                                    e.source_text = "\n".join(file_lines.get(fname, []) or [])
                                mapped = True
                                break
                        if mapped:
                            break

                # Fallback: guess by inclusion (cleaned-line <= file length)
                if not mapped and (getattr(e, 'line', None) is not None):
                    clen = getattr(e, 'line', None)
                    for fname, lines in file_lines.items():
                        if clen is not None and clen <= len(lines or []):
                            omap = orig_map_per_file.get(fname)
                            if omap is not None and clen is not None and 1 <= clen <= len(omap):
                                e.line = omap[clen - 1]
                                e.filename = fname
                                e.source_text = "\n".join(orig_src_per_file.get(fname, []))
                            else:
                                e.filename = fname
                                e.source_text = "\n".join(lines or [])
                            mapped = True
                            break
        except Exception:
            # Keep original error if remapping fails
            pass

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
        enable_peephole = False

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
            if a == "--version":
                print(f"zapc {__version__}")
                sys.exit(0)
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
            if a == "-O1":
                enable_peephole = True
                i += 1
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
            enable_peephole=enable_peephole,
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
        filename = globals().get('src_file', None)
        print_exception(e, filename=filename)
        sys.exit(1)


"""
Module system for handling .module and .include directives
"""
import os
from dataclasses import dataclass
from typing import Dict, Set, Optional, List, NoReturn, cast
from parser import Parser
from ast_nodes import Program, Declaration, ProcDecl, FuncDecl
from preprocessor import Preprocessor
from errors import SemanticError


@dataclass
class ModuleInfo:
    """Information about a parsed module"""
    filepath: str
    is_module: bool  # Has .module directive
    module_name: Optional[str]
    declarations: list[Declaration]
    procedures: list[ProcDecl]
    functions: list[FuncDecl]
    # Preserve original top-level items order (procs, funcs, directives)
    top_level_items: list
    includes: list[str]  # List of included module names
    defined_symbols: Optional[Set[str]] = None  # Preprocessor .define symbols
    program: Program | None = None


class ModuleSystem:
    """
    Manages module loading and dependency resolution
    """
    
    def __init__(self, base_path: str = ".", predefined_symbols: Optional[Set[str]] = None, include_dirs: Optional[List[str]] = None) -> None:
        """Initialize module resolution with base path and include dirs."""
        self.base_path: str = os.path.abspath(base_path)
        self.loaded_modules: Dict[str, ModuleInfo] = {}
        self.include_stack: list[str] = []  # For circular dependency detection
        self.preprocessor = Preprocessor(predefined_symbols)  # Shared preprocessor for all modules
        # Normalize include directory paths
        # Note: include_dirs are relative to the current working directory, not base_path
        if include_dirs is None:
            # Provide a sensible default for common workspace layout: search 'work/lib' under base_path
            default_lib: str = os.path.join(self.base_path, 'work', 'lib')
            if os.path.isdir(default_lib):
                self.include_dirs: List[str] = [os.path.abspath(default_lib)]
            else:
                self.include_dirs = []
        else:
            self.include_dirs: List[str] = [os.path.abspath(d) for d in include_dirs]
        # Map module names to their defining file path to detect duplicates
        self.module_name_to_path: Dict[str, str] = {}
    
    def parse_file(self, filepath: str):
        """Parse a single file and extract module directives"""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            raw_source: str = f.read()
        
        # Strip UTF-8 BOM if present from raw source
        if raw_source.startswith('\ufeff'):
            raw_source = raw_source[1:]
        
        # Apply preprocessor (handles .ifdef, .ifndef, .else, .endif, .define, .undef)
        # If this file appears to be for a specific platform library (e.g., 'lib/atari'),
        # temporarily define the platform symbol so library-internal conditional blocks
        # (like .ifdef ATARI) are included for parsing and diagnostics.
        platform_symbol_added = None
        try:
            path_parts = os.path.normpath(filepath).split(os.sep)
            # Detect patterns like .../lib/atari/... or .../work/lib/atari/...
            if 'lib' in path_parts:
                lib_idx = path_parts.index('lib')
                if lib_idx + 1 < len(path_parts):
                    platform = path_parts[lib_idx + 1]
                    if platform:
                        sym = platform.upper()
                        if sym not in self.preprocessor.defined_symbols:
                            self.preprocessor.defined_symbols.add(sym)
                            platform_symbol_added = sym
            processed_source, defined_symbols = self.preprocessor.process(raw_source)
        finally:
            # Restore previous preprocessor state to avoid side-effects
            if platform_symbol_added is not None:
                self.preprocessor.defined_symbols.discard(platform_symbol_added)
        
        # Extract module/include directives
        module_name: Optional[str] = None
        is_module: bool = False
        includes: list[str] = []
        # module_directive_info is either a tuple (line, col, text) or None
        module_directive_info: Optional[tuple[int, int, str]] = None
        include_directives: dict[str, tuple[int, int, str]] = {}
        
        orig_lines: List[str] = raw_source.split('\n')
        cleaned_lines: list[str] = []
        cleaned_line_map: List[int] = []
        # Initialize loop variables so static analysis sees them as always defined
        ln: int = 0
        line: str = ""
        
        # If the preprocessor provided a list of kept original line numbers, iterate
        # over those so we can preserve original file line numbers for diagnostics.
        kept_line_nums = getattr(self.preprocessor, 'last_kept_line_numbers', None)
        if kept_line_nums is not None:
            # Iterate over original line numbers that were kept by the preprocessor
            for ln in kept_line_nums:
                line = orig_lines[ln-1]
                stripped: str = line.strip()
                lower_stripped: str = stripped.lower()
                if stripped.startswith('.module'):
                    # Extract module name from .module "filename" and validate quotes
                    is_module = True
                    # Find quotes in the original line to get accurate column
                    first_q: int = line.find('"')
                    if first_q == -1:
                        # No opening quote -> error
                        err = SemanticError("Invalid .module directive: module name must be enclosed in double quotes", line=ln, col=line.find('.module')+1)
                        err.filename = filepath
                        err.source_text = raw_source
                        raise err
                    second_q: int = line.find('"', first_q+1)
                    if second_q == -1:
                        # No closing quote -> error
                        err = SemanticError("Invalid .module directive: module name must be enclosed in double quotes", line=ln, col=first_q+1)
                        err.filename = filepath
                        err.source_text = raw_source
                        raise err
                    module_name = line[first_q+1:second_q]
                    module_directive_info = (ln, first_q+1, line)
                elif stripped.startswith('.include'):
                    # Extract include filename from .include "filename"
                    parts: List[str] = line.split('"')
                    if len(parts) >= 2:
                        inc_name = parts[1]
                        includes.append(inc_name)
                        # Record include directive location: name -> (line, col, text)
                        first_q = line.find('"')
                        if first_q != -1:
                            include_directives[inc_name] = (ln, first_q+1, line)
                else:
                    # Keep non-directive lines for parsing
                    cleaned_lines.append(line)
                    cleaned_line_map.append(ln)
        else:
            # Fallback: operate on the processed_source lines (no kept mapping available)
            lines: List[str] = processed_source.split('\n')
            for ln, line in enumerate(lines, start=1):
                stripped: str = line.strip()
                lower_stripped: str = stripped.lower()
                if stripped.startswith('.module'):
                    # Extract module name from .module "filename" and validate quotes
                    is_module = True
                    # Find quotes in the original line to get accurate column
                    first_q: int = line.find('"')
                    if first_q == -1:
                        # No opening quote -> error
                        err = SemanticError("Invalid .module directive: module name must be enclosed in double quotes", line=ln, col=line.find('.module')+1)
                        err.filename = filepath
                        err.source_text = processed_source
                        raise err
                    second_q: int = line.find('"', first_q+1)
                    if second_q == -1:
                        # No closing quote -> error
                        err = SemanticError("Invalid .module directive: module name must be enclosed in double quotes", line=ln, col=first_q+1)
                        err.filename = filepath
                        err.source_text = processed_source
                        raise err
                    module_name = line[first_q+1:second_q]
                    module_directive_info = (ln, first_q+1, line)
                elif stripped.startswith('.include'):
                    # Extract include filename from .include "filename"
                    # Capture the directive position so we can report errors at the include site
                    parts: List[str] = line.split('"')
                    if len(parts) >= 2:
                        inc_name = parts[1]
                        includes.append(inc_name)
                        # Record include directive location: name -> (line, col, text)
                        first_q = line.find('"')
                        if first_q != -1:
                            if 'include_directives' not in locals():
                                include_directives: dict[str, tuple[int, int, str]] = {}
                        include_directives[inc_name] = (ln, first_q+1, line)

            else:
                # Keep non-directive lines for parsing
                cleaned_lines.append(line)
                cleaned_line_map.append(ln)
        
        # Parse the cleaned source
        cleaned_source: str = '\n'.join(cleaned_lines)
        
        parser = Parser(cleaned_source, filename=filepath)
        try:
            program: Program = parser.parse_program()
        except Exception as e:
            # If parsing failed, prefer to report the location in the original file
            # (map cleaned-source line numbers back to original line numbers when possible)
            try:
                setattr(e, "filename", filepath)
            except Exception:
                pass

            # If we have a mapping from cleaned lines back to original lines, remap
            # the exception line number so diagnostics refer to the original source.
            try:
                if getattr(e, 'line', None) is not None and len(cleaned_line_map) > 0:
                    ln_opt = getattr(e, 'line', None)
                    if ln_opt is not None and 1 <= ln_opt <= len(cleaned_line_map):
                        # Narrow ln_opt to int for static type checkers before indexing
                        ln_i: int = cast(int, ln_opt)
                        orig_ln = cleaned_line_map[ln_i - 1]
                        try:
                            setattr(e, "line", orig_ln)
                        except Exception:
                            pass
                        # Use the raw (original) source text so error contexts show proper lines
                        try:
                            setattr(e, "source_text", raw_source)
                        except Exception:
                            pass
                    else:
                        # fallback to cleaned source if mapping is unavailable
                        try:
                            setattr(e, "source_text", cleaned_source)
                        except Exception:
                            pass
                else:
                    try:
                        setattr(e, "source_text", cleaned_source)
                    except Exception:
                        pass
            except Exception:
                # Swallow any error during remapping and re-raise the original exception
                try:
                    setattr(e, "source_text", cleaned_source)
                except Exception:
                    pass
            raise

        # Preserve mapping from cleaned source lines back to the original (pre-directive-removal) lines
        # so diagnostics coming from parser-produced debug info can be reported at the correct
        # locations in the original file.
        if program.debug is None:
            program.debug = {}
        program.debug['orig_line_map'] = cleaned_line_map
        # Save the original (raw) file lines so diagnostics can show original context
        program.debug['orig_source_lines'] = orig_lines
        # Save include directive positions (include name -> (line, col, text)) if any
        if 'include_directives' in locals():
            program.debug['include_directives'] = include_directives

        # Process compile-time diagnostics directives (.error/.warning/.info)
        from ast_nodes import ErrorDirective, WarningDirective, InfoDirective
        from errors import print_error
        new_procs = []
        for item in program.procs:
            if isinstance(item, ErrorDirective):
                err = SemanticError(item.message, line=getattr(item, 'line', None), col=getattr(item, 'col', None))
                err.filename = filepath
                err.source_text = cleaned_source
                raise err
            elif isinstance(item, WarningDirective):
                print_error(cleaned_source, getattr(item, 'line', 1), getattr(item, 'col', 1), item.message, filename=filepath, severity='warning')
                # Diagnostic directives are compile-time only; do not keep them as top-level items
                continue
            elif isinstance(item, InfoDirective):
                print_error(cleaned_source, getattr(item, 'line', 1), getattr(item, 'col', 1), item.message, filename=filepath, severity='info')
                continue
            else:
                new_procs.append(item)
        program.procs = new_procs

        # Handle module CONSTRUCTOR procs:
        # - Forbidden in non-module files
        # - In module files, treat them as if they had #KEEP and #NOEXPORT and
        #   rename them to a unique internal name to avoid label collisions.
        new_procs = []
        prog = program
        debug = (prog.debug or {}) if prog else {}
        proc_src = debug.get('proc_src', {})
        for p in program.procs:
            if isinstance(p, ProcDecl) and p.name.lower() == 'constructor':
                if not is_module:
                    # Raise error: Constructor only allowed in module files
                    # Proc source map may use different case for names (parser keeps identifier case),
                    # so try a case-insensitive lookup to find the debug info.
                    info = proc_src.get(p.name) or proc_src.get(p.name.upper()) or proc_src.get(p.name.lower())
                    if info:
                        if len(info) == 3:
                            fname, line_no, _text = info
                            col_no = 1
                        else:
                            fname, line_no, col_no, _text = info
                        # If we have an original-line mapping from the parser stage, map the
                        # cleaned-source line number back to the original file line number.
                        orig_map = debug.get('orig_line_map')
                        if orig_map and 1 <= line_no <= len(orig_map):
                            orig_line_no = orig_map[line_no - 1]
                            src_lines = debug.get('orig_source_lines', orig_lines)
                        else:
                            orig_line_no = line_no
                            src_lines = (program.debug or {}).get('source_lines', [])
                        err = SemanticError("Constructor procedure is only allowed in module files", line=orig_line_no, col=col_no)
                        err.filename = fname
                        err.source_text = '\n'.join(src_lines)
                        raise err
                    else:
                        err = SemanticError("Constructor procedure is only allowed in module files")
                        err.filename = filepath
                        err.source_text = cleaned_source
                        raise err
                # Module file: mangle name, force keep and noexport
                # Use module name if available, otherwise base filename
                mod_base: str = module_name if module_name else os.path.splitext(os.path.basename(filepath))[0]
                safe_mod: str = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in mod_base)
                new_name: str = f"__CONSTRUCTOR__{safe_mod}"
                # Update proc_src mapping to point to new name
                if prog:
                    proc_debug = prog.debug or {}
                    proc_src_map = proc_debug.get('proc_src')
                    if proc_src_map:
                        info = proc_src_map.pop(p.name, None)
                        if info is not None:
                            proc_src_map[new_name] = info
                # Create new proc decl with modified flags and new name
                new_p = ProcDecl(new_name, p.params, p.locals, p.body, keep=True, noexport=True, export=False)
                new_procs.append(new_p)
            else:
                new_procs.append(p)
        program.procs = new_procs
        
        # If this file is declared as a module, sanity-check it doesn't define PROC MAIN()
        if is_module:
            # Look for any top-level procedure named 'main' (case-insensitive)
            for item in program.procs:
                if isinstance(item, ProcDecl) and item.name.lower() == 'main':
                    # Try to get source location from parser debug info
                    proc_info = None
                    proc_map = debug.get('proc_src', {})
                    proc_info = proc_map.get(item.name) or proc_map.get(item.name.upper()) or proc_map.get(item.name.lower())
                    if proc_info:
                        fname, line_no, col_no, _ = proc_info
                        orig_map = debug.get('orig_line_map')
                        if orig_map and 1 <= line_no <= len(orig_map):
                            orig_line_no = orig_map[line_no - 1]
                            src_lines = debug.get('orig_source_lines', orig_lines)
                        else:
                            orig_line_no = line_no
                            src_lines = debug.get('source_lines', [])
                        err = SemanticError("Modules may not define 'main' procedure", line=orig_line_no, col=col_no)
                        err.filename = fname
                        err.source_text = '\n'.join(src_lines)
                        raise err
                    else:
                        err = SemanticError("Modules may not define 'main' procedure")
                        err.filename = filepath
                        err.source_text = cleaned_source
                        raise err

        # Resolve .incbin file paths
        self._resolve_incbin_paths(program, filepath)
        
        return program, is_module, module_name, includes, defined_symbols, module_directive_info
    
    def _resolve_incbin_paths(self, program: Program, filepath: str) -> None:
        """
        Resolve .incbin file paths in the program using the include search algorithm.
        Updates IncbinDirective objects with resolved paths.
        """
        from ast_nodes import IncbinDirective
        
        file_dir: str = os.path.dirname(filepath)
        
        # Process all top-level items
        for i, item in enumerate(program.procs):
            if isinstance(item, IncbinDirective):
                try:
                    resolved_path: str = self._find_file(item.filename, file_dir)
                    # Replace with a new IncbinDirective containing the resolved path
                    program.procs[i] = IncbinDirective(resolved_path)
                except SemanticError as e:
                    # Propagate with enhanced context for .incbin directive
                    # Prefer the original source text (before removing module/include lines) if available
                    debug = program.debug or {}
                    src_lines = debug.get('orig_source_lines')
                    err = SemanticError(f"Error resolving .incbin '{item.filename}' in {filepath}: {e.message}", line=getattr(e, 'line', None), col=getattr(e, 'col', None))
                    err.filename = filepath
                    if src_lines is not None:
                        err.source_text = '\n'.join(src_lines)
                    else:
                        err.source_text = '\n'.join(debug.get('source_lines', [])) if debug else None
                    raise err
    
    def _find_file(self, filename: str, relative_to_dir: str) -> str:
        """
        Search for a file using the include path search algorithm.
        
        1. If filename is an absolute path, use it directly (no -I directories considered)
        2. If filename is relative, search in order:
           - Relative to the directory of the file being compiled (relative_to_dir)
           - Each -I directory (in order)
        
        Returns the absolute path if found, raises FileNotFoundError if not found.
        """
        # Normalize the filename to remove leading ./
        filename = os.path.normpath(filename)
        
        # If filename is absolute, use it directly
        if os.path.isabs(filename):
            if os.path.isfile(filename):
                return os.path.abspath(filename)
            # Report as a SemanticError to unify user-facing error reporting
            err = SemanticError(f"File not found: {filename}")
            err.filename = filename
            raise err
        
        # Try relative to the current file's directory
        current_relative_path: str = os.path.join(relative_to_dir, filename)
        if os.path.isfile(current_relative_path):
            return os.path.abspath(current_relative_path)
        
        # Try each include directory in order
        for inc_dir in self.include_dirs:
            inc_path: str = os.path.join(inc_dir, filename)
            if os.path.isfile(inc_path):
                return os.path.abspath(inc_path)
        
        # File not found - raise SemanticError for consistent user error reporting
        err = SemanticError(f"File not found: {filename} (searched in: current dir, and {len(self.include_dirs)} include directories)")
        err.filename = relative_to_dir
        raise err
    
    def load_module(self, module_path: str) -> ModuleInfo:
        """Load a module and its dependencies"""
        
        # Resolve full path
        full_path: str = os.path.abspath(module_path)
        
        # Check if already loaded
        if full_path in self.loaded_modules:
            return self.loaded_modules[full_path]
        
        # Check for circular dependencies
        if full_path in self.include_stack:
            msg: str = f"Circular dependency detected: {' -> '.join(self.include_stack + [full_path])}"
            err = SemanticError(msg)
            err.filename = full_path
            raise err
        
        self.include_stack.append(full_path)
        
        try:
            # Parse the module file
            program, is_module, module_name, includes, defined_symbols, module_directive_info = self.parse_file(full_path)

            # If this file declares a module name, check for duplicate module names globally
            if is_module and module_name:
                prev: str | None = self.module_name_to_path.get(module_name)
                if prev and os.path.abspath(prev) != full_path:
                    # Duplicate module name found
                    line_no, col_no, text = module_directive_info if module_directive_info else (None, None, None)
                    err = SemanticError(f"Duplicate module name '{module_name}' already declared in {prev}", line=line_no, col=col_no)
                    err.filename = full_path
                    try:
                        err.source_text = '\n'.join((program.debug or {}).get('source_lines', []))
                    except Exception:
                        err.source_text = None
                    raise err
                else:
                    # Register module name -> file path
                    self.module_name_to_path[module_name] = full_path

            # Separate declarations, and also preserve the original top-level items
            declarations = program.decls
            procedures: List[ProcDecl] = [p for p in program.procs if isinstance(p, ProcDecl)]
            functions: List[FuncDecl] = [p for p in program.procs if isinstance(p, FuncDecl)]
            top_level_items = list(program.procs)
            
            # Create module info (includes will be resolved to absolute paths below)
            module_info = ModuleInfo(
                filepath=full_path,
                is_module=is_module,
                module_name=module_name,
                declarations=declarations,
                procedures=procedures,
                functions=functions,
                top_level_items=top_level_items,
                includes=[],
                defined_symbols=defined_symbols,
                program=program
            )

            # Store in cache
            self.loaded_modules[full_path] = module_info

            # Load and resolve dependencies, store absolute paths
            resolved_includes = []
            for inc in includes:
                # Resolve include path relative to current file's directory
                inc_dir: str = os.path.dirname(full_path)
                try:
                    inc_path: str = self._find_file(inc, inc_dir)
                except SemanticError as e:
                    # Re-wrap with context of the including file and, if available,
                    # point to the .include directive's location so the user sees
                    # the exact line/col where the include failed.
                    inc_info = None
                    prog = module_info.program
                    debug = (prog.debug or {}) if prog else {}
                    include_directives = debug.get('include_directives') or {}
                    inc_info = include_directives.get(inc)
                    if inc_info:
                        iline, icol, _text = inc_info
                        err = SemanticError(f"Error loading include '{inc}' from {full_path}: {e.message}", line=iline, col=icol)
                        err.filename = full_path
                        err.source_text = '\n'.join(debug.get('orig_source_lines', []))
                        raise err
                    else:
                        err = SemanticError(f"Error loading include '{inc}' from {full_path}: {e.message}", line=getattr(e, 'line', None), col=getattr(e, 'col', None))
                        err.filename = full_path
                        raise err
                # Ensure dependency is loaded
                self.load_module(inc_path)
                resolved_includes.append(inc_path)

            # Replace includes with resolved absolute paths
            module_info.includes = resolved_includes
            
            return module_info
            
        finally:
            self.include_stack.pop()
    
    def build_program(self, main_file: str) -> tuple[Program, Set[str]]:
        """
        Build a complete program by loading main file and all its dependencies.
        Returns (program, defined_symbols) where defined_symbols is the union of all .define symbols.
        """
        # Reset state
        self.loaded_modules.clear()
        self.include_stack.clear()
        
        # Load main file and dependencies
        main_info: ModuleInfo = self.load_module(main_file)
        
        # Collect all declarations, procs, and funcs in dependency order
        all_decls = []
        all_procs = []
        seen_decls = set()  # Track to avoid duplicates
        seen_procs = set()
        seen_funcs = set()
        all_defined_symbols = set()  # Collect all .define symbols
        
        # Process in dependency order (includes first, then main)
        processed = set()
        
        # Collect exports during module resolution
        all_exports: set[str] = set()

        def collect_from_module(module_path: str) -> None:
            """Merge declarations and top-level items from a module into the program."""
            if module_path in processed:
                return
            processed.add(module_path)
            
            module_info: ModuleInfo = self.loaded_modules[module_path]

            prog = module_info.program
            debug = (prog.debug or {}) if prog else {}
            decl_src = debug.get("global_decl_src", {})
            proc_src = debug.get("proc_src", {})
            source_lines = debug.get("source_lines", [])
            source_text: str | None = "\n".join(source_lines) if source_lines else None

            def raise_dup(msg: str, name: str, info) -> NoReturn:
                """Raise a duplicate-definition error with best-effort source context."""
                line = None
                col = None
                if info:
                    if len(info) == 4:
                        _, line, col, text = info
                    else:
                        # Fallback for 3-tuple (shouldn't happen with new parser)
                        _, line, text = info
                        if text:
                            idx = text.upper().find(name)
                            if idx != -1:
                                col = idx + 1
                        if col is None:
                            col = 1
                err = SemanticError(msg, line=line, col=col)
                if source_text:
                    setattr(err, "source_text", source_text)
                raise err
            
            # First process dependencies (module_info.includes contains resolved absolute paths)
            for inc_path in module_info.includes:
                # If includes are not absolute for some reason, resolve relative to the module file
                if not os.path.isabs(inc_path):
                    inc_path: str = os.path.abspath(os.path.join(os.path.dirname(module_path), inc_path))
                if inc_path in self.loaded_modules:
                    collect_from_module(inc_path)
            
            # Collect .define symbols from this module
            if module_info.defined_symbols:
                all_defined_symbols.update(module_info.defined_symbols)
            
            # Add this module's declarations and collect exports for variables
            for decl in module_info.declarations:
                # Skip non-variable declarations (e.g., EnumDecl, StructDef)
                if not hasattr(decl, 'declarators'):
                    all_decls.append(decl)
                    continue
                for d in decl.declarators:
                    name: str = d.name
                    if name in seen_decls:
                        raise_dup(f"Variable '{name}' already defined", name, decl_src.get(name))
                    seen_decls.add(name)
                    # Export rules for variables:
                    # - In a .module file, export all variables except those with #NOEXPORT
                    # - In non-module file, export only those variables marked with #EXPORT
                    if module_info.is_module:
                        if not getattr(decl, 'noexport', False):
                            all_exports.add(name)
                    else:
                        if getattr(decl, 'export', False):
                            all_exports.add(name)
                # Keep all declarations in the aggregated declarations list so module-internal
                # procedures can still reference module-local globals during analysis,
                # but they will not be considered exported unless above.
                all_decls.append(decl)

            # Merge top-level items, deduping procs/funcs by name, preserving directives
            for item in module_info.top_level_items:
                # Determine whether this item should be exported to other files
                should_export = False
                if isinstance(item, ProcDecl) or isinstance(item, FuncDecl):
                    if module_info.is_module:
                        should_export: bool = not getattr(item, 'noexport', False)
                    else:
                        # Non-module files behave like part of the main compilation unit
                        # and their top-level items are considered visible here.
                        should_export = True

                # Collect constructors in encountered order (deps first)
                if isinstance(item, ProcDecl) and item.name.startswith("__CONSTRUCTOR__"):
                    constructors.append(item.name)

                if isinstance(item, ProcDecl):
                    name: str = item.name
                    # Only perform cross-module duplicate checks for exported items
                    if should_export:
                        if name in seen_procs:
                            raise_dup(f"Procedure '{name}' already defined", name, proc_src.get(name))
                        if name in seen_funcs:
                            raise_dup(f"Procedure '{name}' conflicts with existing function", name, proc_src.get(name))
                        seen_procs.add(name)
                        all_procs.append(item)
                        if should_export:
                            all_exports.add(name)
                    else:
                        # keep module-local procedures in the aggregate so they can be
                        # analyzed internally, but DO NOT add them to exports nor treat
                        # them as collisions across module boundaries
                        all_procs.append(item)
                elif isinstance(item, FuncDecl):
                    name: str = item.name
                    if should_export:
                        if name in seen_funcs:
                            raise_dup(f"Function '{name}' already defined", name, proc_src.get(name))
                        if name in seen_procs:
                            raise_dup(f"Function '{name}' conflicts with existing procedure", name, proc_src.get(name))
                        seen_funcs.add(name)
                        all_procs.append(item)
                        if should_export:
                            all_exports.add(name)
                    else:
                        all_procs.append(item)
                else:
                    # e.g., SegmentDirective or other future top-level items
                    all_procs.append(item)
        
        # Collect everything starting from main
        constructors: list[str] = []
        collect_from_module(os.path.abspath(main_file))
        
        final_program = Program(all_decls, all_procs)
        # Attach computed exports set for later stages (codegen/cleanup)
        final_program.exports = all_exports
        # Attach constructor call order (from most deeply included to top-level)
        final_program.constructors = constructors

        # Aggregate debug maps from all modules
        agg_stmt = {}
        agg_local = {}
        agg_global = {}
        agg_proc = {}
        file_lines = {}
        # Per-file structures to help map cleaned-source positions back to original files
        per_file_stmt_pos: Dict[str, list[tuple[int,int,str]]] = {}
        orig_line_map_per_file: Dict[str, list[int]] = {}
        orig_source_lines_per_file: Dict[str, list[str]] = {}

        for module_path, module_info in self.loaded_modules.items():
            prog: Program | None = module_info.program
            if prog and prog.debug:
                dbg = prog.debug
                # Merge maps
                for k, v in dbg.get("stmt_src", {}).items():
                    agg_stmt[k] = v
                    # v is (filename, line, col, text) -> record cleaned position in per-file map
                    try:
                        fname = v[0]
                        if not fname:
                            continue
                        raw_line = v[1]
                        raw_col = v[2] if len(v) > 2 else None
                        raw_text = v[3] if len(v) > 3 else None
                        # Normalize/validate types to match Dict[str, list[tuple[int,int,str]]]
                        ln_i = raw_line if isinstance(raw_line, int) and raw_line >= 0 else 0
                        col_i = raw_col if isinstance(raw_col, int) and raw_col >= 0 else 0
                        txt = raw_text if isinstance(raw_text, str) else ""
                        per_file_stmt_pos.setdefault(fname, []).append((ln_i, col_i, txt))
                    except Exception:
                        pass
                for k, v in dbg.get("local_decl_src", {}).items():
                    agg_local[k] = v
                for k, v in dbg.get("global_decl_src", {}).items():
                    agg_global[k] = v
                for k, v in dbg.get("proc_src", {}).items():
                    agg_proc[k] = v
                # Keep filename->lines for reference
                fname = dbg.get("filename")
                lines = dbg.get("source_lines")
                if fname and lines:
                    file_lines[fname] = lines
                # Also preserve original-line mapping and original source lines if available
                orig_map = dbg.get('orig_line_map')
                if fname and orig_map:
                    orig_line_map_per_file[fname] = orig_map
                orig_src_lines = dbg.get('orig_source_lines')
                if fname and orig_src_lines:
                    orig_source_lines_per_file[fname] = orig_src_lines

        # Map filename -> is_module flag for consumer passes that need to know which
        # source files were declared as .module
        file_is_module: Dict[str, bool] = { path: info.is_module for path, info in self.loaded_modules.items() }

        final_program.debug = {
            "stmt_src": agg_stmt,
            "local_decl_src": agg_local,
            "global_decl_src": agg_global,
            "proc_src": agg_proc,
            "file_lines": file_lines,
            "file_is_module": file_is_module,
            # Extra per-file mappings to support remapping of runtime diagnostics
            "per_file_stmt_pos": per_file_stmt_pos,
            "orig_line_map_per_file": orig_line_map_per_file,
            "orig_source_lines_per_file": orig_source_lines_per_file,
        }

        return final_program, all_defined_symbols

"""
Module system for handling .module and .include directives
"""
import os
from dataclasses import dataclass
from typing import Dict, Set, Optional, List
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
    defined_symbols: Set[str] = None  # Preprocessor .define symbols
    program: Program | None = None


class ModuleSystem:
    """
    Manages module loading and dependency resolution
    """
    
    def __init__(self, base_path: str = ".", predefined_symbols: Optional[Set[str]] = None, include_dirs: Optional[List[str]] = None):
        self.base_path = os.path.abspath(base_path)
        self.loaded_modules: Dict[str, ModuleInfo] = {}
        self.include_stack: list[str] = []  # For circular dependency detection
        self.preprocessor = Preprocessor(predefined_symbols)  # Shared preprocessor for all modules
        self.include_dirs = [os.path.abspath(d) for d in (include_dirs or [])]  # Normalize include directory paths
    
    def parse_file(self, filepath: str):
        """Parse a single file and extract module directives"""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            source = f.read()
        
        # Strip UTF-8 BOM if present
        if source.startswith('\ufeff'):
            source = source[1:]
        
        # Apply preprocessor (handles .ifdef, .ifndef, .else, .endif, .define, .undef)
        source, defined_symbols = self.preprocessor.process(source)
        
        # Extract module/include directives
        module_name = None
        is_module = False
        includes = []
        
        lines = source.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            lower_stripped = stripped.lower()
            if stripped.startswith('.module'):
                # Extract module name from .module "filename"
                is_module = True
                parts = stripped.split('"')
                if len(parts) >= 2:
                    module_name = parts[1]
            elif stripped.startswith('.include'):
                # Extract include filename from .include "filename"
                parts = stripped.split('"')
                if len(parts) >= 2:
                    includes.append(parts[1])
            elif lower_stripped.startswith('.segment'):
                # Keep .segment directives - they're parsed as statements
                cleaned_lines.append(line)
            else:
                # Keep non-directive lines for parsing
                cleaned_lines.append(line)
        
        # Parse the cleaned source
        cleaned_source = '\n'.join(cleaned_lines)
        
        parser = Parser(cleaned_source, filename=filepath)
        try:
            program = parser.parse_program()
        except Exception as e:
            # Attach source text for better error reporting if it's a CompileError subtype
            try:
                setattr(e, "source_text", cleaned_source)
            except Exception:
                pass
            raise
        
        # Resolve .incbin file paths
        self._resolve_incbin_paths(program, filepath)
        
        return program, is_module, module_name, includes, defined_symbols
    
    def _resolve_incbin_paths(self, program: Program, filepath: str):
        """
        Resolve .incbin file paths in the program using the include search algorithm.
        Updates IncbinDirective objects with resolved paths.
        """
        from ast_nodes import IncbinDirective
        
        file_dir = os.path.dirname(filepath)
        
        # Process all top-level items
        for i, item in enumerate(program.procs):
            if isinstance(item, IncbinDirective):
                try:
                    resolved_path = self._find_file(item.filename, file_dir)
                    # Replace with a new IncbinDirective containing the resolved path
                    program.procs[i] = IncbinDirective(resolved_path)
                except FileNotFoundError as e:
                    raise Exception(f"Error resolving .incbin '{item.filename}' in {filepath}: {e}")
    
    def _find_file(self, filename: str, relative_to_dir: str) -> str:
        """
        Search for a file using the include path search algorithm.
        
        1. First try the filename as-is (if absolute or relative)
        2. Then try relative to the directory of the file being compiled (relative_to_dir)
        3. Then try in each -I directory (in order)
        
        Returns the absolute path if found, raises FileNotFoundError if not found.
        """
        # If filename is absolute, use it directly
        if os.path.isabs(filename):
            if os.path.isfile(filename):
                return os.path.abspath(filename)
            raise FileNotFoundError(f"File not found: {filename}")
        
        # Try relative to the current file's directory
        current_relative_path = os.path.join(relative_to_dir, filename)
        if os.path.isfile(current_relative_path):
            return os.path.abspath(current_relative_path)
        
        # Try each include directory in order
        for inc_dir in self.include_dirs:
            inc_path = os.path.join(inc_dir, filename)
            if os.path.isfile(inc_path):
                return os.path.abspath(inc_path)
        
        # File not found
        raise FileNotFoundError(f"File not found: {filename} (searched in: current dir, and {len(self.include_dirs)} include directories)")
    
    def load_module(self, module_path: str) -> ModuleInfo:
        """Load a module and its dependencies"""
        
        # Resolve full path
        full_path = os.path.abspath(module_path)
        
        # Check if already loaded
        if full_path in self.loaded_modules:
            return self.loaded_modules[full_path]
        
        # Check for circular dependencies
        if full_path in self.include_stack:
            raise Exception(f"Circular dependency detected: {' -> '.join(self.include_stack + [full_path])}")
        
        self.include_stack.append(full_path)
        
        try:
            # Parse the module file
            program, is_module, module_name, includes, defined_symbols = self.parse_file(full_path)
            
            # Separate declarations, and also preserve the original top-level items
            declarations = program.decls
            procedures = [p for p in program.procs if isinstance(p, ProcDecl)]
            functions = [p for p in program.procs if isinstance(p, FuncDecl)]
            top_level_items = list(program.procs)
            
            # Create module info
            module_info = ModuleInfo(
                filepath=full_path,
                is_module=is_module,
                module_name=module_name,
                declarations=declarations,
                procedures=procedures,
                functions=functions,
                top_level_items=top_level_items,
                includes=includes,
                defined_symbols=defined_symbols,
                program=program
            )
            
            # Store in cache
            self.loaded_modules[full_path] = module_info
            
            # Load dependencies
            for inc in includes:
                # Resolve include path relative to current file's directory
                inc_dir = os.path.dirname(full_path)
                try:
                    inc_path = self._find_file(inc, inc_dir)
                except FileNotFoundError as e:
                    raise Exception(f"Error loading include '{inc}' from {full_path}: {e}")
                self.load_module(inc_path)
            
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
        main_info = self.load_module(main_file)
        
        # Collect all declarations, procs, and funcs in dependency order
        all_decls = []
        all_procs = []
        seen_decls = set()  # Track to avoid duplicates
        seen_procs = set()
        seen_funcs = set()
        all_defined_symbols = set()  # Collect all .define symbols
        
        # Process in dependency order (includes first, then main)
        processed = set()
        
        def collect_from_module(module_path: str):
            if module_path in processed:
                return
            processed.add(module_path)
            
            module_info = self.loaded_modules[module_path]

            debug = module_info.program.debug if module_info.program else {}
            decl_src = debug.get("global_decl_src", {})
            proc_src = debug.get("proc_src", {})
            source_lines = debug.get("source_lines", [])
            source_text = "\n".join(source_lines) if source_lines else None

            def raise_dup(msg: str, name: str, info):
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
            
            # First process dependencies
            for inc in module_info.includes:
                inc_dir = os.path.dirname(module_path)
                inc_path = os.path.join(inc_dir, inc)
                if inc_path in self.loaded_modules:
                    collect_from_module(inc_path)
            
            # Collect .define symbols from this module
            if module_info.defined_symbols:
                all_defined_symbols.update(module_info.defined_symbols)
            
            # Add this module's exports
            for decl in module_info.declarations:
                for d in decl.declarators:
                    name = d.name
                    if name in seen_decls:
                        raise_dup(f"Variable '{name}' already defined", name, decl_src.get(name))
                    seen_decls.add(name)
                all_decls.append(decl)

            # Merge top-level items, deduping procs/funcs by name, preserving directives
            for item in module_info.top_level_items:
                if isinstance(item, ProcDecl):
                    name = item.name
                    if name in seen_procs:
                        raise_dup(f"Procedure '{name}' already defined", name, proc_src.get(name))
                    if name in seen_funcs:
                        raise_dup(f"Procedure '{name}' conflicts with existing function", name, proc_src.get(name))
                    seen_procs.add(name)
                    all_procs.append(item)
                elif isinstance(item, FuncDecl):
                    name = item.name
                    if name in seen_funcs:
                        raise_dup(f"Function '{name}' already defined", name, proc_src.get(name))
                    if name in seen_procs:
                        raise_dup(f"Function '{name}' conflicts with existing procedure", name, proc_src.get(name))
                    seen_funcs.add(name)
                    all_procs.append(item)
                else:
                    # e.g., SegmentDirective or other future top-level items
                    all_procs.append(item)
        
        # Collect everything starting from main
        collect_from_module(os.path.abspath(main_file))
        
        final_program = Program(all_decls, all_procs)

        # Aggregate debug maps from all modules
        agg_stmt = {}
        agg_local = {}
        agg_global = {}
        agg_proc = {}
        file_lines = {}

        for module_path, module_info in self.loaded_modules.items():
            prog = module_info.program
            if prog and prog.debug:
                dbg = prog.debug
                # Merge maps
                for k, v in dbg.get("stmt_src", {}).items():
                    agg_stmt[k] = v
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

        final_program.debug = {
            "stmt_src": agg_stmt,
            "local_decl_src": agg_local,
            "global_decl_src": agg_global,
            "proc_src": agg_proc,
            "file_lines": file_lines,
        }

        return final_program, all_defined_symbols


# The author of this software stands in solidarity with 🇺🇦 Ukraine. 
# We believe in a world where international borders are respected and human rights are upheld. 
# We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


from errors import SemanticError
from typing import Any
from symbols import SemType, Symbol, SymbolTable, StructRegistry, StructInfo, StructFieldInfo, ScopedSymbolTable
from ast_nodes import (
    Expr, IntLiteral, Identifier, BinaryExpr, BinOp, FieldAccess, CallExpr,
    ListInit, StringInit, ExprInit, Declaration, Declarator, StructDef, EnumDecl, EnumItem,
    UnaryExpr, UnOp
)



def eval_const_expr(expr, symtab=None, struct_registry=None):
    """Evaluate a constant expression using optional symbol and struct context."""
    if isinstance(expr, IntLiteral):
        return expr.value
    
    # Handle identifiers - look up const variables
    if isinstance(expr, Identifier):
        if symtab is None:
            raise SemanticError("Constant expression required", node=expr)
        try:
            sym = symtab.lookup(expr.name)
        except KeyError:
            raise SemanticError(f"Undefined identifier: {expr.name}", node=expr)
        if sym is None:
            raise SemanticError(f"Undefined identifier: {expr.name}", node=expr)
        if not sym.is_const:
            raise SemanticError(f"'{expr.name}' is not a const", node=expr)
        if sym.const_value is None:
            raise SemanticError(f"'{expr.name}' const has no value", node=expr)
        return sym.const_value

    # Qualified enum member access, e.g., EnumName.Member
    if isinstance(expr, FieldAccess):
        if symtab is None:
            raise SemanticError("Constant expression required", node=expr)
        # Only support EnumName.Member (object must be Identifier)
        if isinstance(expr.object, Identifier):
            enum_name = expr.object.name.upper()
            enums = getattr(symtab, '_enums', None)
            # If symtab is a ScopedSymbolTable, check parent for enums
            if enums is None:
                parent = getattr(symtab, 'parent', None)
                if parent is not None:
                    enums = getattr(parent, '_enums', None)
            if enums and enum_name in enums:
                members = enums[enum_name]['members']
                mname = expr.field.upper()
                if mname not in members:
                    raise SemanticError(f"Enum '{expr.object.name}' has no member '{expr.field}'", node=expr)
                return members[mname]
        raise SemanticError("Constant expression required", node=expr)

    if isinstance(expr, UnaryExpr):
        operand = eval_const_expr(expr.expr, symtab, struct_registry)
        if expr.op == UnOp.NEG:
            return -operand
        if expr.op == UnOp.NOT:
            return 0 if operand else 1
        if expr.op == UnOp.BNOT:
            return (~operand) & 0xFFFF
        raise SemanticError("Unsupported unary op in constant expression", node=expr)

    if isinstance(expr, BinaryExpr):
        left = eval_const_expr(expr.left, symtab, struct_registry)
        right = eval_const_expr(expr.right, symtab, struct_registry)
        if expr.op == BinOp.ADD:
            return left + right
        elif expr.op == BinOp.SUB:
            return left - right
        elif expr.op == BinOp.MUL:
            return left * right
        elif expr.op == BinOp.DIV:
            return left // right
        elif expr.op == BinOp.MOD:
            return left % right
        else:
            raise SemanticError("Unsupported operation in constant expression", node=expr)
    if isinstance(expr, CallExpr):
        name_upper = expr.name.upper()
        if name_upper in {"LOW", "HIGH", "SIZEOF", "LOWW", "HIGHW"}:
            if len(expr.args) != 1 or expr.args[0] is None:
                raise SemanticError(f"{name_upper}() expects exactly one argument", node=expr)
            arg = expr.args[0]
            if name_upper == "SIZEOF":
                if not isinstance(arg, Identifier):
                    raise SemanticError("SIZEOF expects a struct name", node=expr)
                if struct_registry is None:
                    raise SemanticError("Struct registry not available", node=expr)
                info = struct_registry.lookup(arg.name.upper()) if struct_registry else None
                if not info:
                    raise SemanticError(f"'{arg.name}' is not a defined struct", node=expr)
                return info.size
            value = eval_const_expr(arg, symtab, struct_registry)
            if name_upper == "LOW":
                return value & 0xFF
            if name_upper == "HIGH":
                return (value >> 8) & 0xFF
            if name_upper == "LOWW":
                return value & 0xFFFF
            # HIGHW
            return (value >> 16) & 0xFFFF
        raise SemanticError("Constant expression required", node=expr)

    raise SemanticError("Constant expression required", node=expr)


def eval_array_dimensions(array_sizes, symtab, d_obj=None, struct_registry=None):
    """Evaluate array dimensions and compute metadata for declarations.

    Returns (is_array, array_dims, array_len) where array_len is 1D legacy.
    """
    is_array = False
    array_dims = []
    array_len = None
    
    if array_sizes:
        # Multi-dimensional array
        is_array = True
        for size_expr in array_sizes:
            try:
                sz_val = eval_const_expr(size_expr, symtab, struct_registry)
            except SemanticError as e:
                raise SemanticError(e.message, node=d_obj)

            if sz_val == -1:
                # [] → will be inferred from initializer
                array_dims.append(None)
            elif sz_val <= 0:
                raise SemanticError("Array dimension must be positive", node=d_obj)
            else:
                array_dims.append(sz_val)
        
        # For backward compatibility, set array_len to first dimension if all are known
        if array_dims and all(d is not None for d in array_dims):
            array_len = array_dims[0] if len(array_dims) == 1 else None
    
    return is_array, array_dims, array_len



class StructAnalyzer:
    """Analyzes and registers struct definitions"""
    def __init__(self, struct_registry: StructRegistry, enum_symtab: SymbolTable | None = None) -> None:
        """Initialize with a struct registry to populate."""
        self.registry: StructRegistry = struct_registry
        self.enum_symtab: SymbolTable | None = enum_symtab

    def analyze(self, struct_def: StructDef) -> None:
        """Analyze a struct definition and register it"""
        # Calculate field offsets
        fields: list[StructFieldInfo] = []
        current_offset = 0

        for field_ast in struct_def.fields:
            # Get field type
            field_type: str = field_ast.type.base.upper()
            is_pointer: bool = field_ast.type.is_pointer
            field_base_type: str = field_type

            # Get element width (for a single element, not array)
            if field_type == "BYTE":
                elem_width = 1
            elif field_type == "WORD":
                elem_width = 2
            elif field_type == "LONG":
                elem_width = 4
            elif field_type in self.registry._structs:
                # Nested struct type
                nested_struct: StructInfo = self.registry._structs[field_type]
                elem_width: int = nested_struct.size
            elif self.enum_symtab is not None and field_type in getattr(self.enum_symtab, "_enums", {}):
                # Enum field: use enum base type width
                enum_def = self.enum_symtab._enums[field_type]
                enum_base = enum_def.get("base", "BYTE")
                field_base_type = enum_base
                if enum_base == "BYTE":
                    elem_width = 1
                else:
                    elem_width = 2
            elif is_pointer and field_type == struct_def.name.upper():
                # Self-referential struct pointer (or forward-referenced struct)
                # Pointers are always 16-bit (2 bytes)
                elem_width = 2
            elif is_pointer:
                # Forward reference to struct type (will be resolved later or error at use time)
                # For now, assume pointer size (2 bytes)
                elem_width = 2
            else:
                # Unknown non-pointer type
                raise SemanticError(f"Unsupported field type '{field_type}' in struct", node=field_ast)

            if is_pointer and elem_width != 2:
                # Pointers should be 2 bytes
                elem_width = 2

            # Evaluate array dimensions if present
            array_sizes = None
            if field_ast.array_sizes:
                array_sizes = []
                for size_expr in field_ast.array_sizes:
                    try:
                        size = eval_const_expr(size_expr, struct_registry=self.registry)
                        array_sizes.append(size)
                    except SemanticError as e:
                        raise SemanticError(f"Invalid array size in struct field '{field_ast.name}': {e.message}", node=field_ast)

            # Calculate total width
            width: int = elem_width
            if array_sizes:
                total_elements = 1
                for size in array_sizes:
                    total_elements *= size
                width = elem_width * total_elements

            # Evaluate fixed address if present
            fixed_addr = None
            if field_ast.address is not None:
                try:
                    fixed_addr = eval_const_expr(field_ast.address, struct_registry=self.registry)
                except SemanticError as e:
                    raise SemanticError(f"Invalid field address: {e.message}", node=field_ast)

            # Create field info
            field_info = StructFieldInfo(
                name=field_ast.name.upper(),
                base_type=field_base_type,
                is_pointer=is_pointer,
                offset=current_offset,
                fixed_address=fixed_addr,
                array_sizes=array_sizes,
                is_port=getattr(field_ast, 'is_port', False),
                port_rd=getattr(field_ast, 'port_rd', None),
                port_wr=getattr(field_ast, 'port_wr', None),
            )
            fields.append(field_info)
            current_offset += width

        # Enforce 255-byte limit: field offsets must fit in a single byte (LDY #offset)
        if current_offset > 255:
            raise SemanticError(
                f"Struct '{struct_def.name}' is {current_offset} bytes - maximum struct size is 255 bytes",
                node=struct_def,
            )

        # Create and register struct (with optional port defaults)
        struct_info = StructInfo(
            name=struct_def.name.upper(),
            fields=fields,
            size=current_offset,
            is_port_default=getattr(struct_def, 'is_port', False),
            port_rd_default=getattr(struct_def, 'port_rd', None),
            port_wr_default=getattr(struct_def, 'port_wr', None),
        )

        try:
            # Pass the AST node so the registry can attach accurate source context
            self.registry.define(struct_info, node=struct_def)
        except SemanticError as e:
            # Attach struct definition source location if available
            raise SemanticError(f"Struct definition error: {e.message}", node=struct_def)



class DeclarationAnalyzer:
    """Analyzes variable declarations and populates symbol tables."""
    def __init__(self, symtab: SymbolTable, struct_registry=None, func_table=None, global_symtab=None, debug_info: dict | None = None) -> None:
        """Initialize declaration analyzer with symbol context and debug info."""
        self.symtab: SymbolTable = symtab
        self.struct_registry = struct_registry
        self.func_table = func_table
        self.global_symtab = global_symtab
        self.debug = debug_info or {}

    def analyze(self, decl: Declaration) -> None:
        """Analyze a declaration and add its symbols to the table."""
        # Check if this is a struct type or a built-in type
        base_name: str = decl.type.base.upper()
        is_struct = False
        struct_info = None
        
        if self.struct_registry and self.struct_registry.is_defined(base_name):
            is_struct = True
            struct_info = self.struct_registry.lookup(base_name)
        
        for d in decl.declarators:
            # Build sem_type per declarator: is_pointer lives on each Declarator (C-style).
            sem_type = SemType(
                base=decl.type.base,
                is_pointer=d.is_pointer,
                is_struct=is_struct,
                struct_info=struct_info
            )
            try:
                if not is_struct and base_name not in {"BYTE", "WORD", "LONG"}:
                    raise SemanticError(f"Unknown type '{decl.type.base}'")
                self._analyze_declarator(decl, d, sem_type)
            except SemanticError as e:
                if getattr(e, "filename", None) is None:
                    self._attach_decl_error_context(e, d)
                raise

    def _attach_decl_error_context(self, err: SemanticError, d: Declarator) -> None:
        """Attach filename/line/col to errors based on debug maps."""
        debug = self.debug or {}
        proc_name: str = getattr(self.symtab, "_proc_name", "")
        info = None
        if proc_name:
            info = (debug.get("local_decl_src") or {}).get((proc_name, d.name))
        else:
            info = (debug.get("global_decl_src") or {}).get(d.name)
        if not info:
            return

        if len(info) == 3:
            fname, line, _text = info
            col = 1
        else:
            fname, line, col, _text = info

        orig_map = (debug.get("orig_line_map_per_file") or {}).get(fname)
        if orig_map and isinstance(line, int) and 1 <= line <= len(orig_map):
            line = orig_map[line - 1]

        err.filename = fname
        if getattr(err, "line", None) is None:
            err.line = line if isinstance(line, int) and line >= 1 else err.line
        if getattr(err, "col", None) is None:
            err.col = col if isinstance(col, int) and col >= 1 else err.col

        orig_src = (debug.get("orig_source_lines_per_file") or {}).get(fname)
        if orig_src:
            err.source_text = "\n".join(orig_src)

    def _validate_struct_init(self, init: ListInit, struct_info, line: int, col: int, filename: str = "") -> None:
        """Recursively validate struct initializer has correct field count and nested structs."""
        num_fields: int = len(struct_info.fields)
        num_values: int = len(init.values)

        if num_values != num_fields:
            err = SemanticError(f"Struct '{struct_info.name}' has {num_fields} field(s) but {num_values} value(s) provided", line=line, col=col)
            if filename:
                err.filename = filename
            raise err

        # Validate nested structs
        for field, value in zip(struct_info.fields, init.values):
            # Check if field type is a struct by looking it up in registry
            if self.struct_registry and not field.is_pointer:
                # Try to lookup the field base_type as a struct
                nested_struct_info = None
                try:
                    nested_struct_info = self.struct_registry.lookup(field.base_type.upper())
                except SemanticError:
                    # Not a struct, just a built-in type
                    pass
                
                if nested_struct_info and isinstance(value, ListInit):
                    self._validate_struct_init(value, nested_struct_info, line, col, filename)

    def _analyze_declarator(
        self,
        decl: Declaration,
        d: Declarator,
        sem_type: SemType
        ) -> None:
        """Validate a single declarator and define its symbol."""

        # Validate STATIC modifier
        if decl.is_static or d.is_static:
            # STATIC can only be used on local variables (proc_name must be set)
            if not getattr(self.symtab, '_proc_name', ''):
                raise SemanticError("STATIC modifier can only be used on local variables", node=d)
            
            # STATIC cannot be used on const variables
            if decl.is_const:
                raise SemanticError("STATIC and CONST modifiers cannot be combined", node=d)
            
            # STATIC variables must have an initializer
            if d.initializer is None:
                raise SemanticError("STATIC variable must have an initializer", node=d)

        # Validate PORT modifier
        if decl.is_port:
            # PORT cannot be combined with CONST
            if decl.is_const:
                raise SemanticError("PORT and CONST modifiers cannot be combined", node=d)
            
            # PORT cannot be combined with STATIC
            if decl.is_static or d.is_static:
                raise SemanticError("PORT and STATIC modifiers cannot be combined", node=d)
            
            # PORT requires an address specification (@)
            if d.address is None:
                raise SemanticError("PORT modifier requires address specification with @", node=d)
            
            # PORT cannot be used on arrays
            if d.array_size is not None or d.array_sizes is not None:
                raise SemanticError("PORT modifier cannot be used on arrays", node=d)
            
            # PORT cannot be used on pointers
            if d.is_pointer:
                raise SemanticError("PORT modifier cannot be used on pointers", node=d)
            
            # PORT cannot have initializers (hardware ports can't be initialized)
            if d.initializer is not None:
                raise SemanticError("PORT variable cannot have initializer", node=d)
        # RD/WR modifiers must be used together with #PORT
        if (getattr(decl, 'port_rd', False) or getattr(decl, 'port_wr', False)) and not decl.is_port:
            raise SemanticError("#RD and #WR modifiers are only valid on #PORT declarations", node=d)

        # Extract array dimensions (supports multi-dimensional arrays)
        array_sizes_to_eval: list[Expr] = d.array_sizes if d.array_sizes else (
            [d.array_size] if d.array_size is not None else []
        )
        
        # If a global symbol table was provided, create a scoped lookup that includes both
        # local (this.symtab) and global symbols so constants used in array sizes (e.g., NUM_POINTS)
        # can be resolved.
        if self.global_symtab is not None:
            lookup_symtab = ScopedSymbolTable(self.global_symtab)
            lookup_symtab.local = self.symtab
        else:
            lookup_symtab = self.symtab

        is_array, array_dims, array_len = eval_array_dimensions(
            array_sizes_to_eval,
            lookup_symtab,
            d,
            struct_registry=self.struct_registry
        )  # type: ignore[assignment]
        
        address_val = None

        if d.address is not None:
            # Use a scoped lookup that includes globals (enums) if available
            if self.global_symtab is not None:
                lookup_symtab = ScopedSymbolTable(self.global_symtab)
                lookup_symtab.local = self.symtab
            else:
                lookup_symtab = self.symtab
            address_val = eval_const_expr(d.address, lookup_symtab, self.struct_registry)
            if address_val < 0:
                raise SemanticError(f"Fixed variable address cannot be negative: {address_val}", node=d.address)

        if is_array and array_dims:
            # Process each dimension
            processed_dims = []
            for dim_val in array_dims:
                if dim_val is None:
                    # [] → infer size (will be done below)
                    processed_dims.append(None)
                else:
                    processed_dims.append(dim_val)
            array_dims = processed_dims

        # Compute effective port flags considering declaration and struct defaults
        struct_info_local = sem_type.struct_info
        # Effective: declaration-level #PORT or struct-level default (coerce to bool)
        effective_is_port: bool = bool(getattr(decl, 'is_port', False) or (struct_info_local and bool(getattr(struct_info_local, 'is_port_default', False))))
        # Declaration flags take precedence; if not specified, fall back to struct defaults
        decl_rd_raw = getattr(decl, 'port_rd', None)
        decl_wr_raw = getattr(decl, 'port_wr', None)
        rd: bool = bool(decl_rd_raw) if decl_rd_raw is not None else False
        wr: bool = bool(decl_wr_raw) if decl_wr_raw is not None else False
        if not (decl_rd_raw or decl_wr_raw) and struct_info_local is not None:
            if getattr(struct_info_local, 'port_rd_default', None) is not None:
                rd = bool(struct_info_local.port_rd_default)
            if getattr(struct_info_local, 'port_wr_default', None) is not None:
                wr = bool(struct_info_local.port_wr_default)
        # If this is a PORT (by declaration or struct default) and neither RD/WR is true, allow both by default
        if effective_is_port and not (rd or wr):
            rd = wr = True

        # const pravidla
        if decl.is_const:
            if d.address is not None:
                raise SemanticError("CONST cannot have address", node=d)
            
            # CONST can have expression initializer (scalars), ListInit (structs/arrays), or StringInit (byte arrays)
            if isinstance(d.initializer, ExprInit):
                # Scalar const: must have evaluable expression
                try:
                    # Evaluate constant expression with a lookup that includes globals (for enums)
                    if self.global_symtab is not None:
                        lookup_symtab = ScopedSymbolTable(self.global_symtab)
                        lookup_symtab.local = self.symtab
                    else:
                        lookup_symtab = self.symtab
                    val = eval_const_expr(d.initializer.expr, lookup_symtab, self.struct_registry)
                except SemanticError as e:
                    raise SemanticError(e.message, node=d)

                # Check if constant fits in its type
                if sem_type.base == "BYTE" and not sem_type.is_pointer:
                    if val < 0 or val > 0xFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in BYTE (0-255)",
                            node=d.initializer.expr
                        )
                elif sem_type.base == "WORD" or sem_type.is_pointer:
                    if val < 0 or val > 0xFFFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in WORD (0-65535)",
                            node=d.initializer.expr
                        )

                # Use effective rd/wr computed earlier
                sym = Symbol(
                    name=d.name,
                    type=sem_type,
                    is_const=True,
                    is_array=False,
                    array_len=None,
                    init=None,              # Scalar const has no runtime init
                    const_value=val,
                    address=None,
                    is_volatile=False,
                    proc_name=getattr(self.symtab, '_proc_name', ''),
                    array_dims=None,
                    is_port=effective_is_port,
                    port_rd=rd,
                    port_wr=wr,
                    is_keep=getattr(decl, 'keep', False),
                    noexport=getattr(decl, 'noexport', False),
                    export=getattr(decl, 'export', False),
                )
                try:
                    self.symtab.define(sym)
                except SemanticError as e:
                    # Re-raise with better context for constants
                    raise SemanticError(f"Constant '{d.name}': {e.message}", node=d)
                # Scalar const handled - no further processing for this declarator
                return

    # _analyze_declarator moved earlier into DeclarationAnalyzer class
            
            elif isinstance(d.initializer, ListInit):
                # ListInit for const: can be struct or array
                if is_array:
                    # Const array with ListInit
                    if array_len is None:
                        array_len = len(d.initializer.values)  # type: ignore[assignment]
                        if array_len == 0:
                            raise SemanticError("Array initializer must have at least one element", node=d.initializer)
                    elif array_len != len(d.initializer.values):
                        size_expr = d.array_sizes[0] if d.array_sizes else d.array_size
                        if size_expr is not None:
                            raise SemanticError("Array initializer size mismatch", node=size_expr)
                        raise SemanticError("Array initializer size mismatch", node=d)
                    
                # Use effective rd/wr computed earlier
                
                    sym = Symbol(
                        name=d.name,
                        type=sem_type,
                        is_const=True,
                        is_array=True,
                        array_len=array_len,
                        init=d.initializer,     # Store init for code gen
                        const_value=None,
                        address=None,
                        is_volatile=False,
                        proc_name=getattr(self.symtab, '_proc_name', ''),
                        array_dims=array_dims if array_dims else None,
                        is_port=effective_is_port,
                        port_rd=rd,
                        port_wr=wr,
                        is_keep=getattr(decl, 'keep', False),
                        noexport=getattr(decl, 'noexport', False),
                        export=getattr(decl, 'export', False),
                    )
                    try:
                        self.symtab.define(sym, node=d)
                    except SemanticError as e:
                        raise SemanticError(f"Const array '{d.name}': {e.message}", node=d)
                    return
                
                elif sem_type.is_struct:
                    # Const struct (non-array)
                    # Validate field count (including nested)
                    self._validate_struct_init(d.initializer, sem_type.struct_info, d.line, d.col, d.filename)
                    
                    # Use effective rd/wr computed earlier
                    sym = Symbol(
                        name=d.name,
                        type=sem_type,
                        is_const=True,
                        is_array=False,
                        array_len=None,
                        init=d.initializer,     # Store init for code gen
                        const_value=None,       # Struct const doesn't have single const_value
                        address=None,
                        is_volatile=False,
                        proc_name=getattr(self.symtab, '_proc_name', ''),
                        array_dims=None,
                        is_port=effective_is_port,
                        port_rd=rd,
                        port_wr=wr,
                        is_keep=getattr(decl, 'keep', False),
                        noexport=getattr(decl, 'noexport', False),
                        export=getattr(decl, 'export', False),
                    )
                    try:
                        self.symtab.define(sym, node=d)
                    except SemanticError as e:
                        raise SemanticError(f"Const struct '{d.name}': {e.message}", node=d)
                    return
                else:
                    raise SemanticError("List initializer only allowed for struct or array types", node=d)
            
            elif isinstance(d.initializer, StringInit):
                # String init for const byte array
                if not is_array:
                    raise SemanticError("String initializer for scalar", node=d)
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", node=d.initializer)
                
                if array_len is None:
                    array_len: int = len(d.initializer.value) + 1
                
                # Use effective rd/wr computed earlier
                sym = Symbol(
                    name=d.name,
                    type=sem_type,
                    is_const=True,
                    is_array=True,
                    array_len=array_len,
                    init=d.initializer,     # Store init for code gen
                    const_value=None,
                    address=None,
                    is_volatile=False,
                    proc_name=getattr(self.symtab, '_proc_name', ''),
                    array_dims=array_dims if array_dims else None,
                    is_port=effective_is_port,
                    port_rd=rd,
                    port_wr=wr,
                    is_keep=getattr(decl, 'keep', False),
                    noexport=getattr(decl, 'noexport', False),
                    export=getattr(decl, 'export', False),
                )
                try:
                    self.symtab.define(sym, node=d)
                except SemanticError as e:
                    raise SemanticError(f"Const string '{d.name}': {e.message}", node=d)
                return
            
            else:
                raise SemanticError("CONST must have initializer (expression, list, or string)", node=d)


        # inicializace pole
        if is_array:
            if isinstance(d.initializer, ListInit):
                # Check if this is a struct array with nested initializers
                is_struct_array: bool = sem_type.is_struct and sem_type.struct_info is not None
                
                if is_struct_array:
                    # For struct arrays, each element should be a nested list matching the struct field count
                    for i in range(len(d.initializer.values)):
                        elem = d.initializer.values[i]
                        # elem may be Expr or InitValue; we only accept ListInit for struct array elements
                        if isinstance(elem, ListInit):
                            self._validate_struct_init(elem, sem_type.struct_info, d.line, d.col, d.filename)
                        else:
                            raise SemanticError(f"Struct array element {i} must be a list initializer", node=d)
                    
                    if array_len is None:
                        array_len = len(d.initializer.values)  # type: ignore[assignment]
                        if array_len == 0:
                            raise SemanticError("Array initializer must have at least one element", node=d.initializer)
                    elif array_len != len(d.initializer.values):
                        size_expr = d.array_sizes[0] if d.array_sizes else d.array_size
                        if size_expr is not None:
                            raise SemanticError("Array initializer size mismatch", node=size_expr)
                        raise SemanticError("Array initializer size mismatch", node=d)

                    # Resolve inferred dimensions in array_dims from initializer
                    if array_dims and None in array_dims:
                        # For struct arrays, infer last dimension
                        inferred_size: int = len(d.initializer.values)
                        array_dims[-1] = inferred_size
                else:
                    # Regular (non-struct) array
                    if array_len is None:
                        array_len = len(d.initializer.values)  # type: ignore[assignment]
                        if array_len == 0:
                            raise SemanticError("Array initializer must have at least one element", node=d.initializer)
                    elif array_len != len(d.initializer.values):
                        size_expr = d.array_sizes[0] if d.array_sizes else d.array_size
                        if size_expr is not None:
                            raise SemanticError("Array initializer size mismatch", node=size_expr)
                        raise SemanticError("Array initializer size mismatch", node=d)
                    
                    # Resolve inferred dimensions in array_dims from initializer
                    if array_dims and None in array_dims:
                        # For regular arrays, infer last dimension
                        inferred_size: int = len(d.initializer.values)
                        array_dims[-1] = inferred_size

            elif isinstance(d.initializer, StringInit):
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", node=d.initializer)

                # Check if string fits in the specified array size
                string_len: int = len(d.initializer.value) + 1  # +1 for NUL terminator
                if array_len is not None and string_len > array_len:
                    raise SemanticError(
                        f"String length {len(d.initializer.value)} + 1 = {string_len} exceeds array size {array_len}",
                        node=d
                    )
                
                if array_len is None:
                    array_len: int = string_len
                
                # Resolve inferred dimensions in array_dims from string initializer
                if array_dims and None in array_dims:
                    # For string arrays, infer size (string length + NUL terminator)
                    inferred_size: int = string_len
                    array_dims[-1] = inferred_size

            elif d.initializer is not None:
                raise SemanticError("Invalid array initializer", node=d)

            # Check if array size is specified (either array_len for 1D or array_dims for multi-dimensional)
            if array_len is None and (not array_dims or None in array_dims):
                raise SemanticError("Array size required", node=d)

        # scalar variable
        else:
            if isinstance(d.initializer, ListInit):
                # ListInit is allowed for struct types for nested initialization
                if not sem_type.is_struct:
                    raise SemanticError("List initializer for scalar", node=d)
                
                # Validate struct field count matches initializer value count (including nested)
                if sem_type.struct_info:
                    self._validate_struct_init(d.initializer, sem_type.struct_info, d.line, d.col, d.filename)

            if isinstance(d.initializer, StringInit):
                raise SemanticError("String initializer for scalar", node=d)
            
            # Check if initializer is a constant that fits in the type
            if isinstance(d.initializer, ExprInit) and isinstance(d.initializer.expr, IntLiteral):
                val: int = d.initializer.expr.value
                # Check range
                if sem_type.base == "BYTE" and not sem_type.is_pointer:
                    if val < 0 or val > 0xFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in BYTE (0-255)",
                            node=d.initializer.expr
                        )
                elif sem_type.base == "WORD" or sem_type.is_pointer:
                    if val < 0 or val > 0xFFFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in WORD (0-65535)",
                            node=d.initializer.expr
                        )
            
            # Type-check all expression initializers to trigger validation
            # (e.g., array bounds checking for subscript expressions)
            if isinstance(d.initializer, ExprInit) and self.func_table is not None:
                from sema_expr import ExprTypeChecker
                
                # Create a scoped symbol table that includes both local and global symbols
                # if global_symtab is available (for local variables), otherwise use symtab as-is
                if self.global_symtab is not None:
                    scoped_symtab = ScopedSymbolTable(self.global_symtab)
                    scoped_symtab.local = self.symtab
                    tc = ExprTypeChecker(scoped_symtab, self.func_table, self.struct_registry)
                else:
                    tc = ExprTypeChecker(self.symtab, self.func_table, self.struct_registry)
                tc.check(d.initializer.expr)

        # Use effective rd/wr computed earlier
        sym = Symbol(
            name=d.name,
            type=sem_type,
            is_const=False,
            const_value=None,
            is_array=is_array,
            array_len=array_len,
            init=d.initializer,
            address=address_val,
            is_volatile=address_val is not None,
            proc_name=getattr(self.symtab, '_proc_name', ''),
            array_dims=array_dims if array_dims else None,
            is_static=decl.is_static or d.is_static,
            is_port=effective_is_port,
            port_rd=rd,
            port_wr=wr,
            is_keep=getattr(decl, 'keep', False),
            noexport=getattr(decl, 'noexport', False),
            export=getattr(decl, 'export', False),
        )


        try:
            self.symtab.define(sym, node=d)
        except SemanticError as e:
            # Re-raise with better context
            raise SemanticError(f"{e.message}", node=d)


class EnumAnalyzer:
    """Analyze enum declarations and expand members into const symbols"""
    def __init__(self, symtab: SymbolTable) -> None:
        """Initialize enum analyzer with a target symbol table."""
        self.symtab: SymbolTable = symtab
        # Registry: enum_name -> { 'base': 'BYTE'|'WORD', 'members': { member_name: value, ... } }
        if not hasattr(self.symtab, '_enums'):
            self.symtab._enums = {}

    def _raise_item_error(self, msg: str, item: EnumItem) -> None:
        """Raise a SemanticError for an enum item with correct file location."""
        err = SemanticError(msg, line=item.line, col=item.col)
        if item.filename:
            err.filename = item.filename
        raise err

    def analyze(self, enum_decl: EnumDecl) -> None:
        """Register an enum and its members for qualified access only (EnumName.Member)."""
        base: str = enum_decl.base.upper() if enum_decl.base else 'BYTE'
        if base not in ("BYTE", "WORD"):
            err = SemanticError(f"Enum base type '{enum_decl.base}' is not supported", line=enum_decl.line, col=enum_decl.col)
            if enum_decl.filename:
                err.filename = enum_decl.filename
            raise err
        current = 0
        seen: set[str] = set()
        members: dict[str, int] = {}
        for item in enum_decl.items:
            # Evaluate explicit value if provided
            if item.value is not None:
                try:
                    val = eval_const_expr(item.value, self.symtab)
                except SemanticError as e:
                    self._raise_item_error(e.message, item)
                    val = 0  # unreachable; satisfies type checker
            else:
                val = current

            # Range check
            if base == "BYTE" and (val < 0 or val > 0xFF):
                self._raise_item_error(f"Enum value {val} out of range for byte", item)
            if base == "WORD" and (val < 0 or val > 0xFFFF):
                self._raise_item_error(f"Enum value {val} out of range for word", item)

            name: str = item.name.upper()
            if name in seen:
                self._raise_item_error(f"Enum member '{item.name}' duplicated in enum '{enum_decl.name}'", item)

            seen.add(name)
            members[name] = val
            current = val + 1

        # Register enum definition for qualified access only (e.g., EnumName.Member)
        # Enum members are NOT added to the global symbol table — they are only
        # accessible via the qualified syntax EnumName.Member.
        self.symtab._enums[enum_decl.name.upper()] = {'base': base, 'members': members}



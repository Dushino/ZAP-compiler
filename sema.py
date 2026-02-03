# 

from symbols import SemType, Symbol, SymbolTable, StructRegistry, StructInfo, StructFieldInfo
from errors import *
from ast_nodes import IntLiteral, Identifier, DerefExpr, BinaryExpr, BinOp
from ast_nodes import ListInit, StringInit, ExprInit
from ast_nodes import Declaration, Declarator, StructDef, StructField


def eval_const_expr(expr, symtab=None):
    if isinstance(expr, IntLiteral):
        return expr.value
    
    # Handle identifiers - look up const variables
    if isinstance(expr, Identifier):
        if symtab is None:
            raise SemanticError("Constant expression required")
        sym = symtab.lookup(expr.name)
        if sym is None:
            raise SemanticError(f"Undefined identifier: {expr.name}")
        if not sym.is_const:
            raise SemanticError(f"'{expr.name}' is not a const")
        if sym.const_value is None:
            raise SemanticError(f"'{expr.name}' const has no value")
        return sym.const_value
    
    if isinstance(expr, BinaryExpr):
        left = eval_const_expr(expr.left, symtab)
        right = eval_const_expr(expr.right, symtab)
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
            raise SemanticError("Unsupported operation in constant expression")
    raise SemanticError("Constant expression required")


def eval_array_dimensions(array_sizes, symtab, d_obj=None):
    """Extract and evaluate array dimensions from Declarator
    
    Returns: (is_array, array_dims, array_len)
      - is_array: True if this is an array
      - array_dims: List[int] for multi-dimensional arrays ([3, 4, 5])
      - array_len: int for backward compat with 1D arrays
    """
    is_array = False
    array_dims = []
    array_len = None
    
    if array_sizes:
        # Multi-dimensional array
        is_array = True
        for size_expr in array_sizes:
            try:
                sz_val = eval_const_expr(size_expr, symtab)
            except SemanticError as e:
                line = getattr(d_obj, 'line', 0)
                col = getattr(d_obj, 'col', 0)
                raise SemanticError(e.message, line=line, col=col)
            
            if sz_val == -1:
                # [] → will be inferred from initializer
                array_dims.append(None)
            elif sz_val <= 0:
                line = getattr(d_obj, 'line', 0)
                col = getattr(d_obj, 'col', 0)
                raise SemanticError("Array dimension must be positive", line=line, col=col)
            else:
                array_dims.append(sz_val)
        
        # For backward compatibility, set array_len to first dimension if all are known
        if array_dims and all(d is not None for d in array_dims):
            array_len = array_dims[0] if len(array_dims) == 1 else None
    
    return is_array, array_dims, array_len



class StructAnalyzer:
    """Analyzes and registers struct definitions"""
    def __init__(self, struct_registry: StructRegistry):
        self.registry = struct_registry

    def analyze(self, struct_def: StructDef):
        """Analyze a struct definition and register it"""
        # Calculate field offsets
        fields: list[StructFieldInfo] = []
        current_offset = 0

        for field_ast in struct_def.fields:
            # Get field type
            field_type = field_ast.type.base.upper()
            is_pointer = field_ast.type.is_pointer

            # Get element width (for a single element, not array)
            if field_type == "BYTE":
                elem_width = 1
            elif field_type == "WORD":
                elem_width = 2
            elif field_type in self.registry._structs:
                # Nested struct type
                nested_struct = self.registry._structs[field_type]
                elem_width = nested_struct.size
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
                raise SemanticError(f"Unsupported field type '{field_type}' in struct")

            if is_pointer and elem_width != 2:
                # Pointers should be 2 bytes
                elem_width = 2

            # Evaluate array dimensions if present
            array_sizes = None
            if field_ast.array_sizes:
                array_sizes = []
                for size_expr in field_ast.array_sizes:
                    try:
                        size = eval_const_expr(size_expr)
                        array_sizes.append(size)
                    except SemanticError as e:
                        raise SemanticError(f"Invalid array size in struct field '{field_ast.name}': {e.message}")

            # Calculate total width
            width = elem_width
            if array_sizes:
                total_elements = 1
                for size in array_sizes:
                    total_elements *= size
                width = elem_width * total_elements

            # Evaluate fixed address if present
            fixed_addr = None
            if field_ast.address is not None:
                try:
                    fixed_addr = eval_const_expr(field_ast.address)
                except SemanticError as e:
                    raise SemanticError(f"Invalid field address: {e.message}")

            # Create field info
            field_info = StructFieldInfo(
                name=field_ast.name.upper(),
                base_type=field_type,
                is_pointer=is_pointer,
                offset=current_offset,
                fixed_address=fixed_addr,
                array_sizes=array_sizes
            )
            fields.append(field_info)
            current_offset += width

        # Create and register struct
        struct_info = StructInfo(
            name=struct_def.name.upper(),
            fields=fields,
            size=current_offset
        )

        try:
            self.registry.define(struct_info)
        except SemanticError as e:
            # Attach struct definition source location if available
            raise SemanticError(f"Struct definition error: {e.message}", line=struct_def.line, col=struct_def.col)



class DeclarationAnalyzer:
    def __init__(self, symtab: SymbolTable, struct_registry=None, func_table=None, global_symtab=None):
        self.symtab = symtab
        self.struct_registry = struct_registry
        self.func_table = func_table
        self.global_symtab = global_symtab

    def analyze(self, decl: Declaration):
        # Check if this is a struct type or a built-in type
        base_name = decl.type.base.upper()
        is_struct = False
        struct_info = None
        
        if self.struct_registry and self.struct_registry.is_defined(base_name):
            is_struct = True
            struct_info = self.struct_registry.lookup(base_name)
        
        sem_type = SemType(
            base=decl.type.base,
            is_pointer=decl.type.is_pointer,
            is_struct=is_struct,
            struct_info=struct_info
        )

        for d in decl.declarators:
            self._analyze_declarator(decl, d, sem_type)

    def _validate_struct_init(self, init: ListInit, struct_info, line: int, col: int):
        """Recursively validate struct initializer has correct field count and nested structs."""
        num_fields = len(struct_info.fields)
        num_values = len(init.values)
        
        if num_values != num_fields:
            raise SemanticError(
                f"Struct '{struct_info.name}' has {num_fields} field(s) but {num_values} value(s) provided",
                line=line, col=col
            )
        
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
                    self._validate_struct_init(value, nested_struct_info, line, col)

    def _analyze_declarator(
        self,
        decl: Declaration,
        d: Declarator,
        sem_type: SemType
        ):

        # Validate STATIC modifier
        if decl.is_static or d.is_static:
            # STATIC can only be used on local variables (proc_name must be set)
            if not getattr(self.symtab, '_proc_name', ''):
                raise SemanticError("STATIC modifier can only be used on local variables", line=d.line, col=d.col)
            
            # STATIC cannot be used on const variables
            if decl.is_const:
                raise SemanticError("STATIC and CONST modifiers cannot be combined", line=d.line, col=d.col)
            
            # STATIC variables must have an initializer
            if d.initializer is None:
                raise SemanticError("STATIC variable must have an initializer", line=d.line, col=d.col)

        # Validate PORT modifier
        if decl.is_port:
            # PORT cannot be combined with CONST
            if decl.is_const:
                raise SemanticError("PORT and CONST modifiers cannot be combined", line=d.line, col=d.col)
            
            # PORT cannot be combined with STATIC
            if decl.is_static or d.is_static:
                raise SemanticError("PORT and STATIC modifiers cannot be combined", line=d.line, col=d.col)
            
            # PORT requires an address specification (@)
            if d.address is None:
                raise SemanticError("PORT modifier requires address specification with @", line=d.line, col=d.col)
            
            # PORT cannot be used on arrays
            if d.array_size is not None or d.array_sizes is not None:
                raise SemanticError("PORT modifier cannot be used on arrays", line=d.line, col=d.col)
            
            # PORT cannot be used on pointers
            if decl.type.is_pointer:
                raise SemanticError("PORT modifier cannot be used on pointers", line=d.line, col=d.col)
            
            # PORT cannot have initializers (hardware ports can't be initialized)
            if d.initializer is not None:
                raise SemanticError("PORT variable cannot have initializer", line=d.line, col=d.col)

        # RD/WR modifiers must be used together with #PORT
        if (getattr(decl, 'port_rd', False) or getattr(decl, 'port_wr', False)) and not decl.is_port:
            raise SemanticError("#RD and #WR modifiers are only valid on #PORT declarations", line=d.line, col=d.col)

        # Extract array dimensions (supports multi-dimensional arrays)
        array_sizes_to_eval = d.array_sizes if d.array_sizes else (
            [d.array_size] if d.array_size is not None else []
        )
        
        is_array, array_dims, array_len = eval_array_dimensions(array_sizes_to_eval, self.symtab, d)
        
        address_val = None

        if d.address is not None:
            address_val = eval_const_expr(d.address, self.symtab)

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

        # const pravidla
        if decl.is_const:
            if d.address is not None:
                raise SemanticError("CONST cannot have address", line=d.line, col=d.col)
            
            # CONST can have expression initializer (scalars), ListInit (structs/arrays), or StringInit (byte arrays)
            if isinstance(d.initializer, ExprInit):
                # Scalar const: must have evaluable expression
                try:
                    val = eval_const_expr(d.initializer.expr, self.symtab)
                except SemanticError as e:
                    raise SemanticError(e.message, line=d.line, col=d.col)
                
                # Check if constant fits in its type
                if sem_type.base == "BYTE" and not sem_type.is_pointer:
                    if val < 0 or val > 0xFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in BYTE (0-255)",
                            line=d.line, col=d.col
                        )
                elif sem_type.base == "WORD" or sem_type.is_pointer:
                    if val < 0 or val > 0xFFFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in WORD (0-65535)",
                            line=d.line, col=d.col
                        )

                rd = getattr(decl, 'port_rd', False)
                wr = getattr(decl, 'port_wr', False)
                if decl.is_port and not (rd or wr):
                    rd = wr = True
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
                    is_port=decl.is_port,
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
                    raise SemanticError(f"Constant '{d.name}': {e.message}", line=d.line, col=d.col)
                return
            
            elif isinstance(d.initializer, ListInit):
                # ListInit for const: can be struct or array
                if is_array:
                    # Const array with ListInit
                    if array_len is None:
                        array_len = len(d.initializer.values)
                    elif array_len != len(d.initializer.values):
                        raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)
                    
                    rd = getattr(decl, 'port_rd', False)
                    wr = getattr(decl, 'port_wr', False)
                    if decl.is_port and not (rd or wr):
                        rd = wr = True
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
                        is_port=decl.is_port,
                        port_rd=rd,
                        port_wr=wr,
                        is_keep=getattr(decl, 'keep', False),
                        noexport=getattr(decl, 'noexport', False),
                        export=getattr(decl, 'export', False),
                    )
                    try:
                        self.symtab.define(sym)
                    except SemanticError as e:
                        raise SemanticError(f"Const array '{d.name}': {e.message}", line=d.line, col=d.col)
                    return
                
                elif sem_type.is_struct:
                    # Const struct (non-array)
                    # Validate field count (including nested)
                    self._validate_struct_init(d.initializer, sem_type.struct_info, d.line, d.col)
                    
                    rd = getattr(decl, 'port_rd', False)
                    wr = getattr(decl, 'port_wr', False)
                    if decl.is_port and not (rd or wr):
                        rd = wr = True
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
                        is_port=decl.is_port,
                        port_rd=rd,
                        port_wr=wr,
                        is_keep=getattr(decl, 'keep', False),
                        noexport=getattr(decl, 'noexport', False),
                        export=getattr(decl, 'export', False),
                    )
                    try:
                        self.symtab.define(sym)
                    except SemanticError as e:
                        raise SemanticError(f"Const struct '{d.name}': {e.message}", line=d.line, col=d.col)
                    return
                else:
                    raise SemanticError("List initializer only allowed for struct or array types", line=d.line, col=d.col)
            
            elif isinstance(d.initializer, StringInit):
                # String init for const byte array
                if not is_array:
                    raise SemanticError("String initializer for scalar", line=d.line, col=d.col)
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", line=d.line, col=d.col)
                
                if array_len is None:
                    array_len = len(d.initializer.value) + 1
                
                rd = getattr(decl, 'port_rd', False)
                wr = getattr(decl, 'port_wr', False)
                if decl.is_port and not (rd or wr):
                    rd = wr = True
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
                    is_port=decl.is_port,
                    port_rd=rd,
                    port_wr=wr,
                    is_keep=getattr(decl, 'keep', False),
                    noexport=getattr(decl, 'noexport', False),
                    export=getattr(decl, 'export', False),
                )
                try:
                    self.symtab.define(sym)
                except SemanticError as e:
                    raise SemanticError(f"Const string '{d.name}': {e.message}", line=d.line, col=d.col)
                return
            
            else:
                raise SemanticError("CONST must have initializer (expression, list, or string)", line=d.line, col=d.col)


        # inicializace pole
        if is_array:
            if isinstance(d.initializer, ListInit):
                # Check if this is a struct array with nested initializers
                is_struct_array = sem_type.is_struct and sem_type.struct_info is not None
                
                if is_struct_array:
                    # For struct arrays, each element should be a nested list matching the struct field count
                    for i, val in enumerate(d.initializer.values):
                        if isinstance(val, ListInit):
                            self._validate_struct_init(val, sem_type.struct_info, d.line, d.col)
                        else:
                            raise SemanticError(f"Struct array element {i} must be a list initializer", line=d.line, col=d.col)
                    
                    if array_len is None:
                        array_len = len(d.initializer.values)
                    elif array_len != len(d.initializer.values):
                        raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)
                    
                    # Resolve inferred dimensions in array_dims from initializer
                    if array_dims and None in array_dims:
                        # For struct arrays, infer last dimension
                        inferred_size = len(d.initializer.values)
                        array_dims[-1] = inferred_size
                else:
                    # Regular (non-struct) array
                    if array_len is None:
                        array_len = len(d.initializer.values)
                    elif array_len != len(d.initializer.values):
                        raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)
                    
                    # Resolve inferred dimensions in array_dims from initializer
                    if array_dims and None in array_dims:
                        # For regular arrays, infer last dimension
                        inferred_size = len(d.initializer.values)
                        array_dims[-1] = inferred_size

            elif isinstance(d.initializer, StringInit):
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", line=d.line, col=d.col)
                
                # Check if string fits in the specified array size
                string_len = len(d.initializer.value) + 1  # +1 for NUL terminator
                if array_len is not None and string_len > array_len:
                    raise SemanticError(
                        f"String length {len(d.initializer.value)} + 1 (NUL) = {string_len} exceeds array size {array_len}",
                        line=d.line, col=d.col
                    )
                
                if array_len is None:
                    array_len = string_len
                
                # Resolve inferred dimensions in array_dims from string initializer
                if array_dims and None in array_dims:
                    # For string arrays, infer size (string length + NUL terminator)
                    inferred_size = string_len
                    array_dims[-1] = inferred_size

            elif d.initializer is not None:
                raise SemanticError("Invalid array initializer", line=d.line, col=d.col)

            # Check if array size is specified (either array_len for 1D or array_dims for multi-dimensional)
            if array_len is None and (not array_dims or None in array_dims):
                raise SemanticError("Array size required", line=d.line, col=d.col)

        # skalární proměnná
        else:
            if isinstance(d.initializer, ListInit):
                # ListInit is allowed for struct types for nested initialization
                if not sem_type.is_struct:
                    raise SemanticError("List initializer for scalar", line=d.line, col=d.col)
                
                # Validate struct field count matches initializer value count (including nested)
                if sem_type.struct_info:
                    self._validate_struct_init(d.initializer, sem_type.struct_info, d.line, d.col)

            if isinstance(d.initializer, StringInit):
                raise SemanticError("String initializer for scalar", line=d.line, col=d.col)
            
            # Check if initializer is a constant that fits in the type
            if isinstance(d.initializer, ExprInit) and isinstance(d.initializer.expr, IntLiteral):
                val = d.initializer.expr.value
                # Check range
                if sem_type.base == "BYTE" and not sem_type.is_pointer:
                    if val < 0 or val > 0xFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in BYTE (0-255)",
                            line=d.line, col=d.col
                        )
                elif sem_type.base == "WORD" or sem_type.is_pointer:
                    if val < 0 or val > 0xFFFF:
                        raise SemanticError(
                            f"Constant value {val} (0x{val:X}) does not fit in WORD (0-65535)",
                            line=d.line, col=d.col
                        )
            
            # Type-check all expression initializers to trigger validation
            # (e.g., array bounds checking for subscript expressions)
            if isinstance(d.initializer, ExprInit) and self.func_table is not None:
                from sema_expr import ExprTypeChecker
                from symbols import ScopedSymbolTable
                
                # Create a scoped symbol table that includes both local and global symbols
                # if global_symtab is available (for local variables), otherwise use symtab as-is
                if self.global_symtab is not None:
                    scoped_symtab = ScopedSymbolTable(self.global_symtab)
                    scoped_symtab.local = self.symtab
                    tc = ExprTypeChecker(scoped_symtab, self.func_table, self.struct_registry)
                else:
                    tc = ExprTypeChecker(self.symtab, self.func_table, self.struct_registry)
                tc.check(d.initializer.expr)

        rd = getattr(decl, 'port_rd', False)
        wr = getattr(decl, 'port_wr', False)
        if decl.is_port and not (rd or wr):
            rd = wr = True
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
            is_port=decl.is_port,
            port_rd=rd,
            port_wr=wr,
            is_keep=getattr(decl, 'keep', False),
            noexport=getattr(decl, 'noexport', False),
            export=getattr(decl, 'export', False),
        )

        try:
            self.symtab.define(sym)
        except SemanticError as e:
            # Re-raise with better context
            raise SemanticError(f"{e.message}", line=d.line, col=d.col)


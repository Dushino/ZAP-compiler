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

            # Get field width
            if field_type == "BYTE":
                width = 1
            elif field_type == "WORD":
                width = 2
            elif field_type in self.registry._structs:
                # Nested struct type
                nested_struct = self.registry._structs[field_type]
                width = nested_struct.size
            elif is_pointer and field_type == struct_def.name.upper():
                # Self-referential struct pointer (or forward-referenced struct)
                # Pointers are always 16-bit (2 bytes)
                width = 2
            elif is_pointer:
                # Forward reference to struct type (will be resolved later or error at use time)
                # For now, assume pointer size (2 bytes)
                width = 2
            else:
                # Unknown non-pointer type
                raise SemanticError(f"Unsupported field type '{field_type}' in struct")

            if is_pointer and width != 2:
                # Pointers should be 2 bytes
                width = 2

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
                fixed_address=fixed_addr
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
            raise SemanticError(f"Struct definition error: {e.message}")


class DeclarationAnalyzer:
    def __init__(self, symtab: SymbolTable, struct_registry=None):
        self.symtab = symtab
        self.struct_registry = struct_registry

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

    def _analyze_declarator(
        self,
        decl: Declaration,
        d: Declarator,
        sem_type: SemType
        ):

        # pole
        is_array = d.array_size is not None
        array_len = None
        address_val = None

        if d.address is not None:
            address_val = eval_const_expr(d.address, self.symtab)

        if is_array:
            try:
                sz_val = eval_const_expr(d.array_size, self.symtab)
            except SemanticError as e:
                raise SemanticError(e.message, line=d.line, col=d.col)
            if sz_val == -1:
                # [] → infer size
                array_len = None
            elif sz_val <= 0:
                raise SemanticError("Array size must be positive", line=d.line, col=d.col)
            else:
                array_len = sz_val

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
                    proc_name=getattr(self.symtab, '_proc_name', '')
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
                        proc_name=getattr(self.symtab, '_proc_name', '')
                    )
                    try:
                        self.symtab.define(sym)
                    except SemanticError as e:
                        raise SemanticError(f"Const array '{d.name}': {e.message}", line=d.line, col=d.col)
                    return
                
                elif sem_type.is_struct:
                    # Const struct (non-array)
                    # Validate field count
                    num_fields = len(sem_type.struct_info.fields)
                    if len(d.initializer.values) != num_fields:
                        raise SemanticError(f"Struct initializer has {len(d.initializer.values)} values, expected {num_fields}", line=d.line, col=d.col)
                    
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
                        proc_name=getattr(self.symtab, '_proc_name', '')
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
                    proc_name=getattr(self.symtab, '_proc_name', '')
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
                    num_fields = len(sem_type.struct_info.fields)
                    for i, val in enumerate(d.initializer.values):
                        if isinstance(val, ListInit):
                            if len(val.values) != num_fields:
                                raise SemanticError(f"Struct initializer has {len(val.values)} values, expected {num_fields}", line=d.line, col=d.col)
                        else:
                            raise SemanticError(f"Struct array element {i} must be a list initializer", line=d.line, col=d.col)
                    
                    if array_len is None:
                        array_len = len(d.initializer.values)
                    elif array_len != len(d.initializer.values):
                        raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)
                else:
                    # Regular (non-struct) array
                    if array_len is None:
                        array_len = len(d.initializer.values)
                    elif array_len != len(d.initializer.values):
                        raise SemanticError("Array initializer size mismatch", line=d.line, col=d.col)

            elif isinstance(d.initializer, StringInit):
                if sem_type.base.lower() != "byte":
                    raise SemanticError("String only allowed for byte array", line=d.line, col=d.col)
                if array_len is None:
                    array_len = len(d.initializer.value) + 1

            elif d.initializer is not None:
                raise SemanticError("Invalid array initializer", line=d.line, col=d.col)

            if array_len is None:
                raise SemanticError("Array size required", line=d.line, col=d.col)

        # skalární proměnná
        else:
            if isinstance(d.initializer, ListInit):
                # ListInit is allowed for struct types for nested initialization
                if not sem_type.is_struct:
                    raise SemanticError("List initializer for scalar", line=d.line, col=d.col)

            if isinstance(d.initializer, StringInit):
                raise SemanticError("String initializer for scalar", line=d.line, col=d.col)

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
            proc_name=getattr(self.symtab, '_proc_name', '')
        )

        try:
            self.symtab.define(sym)
        except SemanticError as e:
            # Re-raise with better context
            raise SemanticError(f"{e.message}", line=d.line, col=d.col)


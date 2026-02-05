from typing import Literal
from typing import Literal
from symbols import FuncSymbol, SemType, SemType, Symbol, Symbol, StructInfo, Symbol, SymbolLookup, FuncTable
from sema import SemanticError
from sema_types import ExprKind, ExprType
from ast_nodes import Expr, Expr, IntLiteral, Identifier, DerefExpr, CallExpr
from ast_nodes import BinaryExpr, UnaryExpr, BinOp, UnOp, SubscriptExpr, FieldAccess


def promote(a: SemType, b: SemType) -> SemType:
    if a.base == "WORD" or b.base == "WORD":
        return SemType("WORD", False)
    return SemType("BYTE", False)


class ExprTypeChecker:
    def __init__(self, symtab: SymbolLookup, func_table: FuncTable, struct_registry=None) -> None:
        self.symtab: SymbolLookup = symtab
        self.func_table: FuncTable = func_table
        self.struct_registry = struct_registry

    def check(self, expr, read_check_enabled: bool = True) -> ExprType:
        if isinstance(expr, IntLiteral):
            # Small literals (0-255) are BYTE, larger are WORD
            if 0 <= expr.value <= 255:
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)
            else:
                return ExprType(SemType("WORD", False), ExprKind.VALUE)

        if isinstance(expr, Identifier):
            try:
                sym: Symbol = self.symtab.lookup(expr.name)
            except KeyError:
                raise SemanticError(f"Variable '{expr.name}' is not defined", node=expr)
            if sym.is_array:
                # Array addresses are 16-bit pointers even if they point to BYTE
                # But preserve struct information
                return ExprType(
                    SemType(
                        base=sym.type.base,
                        is_pointer=True,
                        is_struct=sym.type.is_struct,
                        struct_info=sym.type.struct_info
                    ),
                    ExprKind.ADDR
                )

            if sym.type.is_pointer:
                return ExprType(
                    sym.type,        # ← PONECHAT is_pointer = True
                    ExprKind.ADDR
                )

            # This is a read (value) use of the identifier - enforce read permission for ports
            if sym.is_port and not getattr(sym, 'port_rd', False) and read_check_enabled:
                raise SemanticError("Read from write-only port", node=expr)

            return ExprType(sym.type, ExprKind.VALUE)

        if isinstance(expr, DerefExpr):
            base: ExprType = self.check(expr.pointer, read_check_enabled=read_check_enabled)
            if base.kind != ExprKind.ADDR or not base.sem_type.is_pointer:
                raise SemanticError("Cannot dereference non-pointer", node=expr)
            
            # When dereferencing, preserve struct information if the pointed-to type is a struct
            result_type = SemType(
                base=base.sem_type.base,
                is_pointer=False,
                is_struct=base.sem_type.is_struct,
                struct_info=base.sem_type.struct_info
            )
            return ExprType(result_type, ExprKind.LVALUE)

        if isinstance(expr, SubscriptExpr):
            arr_t: ExprType = self.check(expr.array, read_check_enabled=read_check_enabled)
            if arr_t.kind != ExprKind.ADDR:
                raise SemanticError("Subscript requires array address", node=expr)
            
            # Check if index is a constant and validate bounds
            if isinstance(expr.index, IntLiteral):
                self._check_array_bounds(expr, expr.index.value)
            
            # Check if this is a multi-dimensional array
            # For multi-dimensional arrays, partial subscripting returns ADDR (pointer to next dimension)
            # Only final subscript returns LVALUE (actual element)
            
            # Helper function to count subscript depth and find base array
            def get_subscript_info(sub_expr) -> tuple[str, int, Literal[False]] | tuple[FieldAccess, int, Literal[True]] | tuple[None, int, Literal[False]]:
                """Returns (base_identifier, subscript_depth, base_is_field_access)"""
                depth = 0
                current = sub_expr
                while isinstance(current, SubscriptExpr):
                    depth += 1
                    current: Expr = current.array
                if isinstance(current, Identifier):
                    return current.name, depth, False
                elif isinstance(current, FieldAccess):
                    return current, depth, True
                return None, depth, False
            
            base_info, current_depth, is_field_access = get_subscript_info(expr)
            
            if base_info and not is_field_access:
                # We found a base array identifier - check its dimensions
                if isinstance(base_info, str):
                    try:
                        arr_sym: Symbol = self.symtab.lookup(base_info)
                        if arr_sym.is_array and arr_sym.array_dims and len(arr_sym.array_dims) > current_depth:
                            # More dimensions remain after this subscript - return ADDR
                            elem_type = SemType(
                                base=arr_t.sem_type.base,
                                is_pointer=True,  # Returns a pointer to next dimension
                                is_struct=arr_t.sem_type.is_struct,
                                struct_info=arr_t.sem_type.struct_info
                            )
                            return ExprType(elem_type, ExprKind.ADDR)
                    except (KeyError, AttributeError):
                        pass
            elif base_info and is_field_access:
                # We have a field access as base - check if the field has multiple dimensions
                if isinstance(base_info, FieldAccess):
                    field_access_expr: FieldAccess = base_info
                    # Get the field info from the struct registry
                    if not self.struct_registry:
                        pass  # Will default to LVALUE below
                    else:
                        try:
                            # Check the object type
                            obj_type: ExprType = self.check(field_access_expr.object, read_check_enabled=read_check_enabled)
                            
                            # Get struct info
                            if field_access_expr.is_deref:
                                base_type_name: str = obj_type.sem_type.base
                            else:
                                base_type_name: str = obj_type.sem_type.base
                            
                            struct_info = self.struct_registry.lookup(base_type_name.upper())
                            if struct_info:
                                field_info = struct_info.get_field(field_access_expr.field.upper())
                                if field_info and field_info.array_sizes and len(field_info.array_sizes) > current_depth:
                                    # More dimensions remain after this subscript - return ADDR
                                    elem_type = SemType(
                                        base=arr_t.sem_type.base,
                                        is_pointer=True,  # Returns a pointer to next dimension
                                        is_struct=arr_t.sem_type.is_struct,
                                        struct_info=arr_t.sem_type.struct_info
                                    )
                                    return ExprType(elem_type, ExprKind.ADDR)
                        except (KeyError, AttributeError, SemanticError):
                            pass
            
            # Single-dimensional array or final subscript of multi-dimensional array
            # array element is LVALUE of base type
            # Preserve is_struct and struct_info from array element type
            elem_type = SemType(
                base=arr_t.sem_type.base,
                is_pointer=False,
                is_struct=arr_t.sem_type.is_struct,
                struct_info=arr_t.sem_type.struct_info
            )
            return ExprType(elem_type, ExprKind.LVALUE)

        if isinstance(expr, BinaryExpr):
            lt: ExprType = self.check(expr.left)
            rt: ExprType = self.check(expr.right)
            op: BinOp = expr.op

            # Convert LVALUE to VALUE when used in expression context (reading)
            # LVALUE means "location that can be written to", but when used in
            # an expression, we're reading from it (e.g., ptr^ + 1 or arr[i] + 1)
            if lt.kind == ExprKind.LVALUE:
                lt = ExprType(lt.sem_type, ExprKind.VALUE)
            if rt.kind == ExprKind.LVALUE:
                rt = ExprType(rt.sem_type, ExprKind.VALUE)

            # aritmetika
            if op in {
                BinOp.ADD, BinOp.SUB, BinOp.MUL, BinOp.DIV, BinOp.MOD
            }:
                # Check for division/modulo by zero
                if op in {BinOp.DIV, BinOp.MOD} and isinstance(expr.right, IntLiteral):
                    if expr.right.value == 0:
                        raise SemanticError("Division by zero", node=expr.right)
                
                if lt.kind == ExprKind.ADDR or rt.kind == ExprKind.ADDR:
                    if op in (BinOp.ADD, BinOp.SUB):
                        if lt.kind == ExprKind.ADDR and rt.kind == ExprKind.VALUE:
                            return ExprType(lt.sem_type, ExprKind.ADDR)
                        if lt.kind == ExprKind.VALUE and rt.kind == ExprKind.ADDR:
                            return ExprType(rt.sem_type, ExprKind.ADDR)
                    raise SemanticError("Invalid pointer arithmetic", node=expr)

                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

            # relační
            if op in {
                BinOp.EQ, BinOp.NE,
                BinOp.LT, BinOp.GT, BinOp.LE, BinOp.GE
            }:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Comparison requires values", node=expr)
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # logické
            if op in {BinOp.LAND, BinOp.LOR}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Logical operator requires values", node=expr)
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # bitové
            if op in {BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.LSHIFT, BinOp.RSHIFT}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Bitwise operator requires values", node=expr)
                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

        # unární OP
        if isinstance(expr, UnaryExpr):
            # Handle address-of operator (@)
            if expr.op == UnOp.ADDROF:
                # @ can only be applied to lvalues (variables, array elements, struct fields)
                operand_t: ExprType = self.check(expr.expr)
                
                # Check that operand is addressable
                if isinstance(expr.expr, Identifier):
                    # Variable address - always valid
                    pass
                elif isinstance(expr.expr, SubscriptExpr):
                    # Array element address - valid
                    pass
                elif isinstance(expr.expr, FieldAccess):
                    # Struct field address - valid
                    pass
                else:
                    raise SemanticError("Cannot take address of this expression", node=expr)
                
                # Address-of always returns WORD pointer to the operand's type
                base_type: str = operand_t.sem_type.base
                is_struct: bool = operand_t.sem_type.is_struct
                struct_info: StructInfo | None = operand_t.sem_type.struct_info
                
                return ExprType(
                    SemType(base=base_type, is_pointer=True, is_struct=is_struct, struct_info=struct_info),
                    ExprKind.ADDR
                )
            
            t: ExprType = self.check(expr.expr)
            # Convert LVALUE to VALUE when reading (e.g., !ptr^ or -ptr^ or ~ptr^)
            if t.kind == ExprKind.LVALUE:
                t = ExprType(t.sem_type, ExprKind.VALUE)
            if t.kind != ExprKind.VALUE:
                raise SemanticError("Unary operator requires value", node=expr)
            
            # For bitwise NOT (~), preserve the operand type
            if expr.op.value == "~":
                return ExprType(t.sem_type, ExprKind.VALUE)
            
            # For logical NOT (!), return BYTE
            return ExprType(SemType("BYTE", False), ExprKind.VALUE)

        # funkce
        if isinstance(expr, CallExpr):
            fs: FuncSymbol = self.func_table.lookup(expr.name)
            # Allow arguments from required_params to param_count
            if len(expr.args) < fs.required_params or len(expr.args) > fs.param_count:
                raise SemanticError(
                    f"Function '{expr.name}' expects {fs.param_count} parameters, "
                    f"but {len(expr.args)} were provided",
                    node=expr
                )
            return ExprType(fs.ret_type, ExprKind.VALUE)

        # struct field access: obj.field or ptr^.field
        if isinstance(expr, FieldAccess):
            # First, check for qualified enum access: EnumName.Member
            if isinstance(expr.object, Identifier):
                enums = getattr(self.symtab, '_enums', None)
                # If symtab is a ScopedSymbolTable, check parent for enums
                if enums is None:
                    parent = getattr(self.symtab, 'parent', None)
                    if parent is not None:
                        enums = getattr(parent, '_enums', None)
                if enums and expr.object.name.upper() in enums:
                    enum_def = enums[expr.object.name.upper()]
                    if expr.field.upper() not in enum_def['members']:
                        raise SemanticError(f"Enum '{expr.object.name}' has no member '{expr.field}'", node=expr)
                    # Return value with enum base type
                    return ExprType(SemType(enum_def['base'], False), ExprKind.VALUE)

            if not self.struct_registry:
                raise SemanticError("Struct registry not available", node=expr)
            
            # Check the object type
            obj_type: ExprType = self.check(expr.object, read_check_enabled=read_check_enabled)
            
            # For deref field access (ptr^.field), object is a DerefExpr which is LVALUE of struct type
            # For direct field access (obj.field), object can be LVALUE or VALUE of struct type
            if obj_type.kind not in (ExprKind.VALUE, ExprKind.LVALUE):
                raise SemanticError("Field access requires struct value or lvalue", node=expr)
            
            base_type_name: str = obj_type.sem_type.base
            
            # Look up struct definition
            struct_info = self.struct_registry.lookup(base_type_name.upper())
            if not struct_info:
                raise SemanticError(f"'{base_type_name}' is not a defined struct", node=expr)
            
            # Look up field
            field_info = struct_info.get_field(expr.field.upper())
            if not field_info:
                raise SemanticError(f"Struct '{base_type_name}' has no field '{expr.field}'", node=expr)
            
            # Create field type, preserving struct information if the field is a struct
            field_sem_type = SemType(field_info.base_type, field_info.is_pointer)
            
            # If field is a nested struct, look it up and create SemType with struct_info
            if field_info.base_type.upper() in self.struct_registry._structs:
                nested_struct = self.struct_registry.lookup(field_info.base_type.upper())
                field_sem_type = SemType(field_info.base_type, field_info.is_pointer, 
                                        is_struct=True, struct_info=nested_struct)
            
            # If field is an array, return ADDR (pointer to array), not LVALUE
            if field_info.array_sizes:
                # Address-of an array field - still treat as ADDR; no read permission check here
                return ExprType(field_sem_type, ExprKind.ADDR)

            # Enforce read permission for port-mapped struct variables' fields when possible
            base_sym = None
            try:
                # obj.field where obj is Identifier
                if isinstance(expr.object, Identifier):
                    base_sym = self.symtab.lookup(expr.object.name)
                # ptr^.field where ptr is Identifier pointing to struct variable
                elif expr.is_deref and isinstance(expr.object, DerefExpr) and isinstance(expr.object.pointer, Identifier):
                    base_sym = self.symtab.lookup(expr.object.pointer.name)
            except (AttributeError, KeyError):
                base_sym = None

            if base_sym is not None and getattr(base_sym, 'is_port', False) and read_check_enabled:
                # Field-level override: if any field-level modifier is present, treat unspecified as False
                if field_info.port_rd is not None or field_info.port_wr is not None:
                    allowed = bool(field_info.port_rd)
                else:
                    # Fall back to symbol-level flags (already resolved with declaration/struct defaults)
                    allowed = getattr(base_sym, 'port_rd', False)
                if not allowed:
                        raise SemanticError("Read from write-only port", node=expr)

            return ExprType(field_sem_type, ExprKind.LVALUE)

        # chyba
        raise SemanticError(
            f"Unsupported expression type: {type(expr).__name__}",
            node=expr
        )

    def _check_array_bounds(self, subscript_expr: SubscriptExpr, index_value: int) -> None:
        """Check if a constant array index is within bounds.
        
        For multi-dimensional arrays, finds the base array and checks the index
        against the appropriate dimension based on subscript depth.
        """
        # Helper to get base array info and subscript depth
        def get_subscript_info(sub_expr) -> tuple[str, int, Literal[False], None] | tuple[None, int, Literal[True], FieldAccess] | tuple[None, int, Literal[False], None]:
            """Returns (base_identifier, subscript_depth, is_field_access, base_field_access)"""
            depth = 0
            current = sub_expr
            while isinstance(current, SubscriptExpr):
                depth += 1
                current: Expr = current.array
            if isinstance(current, Identifier):
                return current.name, depth, False, None
            elif isinstance(current, FieldAccess):
                return None, depth, True, current
            return None, depth, False, None
        
        base_name, depth, is_field_access, field_access_expr = get_subscript_info(subscript_expr)
        
        # Check negative indices
        if index_value < 0:
            raise SemanticError(f"Array index cannot be negative: {index_value}", node=subscript_expr)
        
        # For regular array identifiers
        if base_name and not is_field_access:
            try:
                arr_sym: Symbol = self.symtab.lookup(base_name)
                if arr_sym.is_array:
                    # Get the dimension to check based on subscript depth
                    # depth=1 means first subscript, check first dimension
                    dim_index: int = depth - 1
                    
                    if arr_sym.array_dims and dim_index < len(arr_sym.array_dims):
                        max_size: int = arr_sym.array_dims[dim_index]
                        if max_size is not None and index_value >= max_size:
                            raise SemanticError(
                                f"Array index {index_value} is out of bounds for array dimension {dim_index + 1} with size {max_size}",
                                node=subscript_expr
                            )
                    elif arr_sym.array_len and dim_index == 0:
                        # Old 1D array format with array_len
                        if index_value >= arr_sym.array_len:
                            raise SemanticError(
                                f"Array index {index_value} is out of bounds for array dimension 1 with size {arr_sym.array_len}",
                                node=subscript_expr
                            )
            except (KeyError, AttributeError):
                # Symbol not found, skip bounds check (error will be caught elsewhere)
                pass
        
        # For field access (struct field arrays)
        elif is_field_access and field_access_expr:
            try:
                obj_type: ExprType = self.check(field_access_expr.object)
                
                # Get struct info
                if field_access_expr.is_deref:
                    base_type_name: str = obj_type.sem_type.base
                else:
                    base_type_name: str = obj_type.sem_type.base
                
                if self.struct_registry:
                    struct_info = self.struct_registry.lookup(base_type_name.upper())
                    if struct_info:
                        field_info = struct_info.get_field(field_access_expr.field.upper())
                        if field_info and field_info.array_sizes:
                            dim_index: int = depth - 1
                            if dim_index < len(field_info.array_sizes):
                                max_size = field_info.array_sizes[dim_index]
                                if max_size is not None and index_value >= max_size:
                                    raise SemanticError(
                                        f"Array index {index_value} is out of bounds for struct field dimension {dim_index} with size {max_size}",
                                        node=subscript_expr
                                    )
            except (KeyError, AttributeError, SemanticError) as e:
                # Re-raise SemanticError, skip others
                if isinstance(e, SemanticError):
                    raise
                pass


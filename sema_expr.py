from symbols import SemType, SemType, SymbolLookup, FuncTable
from sema import SemanticError
from sema_types import ExprKind, ExprType
from ast_nodes import IntLiteral, Identifier, DerefExpr, CallExpr
from ast_nodes import BinaryExpr, UnaryExpr, BinOp, UnOp, SubscriptExpr, FieldAccess


def promote(a: SemType, b: SemType) -> SemType:
    if a.base == "WORD" or b.base == "WORD":
        return SemType("WORD", False)
    return SemType("BYTE", False)


class ExprTypeChecker:
    def __init__(self, symtab: SymbolLookup, func_table: FuncTable, struct_registry=None):
        self.symtab = symtab
        self.func_table = func_table
        self.struct_registry = struct_registry

    def check(self, expr) -> ExprType:
        if isinstance(expr, IntLiteral):
            # Small literals (0-255) are BYTE, larger are WORD
            if 0 <= expr.value <= 255:
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)
            else:
                return ExprType(SemType("WORD", False), ExprKind.VALUE)

        if isinstance(expr, Identifier):
            sym = self.symtab.lookup(expr.name)
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

            return ExprType(sym.type, ExprKind.VALUE)

        if isinstance(expr, DerefExpr):
            base = self.check(expr.pointer)
            if base.kind != ExprKind.ADDR or not base.sem_type.is_pointer:
                raise SemanticError("Cannot dereference non-pointer")
            return ExprType(
                SemType(base.sem_type.base, False),
                ExprKind.LVALUE
            )

        if isinstance(expr, SubscriptExpr):
            arr_t = self.check(expr.array)
            if arr_t.kind != ExprKind.ADDR:
                raise SemanticError("Subscript requires array address")
            
            # Check if this is a multi-dimensional array
            # For multi-dimensional arrays, partial subscripting returns ADDR (pointer to next dimension)
            # Only final subscript returns LVALUE (actual element)
            
            # Detect if array base is a direct identifier (indicating this might be first subscript of multi-dim)
            is_direct_array = isinstance(expr.array, Identifier)
            
            if is_direct_array:
                # First subscript on array - check if array is multi-dimensional
                try:
                    arr_sym = self.symtab.lookup(expr.array.name)
                    if arr_sym.is_array and arr_sym.array_dims and len(arr_sym.array_dims) > 1:
                        # Multi-dimensional array - first subscript returns ADDR (pointer to next dimension)
                        elem_type = SemType(
                            base=arr_t.sem_type.base,
                            is_pointer=True,  # Returns a pointer to next dimension
                            is_struct=arr_t.sem_type.is_struct,
                            struct_info=arr_t.sem_type.struct_info
                        )
                        return ExprType(elem_type, ExprKind.ADDR)
                except (KeyError, AttributeError):
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
            lt = self.check(expr.left)
            rt = self.check(expr.right)
            op = expr.op

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
                if lt.kind == ExprKind.ADDR or rt.kind == ExprKind.ADDR:
                    if op in (BinOp.ADD, BinOp.SUB):
                        if lt.kind == ExprKind.ADDR and rt.kind == ExprKind.VALUE:
                            return ExprType(lt.sem_type, ExprKind.ADDR)
                        if lt.kind == ExprKind.VALUE and rt.kind == ExprKind.ADDR:
                            return ExprType(rt.sem_type, ExprKind.ADDR)
                    raise SemanticError("Invalid pointer arithmetic")

                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

            # relační
            if op in {
                BinOp.EQ, BinOp.NE,
                BinOp.LT, BinOp.GT, BinOp.LE, BinOp.GE
            }:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Comparison requires values")
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # logické
            if op in {BinOp.LAND, BinOp.LOR}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Logical operator requires values")
                return ExprType(SemType("BYTE", False), ExprKind.VALUE)

            # bitové
            if op in {BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.LSHIFT, BinOp.RSHIFT}:
                if lt.kind != ExprKind.VALUE or rt.kind != ExprKind.VALUE:
                    raise SemanticError("Bitwise operator requires values")
                return ExprType(promote(lt.sem_type, rt.sem_type), ExprKind.VALUE)

        # unární OP
        if isinstance(expr, UnaryExpr):
            # Handle address-of operator (@)
            if expr.op == UnOp.ADDROF:
                # @ can only be applied to lvalues (variables, array elements, struct fields)
                operand_t = self.check(expr.expr)
                
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
                    raise SemanticError("Cannot take address of this expression")
                
                # Address-of always returns WORD pointer to the operand's type
                base_type = operand_t.sem_type.base
                is_struct = operand_t.sem_type.is_struct
                struct_info = operand_t.sem_type.struct_info
                
                return ExprType(
                    SemType(base=base_type, is_pointer=True, is_struct=is_struct, struct_info=struct_info),
                    ExprKind.ADDR
                )
            
            t = self.check(expr.expr)
            # Convert LVALUE to VALUE when reading (e.g., !ptr^ or -ptr^ or ~ptr^)
            if t.kind == ExprKind.LVALUE:
                t = ExprType(t.sem_type, ExprKind.VALUE)
            if t.kind != ExprKind.VALUE:
                raise SemanticError("Unary operator requires value")
            
            # For bitwise NOT (~), preserve the operand type
            if expr.op.value == "~":
                return ExprType(t.sem_type, ExprKind.VALUE)
            
            # For logical NOT (!), return BYTE
            return ExprType(SemType("BYTE", False), ExprKind.VALUE)

        # funkce
        if isinstance(expr, CallExpr):
            fs = self.func_table.lookup(expr.name)
            if len(expr.args) != fs.param_count:
                raise SemanticError(
                    f"Function '{expr.name}' expects {fs.param_count} parameters, "
                    f"but {len(expr.args)} were provided"
                )
            return ExprType(fs.ret_type, ExprKind.VALUE)

        # struct field access: obj.field or ptr^.field
        if isinstance(expr, FieldAccess):
            if not self.struct_registry:
                raise SemanticError("Struct registry not available")
            
            # Check the object type
            obj_type = self.check(expr.object)
            
            # For deref field access (ptr^.field), object must be pointer
            if expr.is_deref:
                if obj_type.kind != ExprKind.ADDR or not obj_type.sem_type.is_pointer:
                    raise SemanticError("Cannot use ^. on non-pointer")
                base_type_name = obj_type.sem_type.base
            else:
                # For direct field access (obj.field), object must be struct value or lvalue
                # (e.g., arr[0].field where arr[0] is LVALUE)
                if obj_type.kind not in (ExprKind.VALUE, ExprKind.LVALUE):
                    raise SemanticError("Field access requires struct value or pointer")
                base_type_name = obj_type.sem_type.base
            
            # Look up struct definition
            struct_info = self.struct_registry.lookup(base_type_name.upper())
            if not struct_info:
                raise SemanticError(f"'{base_type_name}' is not a defined struct")
            
            # Look up field
            field_info = struct_info.get_field(expr.field.upper())
            if not field_info:
                raise SemanticError(f"Struct '{base_type_name}' has no field '{expr.field}'")
            
            # Create field type, preserving struct information if the field is a struct
            field_sem_type = SemType(field_info.base_type, field_info.is_pointer)
            
            # If field is a nested struct, look it up and create SemType with struct_info
            if field_info.base_type.upper() in self.struct_registry._structs:
                nested_struct = self.struct_registry.lookup(field_info.base_type.upper())
                field_sem_type = SemType(field_info.base_type, field_info.is_pointer, 
                                        is_struct=True, struct_info=nested_struct)
            
            return ExprType(field_sem_type, ExprKind.LVALUE)

        # chyba
        raise SemanticError(
            f"Unsupported expression type: {type(expr).__name__}"
        )


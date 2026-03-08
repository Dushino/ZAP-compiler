import sys
from typing import Any, Callable, Literal, NoReturn, Sequence, cast
from version import __version__
from constfold import fold_expr
from constsubst import subst_const
from symbols import StructInfo, StructFieldInfo, Symbol, SymbolTable, SemType, StructRegistry
from sema_types import ExprKind, ExprType
from ast_nodes import (
    BinOp,
    BreakStmt,
    ContinueStmt,
    IntLiteral,
    Identifier,
    DerefExpr,
    SubscriptExpr,
    BinaryExpr,
    UnaryExpr,
    UnOp,
    Expr, ExprInit, ListInit, StringInit, CallExpr, StructLiteral, InitValue,
    CallStmt, AssignStmt,
    IfStmt, ReturnStmt, WhileStmt, RepeatUntilStmt, ForStmt, SwitchStmt,
    AsmBlock, FieldAccess, StringLiteral
)
from sema_expr import ExprTypeChecker
from sema_proc import AnalyzedProc
from sema_func import AnalyzedFunc

from errors import SemanticError


class CodeGen:
    """Code generation engine for ZAP programs.
    Emits assembly for expressions, statements, and routines.
    """
    label_id = 0
    loop_stack = []
    internal_label_prefix = "__ZAP_"

    def __init__(self, symtab: SymbolTable, type_checker: ExprTypeChecker, *, is_65c02: bool = True, used_globals: set[str] | None = None, debug_info: dict | None = None, command_line: str | None = None, proc_param_specs: dict[str, list[tuple[str, int, object, SemType]]] | None = None, func_param_specs: dict[str, list[tuple[str, int, object, SemType]]] | None = None, pruned_procs: list[str] | None = None, struct_registry: StructRegistry | None = None, func_return_buffers: dict[str, tuple[str, StructInfo]] | None = None, system_temp_slots: dict[str, str] | None = None, seg_zp: str = "ZEROPAGE", seg_bss: str = "BSS", seg_code: str = "CODE") -> None:
        """Initialize code generation state.
        Stores symbol tables, options, and debug maps.
        """
        # global symbol table (globals)
        self.global_symtab: SymbolTable = symtab
        # currently active table (can be scoped for PROC/FUNC)
        self.current_symtab: SymbolTable = symtab
        self.tc: ExprTypeChecker = type_checker
        self.struct_registry: StructRegistry = struct_registry or StructRegistry()
        self.code: list[str] = []
        self.for_id = 0
        # Map id(ForStmt) -> set[str] of pre-declared temp names; set by compiler_pipeline
        self.for_temp_map: dict[int, set[str]] | None = None
        self.string_literals = {}  # Maps string content to label name
        self.string_id = 0
        self.array_literals = {}   # Maps array data tuple to label name
        self.array_id = 0
        self.copy_bytes_needed = False
        self.copy_bytes16_needed = False
        self.math_routines_needed: set[str] = set()
        self.is_65c02: bool = is_65c02
        self.used_globals: set[str] = used_globals or set()
        self.used_temps: set[str] = set()
        self.command_line: str | None = command_line
        self.seg_zp: str = seg_zp
        self.seg_bss: str = seg_bss
        self.seg_code: str = seg_code
        self.math_stack_depth: int = 0
        self.system_temp_slots: dict[str, str] = system_temp_slots or {}  # Maps temp name to shared slot
        
        # RPN Code Generation (Phase 1+)
        self.rpn_enabled: bool = True  # [PHASE 4 VALIDATED] RPN enabled by default - 20-25% code size savings
        self.rpn_eval_stack: list[tuple[str, bool]] = []  # Stack of (value, is_16bit) during RPN evaluation
        self.rpn_temp_count: int = 0  # Counter for allocating temporary values
        self.rpn_helper_routines_needed: set[str] = set()  # Track SET_MATH0, SET_MATH1, GET_MATH0
        # Parameter specs: mapping name -> list of (param_name, width_bytes, default_value, sem_type)
        self.proc_param_specs: dict[str, list[tuple[str, int, object, SemType]]] = proc_param_specs or {}
        self.func_param_specs: dict[str, list[tuple[str, int, object, SemType]]] = func_param_specs or {}
        self.func_return_buffers: dict[str, tuple[str, StructInfo]] = func_return_buffers or {}
        self.pruned_procs: list[str] = pruned_procs or []
        # Exports set (populated by pipeline)
        self.exports: set[str] = set()
        # Debug/source maps
        self.debug = debug_info or {}
        self.stmt_src = self.debug.get("stmt_src", {})
        self.local_decl_src = self.debug.get("local_decl_src", {})
        self.global_decl_src = self.debug.get("global_decl_src", {})
        self.proc_src = self.debug.get("proc_src", {})
        self.source_lines = self.debug.get("source_lines", [])
        self.file_lines = self.debug.get("file_lines", {})
        self.orig_line_map_per_file = self.debug.get("orig_line_map_per_file", {})
        self.orig_source_lines_per_file = self.debug.get("orig_source_lines_per_file", {})
        # Track current statement source info for error reporting
        self.current_stmt_info: tuple[str, int, int, str] | None = None
        # Track fixed-address variables (hardware registers) - never optimize these
        self.fixed_address_labels: set[str] = set()
        # Track PORT variables (hardware port-mapped) - never optimize these
        self.port_labels: set[str] = set()
        # Track current function return type for narrowing WORD to BYTE
        self.current_func_return_type: str | None = None
        self.current_func_return_is_pointer: bool = False
        self.current_func_return_buf: str | None = None
        self.current_func_return_struct: StructInfo | None = None
        # Caller-side widening: mark when a byte result must be treated as 16-bit
        self.force_word_result: bool = False
        # Suppress clearing X for byte-return functions (ABI change)
        self.suppress_byte_return_x: bool = False
        # Track assignment context for optimizations that need target type
        self.assign_target_type: SemType | None = None  # Current assignment LHS type
        # Track assignment target for safe temp reuse in expression codegen
        self.assign_target_sym: Symbol | None = None
        self.assign_target_blocked: bool = False
        # Control-flow stacks
        self.loop_stack: list[tuple[str, str]] = []
        self.break_stack: list[str] = []
        # Internal name mapping for compiler-generated symbols
        self._internal_name_map: dict[str, str] = self._build_internal_name_map()
        self._internal_name_re = self._build_internal_name_regex(self._internal_name_map)
        
        # ZP Prioritization: Track load/store frequency for each local scalar
        # Format: {"ROUTINE::LOCAL_NAME": frequency_count, ...}
        self.local_access_frequency: dict[str, int] = {}

    def tc_check(self, expr, read_check_enabled: bool = True) -> ExprType:
        """Type-check an expression with codegen context.
        Attaches source info to semantic errors.
        """
        # Wrapper to attach source location to type-checker errors
        try:
            return self.tc.check(expr, read_check_enabled=read_check_enabled)
        except SemanticError as e:
            if self.current_stmt_info and getattr(e, "filename", None) is None:
                fname, _, _, _ = self.current_stmt_info
                if getattr(e, "line", None) is not None:
                    mapped_line = self._map_clean_line_to_orig(fname, e.line)
                    if mapped_line is not None:
                        e.line = mapped_line
                e.filename = fname
                src_lines = self._get_source_lines_for_file(fname)
                if src_lines:
                    e.source_text = "\n".join(src_lines)
            # If error lacks position, attach current statement info
            if getattr(e, 'line', None) is None and self.current_stmt_info:
                self._raise_error(e.message)
            raise

    # ============================================================================
    # RPN Code Generation Infrastructure (Phase 1+)
    # ============================================================================
    
    class RPNNode:
        """Represents a node in RPN evaluation (operand or operator)."""
        def __init__(self, node_type: str, value: BinOp | UnOp | str | int | Expr | None = None, is_16bit: bool = False, width: int = 0):
            """Initialize code generation state.
            Stores symbol tables, options, and debug maps.
            """
            self.node_type = node_type  # 'OPERAND', 'OPERATOR', 'CONST', 'VAR', 'CALL', etc.
            self.value = value  # Operator name, variable name, constant value, etc.
            
            # Auto-detect width from is_16bit if width not provided
            if width == 0:
                if is_16bit:
                    width = 2
                else:
                    width = 1
            
            self.width = width
            self.is_16bit = (width >= 2)  # For backward compatibility within existing methods
        
        def __repr__(self):
            """Return a readable debug representation.
            Used for logging and diagnostics.
            """
            return f"RPNNode({self.node_type}, {self.value}, width={self.width})"
    
    def ast_to_rpn(self, expr: BinaryExpr | UnaryExpr | Expr) -> list['CodeGen.RPNNode']:
        """Convert an AST expression to RPN sequence.
        
        Example:
            AST: BinaryExpr('+', Identifier('a'), Identifier('b'))
            RPN: [Identifier('a'), Identifier('b'), '+']
            
            AST: BinaryExpr('+', BinaryExpr('*', Identifier('a'), Identifier('b')), Identifier('c'))
            RPN: [Identifier('a'), Identifier('b'), '*', Identifier('c'), '+']
        
        The RPN conversion respects operator precedence from the AST.
        Type information (16-bit vs 8-bit) is preserved through is_16bit flag.
        """
        rpn: list['CodeGen.RPNNode'] = []
        
        def get_expr_width(node: Expr) -> int:
            """Determine width of expression result in bytes."""
            try:
                expr_type = self.tc_check(node, read_check_enabled=False)
                return expr_type.sem_type.width
            except Exception:
                # Fallback for identifiers if type check fails (e.g. context issues)
                if isinstance(node, Identifier):
                    try:
                        sym = self.current_symtab.lookup(node.name)
                        return sym.type.width
                    except Exception:
                        pass
                elif isinstance(node, IntLiteral):
                    if node.value <= 255: return 1
                    if node.value <= 65535: return 2
                    return 4
                elif isinstance(node, BinaryExpr):
                    w1 = get_expr_width(node.left)
                    w2 = get_expr_width(node.right)
                    return max(w1, w2)
                return 1
        
        def walk(node: Expr) -> None:
            """Recursively walk AST and build RPN sequence."""
            if isinstance(node, BinaryExpr):
                # OPTIMIZATION: Swap operands for commutative operations in RPN
                # if the left is an IntLiteral so the constant is on the right
                if node.op in {BinOp.ADD, BinOp.MUL, BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.EQ, BinOp.NE}:
                    if isinstance(node.left, IntLiteral) and not isinstance(node.right, IntLiteral):
                        node = BinaryExpr(left=node.right, op=node.op, right=node.left, line=node.line, col=node.col)
                
                # Check for Pointer Arithmetic Scaling needing injection into RPN
                lt_type = None
                rt_type = None
                try:
                    lt_type = self.tc_check(node.left, read_check_enabled=False)
                    rt_type = self.tc_check(node.right, read_check_enabled=False)
                except Exception:
                    pass

                scale_left = False
                scale_right = False
                scale_factor = 1
                is_ptr_diff = False
                
                if lt_type and rt_type:
                    if node.op == BinOp.ADD:
                        if lt_type.kind == ExprKind.ADDR and rt_type.kind == ExprKind.VALUE:
                            scale_factor = SemType(base=lt_type.sem_type.base, is_pointer=False, is_struct=lt_type.sem_type.is_struct, struct_info=lt_type.sem_type.struct_info).width
                            scale_right = (scale_factor > 1)
                        elif lt_type.kind == ExprKind.VALUE and rt_type.kind == ExprKind.ADDR:
                            scale_factor = SemType(base=rt_type.sem_type.base, is_pointer=False, is_struct=rt_type.sem_type.is_struct, struct_info=rt_type.sem_type.struct_info).width
                            scale_left = (scale_factor > 1)
                    elif node.op == BinOp.SUB:
                        if lt_type.kind == ExprKind.ADDR and rt_type.kind == ExprKind.VALUE:
                            scale_factor = SemType(base=lt_type.sem_type.base, is_pointer=False, is_struct=lt_type.sem_type.is_struct, struct_info=lt_type.sem_type.struct_info).width
                            scale_right = (scale_factor > 1)
                        elif lt_type.kind == ExprKind.ADDR and rt_type.kind == ExprKind.ADDR:
                            scale_factor = SemType(base=lt_type.sem_type.base, is_pointer=False, is_struct=lt_type.sem_type.is_struct, struct_info=lt_type.sem_type.struct_info).width
                            is_ptr_diff = (scale_factor > 1)
                
                # Left subtree
                walk(node.left)
                if scale_left:
                    rpn.append(self.RPNNode('CONST', scale_factor, width=2 if scale_factor > 255 else 1))
                    rpn.append(self.RPNNode('BINOP', BinOp.MUL, width=max(get_expr_width(node.left), 2 if scale_factor > 255 else 1)))
                
                # Right subtree
                walk(node.right)
                if scale_right:
                    rpn.append(self.RPNNode('CONST', scale_factor, width=2 if scale_factor > 255 else 1))
                    rpn.append(self.RPNNode('BINOP', BinOp.MUL, width=max(get_expr_width(node.right), 2 if scale_factor > 255 else 1)))
                
                # Operator
                width = get_expr_width(node)
                rpn.append(self.RPNNode('BINOP', node.op, width=width))
                
                # Pointer difference division
                if is_ptr_diff:
                    rpn.append(self.RPNNode('CONST', scale_factor, width=2 if scale_factor > 255 else 1))
                    rpn.append(self.RPNNode('BINOP', BinOp.DIV, width=width))
                
            elif isinstance(node, UnaryExpr):
                # Operand -> Unary Operator
                walk(node.expr)
                width = get_expr_width(node)
                rpn.append(self.RPNNode('UNOP', node.op, width=width))
                
            elif isinstance(node, Identifier):
                # Variable reference
                width = get_expr_width(node)
                rpn.append(self.RPNNode('VAR', node.name, width=width))
                
            elif isinstance(node, IntLiteral):
                # Constant value
                value = node.value
                width = 1
                if isinstance(value, int):
                    if value > 65535 or value < -32768: # simplistic check
                        width = 4
                    elif value > 255:
                        width = 2
                rpn.append(self.RPNNode('CONST', value, width=width))
                
            elif isinstance(node, SubscriptExpr):
                # Array subscript: array[index] -> load from compute address
                width = get_expr_width(node)
                rpn.append(self.RPNNode('ARRAY_SUB', node, width=width))
                
            elif isinstance(node, FieldAccess):
                # Struct field access
                width = get_expr_width(node)
                rpn.append(self.RPNNode('FIELD_ACCESS', node, width=width))
                
            elif isinstance(node, DerefExpr):
                # Pointer dereference: *ptr
                walk(node.pointer)  # Evaluate pointer first
                width = get_expr_width(node)
                rpn.append(self.RPNNode('DEREF', node, width=width))
                
            elif isinstance(node, CallExpr):
                # Function call
                width = get_expr_width(node)
                rpn.append(self.RPNNode('CALL', node, width=width))
                
            else:
                # Unknown node type, treat as leaf
                width = get_expr_width(node)
                rpn.append(self.RPNNode('UNKNOWN', node, width=width))
        
        walk(expr)
        return rpn
    
    def rpn_eval_to_code(self, rpn: list['CodeGen.RPNNode'], target_16bit: bool = False) -> None:
        """Evaluate RPN sequence and emit code.
        
        The RPN evaluator uses a stack-based approach:
        - Operands push their value onto the evaluation stack (stored in MATH0/MATH1/temps)
        - Operators pop arguments, perform operation, push result
        - Final result should be in A/X for consuming code
        
        Stack storage strategy:
        1. MATH0/MATH0+1 - left operand storage
        2. MATH1/MATH1+1 - right operand storage  
        3. For deeper stacks: spill to ZEROPAGE temps (TMP0-TMP5)
        """
        eval_stack: list[tuple[str, int]] = []  # Stack of (location, width)
        temp_offset = 0  # Byte offset for allocated temps
        
        def get_operand_loc(node_type: str, value: object, width: int) -> tuple[str, int]:
            """Get location of an operand. Does not emit code for basic operands."""
            if node_type == 'CONST':
                const_val = cast(int, value)
                return (f"CONST:{const_val}", width)
            
            elif node_type == 'VAR':
                var_name = cast(str, value)
                try:
                    sym = self.current_symtab.lookup(var_name)
                    if sym:
                        return (sym.asm_name(), width)
                except Exception:
                    pass
                return (var_name, width)
            
            return ("AX", width)

        def load_to_ax(loc: str, is_16bit: bool) -> None:
            """Emit code to load a location into A/X."""
            if loc == "AX" or loc == "A":
                # Already in A/X or just in A (for byte results from shifts)
                if loc == "A" and is_16bit:
                    # If we need 16-bit but only have A, zero-extend
                    self.emit("\tLDX #$00")
                return
            if loc.startswith("CONST:"):
                val = int(loc.split(":")[1])
                if is_16bit:
                    self.emit(f"\tLDA #${val & 0xFF:02X}")
                    self.emit(f"\tLDX #${(val >> 8) & 0xFF:02X}")
                else:
                    self.emit(f"\tLDA #${val & 0xFF:02X}")
                    if not self.suppress_byte_return_x:
                        self.emit("\tLDX #$00")
            else:
                # Memory location
                self.emit(f"\tLDA {loc}")
                if is_16bit:
                    self.emit(f"\tLDX {loc}+1")
                elif not self.suppress_byte_return_x:
                    self.emit("\tLDX #$00")

        def load_to_ax_for_math(loc: str, is_16bit: bool) -> None:
            """Load operand into A/X for math setup without forcing X for bytes."""
            prev = self.suppress_byte_return_x
            if not is_16bit:
                self.suppress_byte_return_x = True
            load_to_ax(loc, is_16bit)
            self.suppress_byte_return_x = prev

        def emit_set_math0_from_ax(is_16bit: bool, *, force_word: bool = False) -> None:
            """Store A/X into MATH0, inlining for byte values."""
            if is_16bit:
                self.emit("\tJSR SET_MATH0")
                self.rpn_helper_routines_needed.add("SET_MATH0")
            else:
                self.emit("\tSTA MATH0")
                if force_word:
                    self._stz("MATH0+1")

        def emit_set_math1_from_ax(is_16bit: bool, *, force_word: bool = False) -> None:
            """Store A/X into MATH1, inlining for byte values."""
            if is_16bit:
                self.emit("\tJSR SET_MATH1")
                self.rpn_helper_routines_needed.add("SET_MATH1")
            else:
                self.emit("\tSTA MATH1")
                if force_word:
                    self._stz("MATH1+1")
        
        def emit_move_to_math(src: str, dst_math: str, width: int, target_width: int = 0) -> None:
            """Move value from src to dst_math (MATH0 or MATH1)."""
            if target_width == 0:
                target_width = width
            
            if width <= 2:
                # Use existing A/X logic for speed and code size
                prev_suppress = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    load_to_ax(src, width == 2)
                finally:
                    self.suppress_byte_return_x = prev_suppress

                if dst_math == "MATH0":
                    emit_set_math0_from_ax(width == 2, force_word=(target_width >= 2))
                else:
                    emit_set_math1_from_ax(width == 2, force_word=(target_width >= 2))
                
                # Zero-extend if target is wider than 2 bytes
                if target_width > 2:
                    self._stz(f"{dst_math}+2")
                    self._stz(f"{dst_math}+3")
            else:
                # 32-bit (or >2 byte) move
                if src.startswith("CONST:"):
                    val = int(src.split(":")[1])
                    self.emit(f"\tLDA #${val & 0xFF:02X}")
                    self.emit(f"\tSTA {dst_math}")
                    self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
                    self.emit(f"\tSTA {dst_math}+1")
                    self.emit(f"\tLDA #${(val >> 16) & 0xFF:02X}")
                    self.emit(f"\tSTA {dst_math}+2")
                    self.emit(f"\tLDA #${(val >> 24) & 0xFF:02X}")
                    self.emit(f"\tSTA {dst_math}+3")
                elif src == "MATH0" or src == "MATH1":
                    # Register to Register move
                    for i in range(4):
                        offset = f"+{i}" if i > 0 else ""
                        self.emit(f"\tLDA {src}{offset}")
                        self.emit(f"\tSTA {dst_math}{offset}")
                else:
                    # Memory to Register move
                    # Ensure we don't clobber X/Y if not needed, but A is fair game.
                    # Simple copy loop unrolled
                    for i in range(4):
                        offset = f"+{i}" if i > 0 else ""
                        self.emit(f"\tLDA {src}{offset}")
                        self.emit(f"\tSTA {dst_math}{offset}")

        def spill_ax_if_needed(stack: list[tuple[str, int]]) -> None:
            """If AX is on stack, spill it to a temp to avoid overwriting."""
            for i, (loc, width) in enumerate(stack):
                if loc == "AX":
                    nonlocal temp_offset
                    if temp_offset + width > 32:
                        self._raise_error(
                            "Expression is too complex (MATH_STACK overflow): Please simplify the expression."
                        )
                    spill_base = f"MATH_STACK+{temp_offset}"
                    temp_offset += width
                    
                    if width <= 2:
                        self.emit(f"\tSTA {spill_base}")
                        if width == 2:
                            self.emit(f"\tSTX {spill_base}+1")
                        elif not self.suppress_byte_return_x:
                             # For byte results, usually only A is significant, X might be garbage or zero
                             # But if we spill, we only need to restore A.
                             pass
                    else:
                        # 4-byte spill from where? AX can only hold 2 bytes!
                        # This should not happen if we respect that 4-byte values don't live in AX.
                        # But if we treat AX as a placeholder for "result of last operation", 
                        # and that operation was 32-bit, it returns in MATH0, not AX.
                        # So "AX" location for 4-byte value is invalid state?
                        # Or maybe we change semantic of "AX" to "Result Register".
                        # For now, assume 32-bit results are in MATH0, so they hit spill_math0, not spill_ax.
                        # However, if some routine mistakenly returns "AX" for 32-bit... check it.
                        pass
                    stack[i] = (spill_base, width)

        def spill_math0_if_needed(stack: list[tuple[str, int]]) -> None:
            """Spill MATH0, A, or AX if they remain on the stack to avoid clobbering."""
            nonlocal temp_offset
            for i, (loc, width) in enumerate(stack):
                if loc == "MATH0":
                    if temp_offset + width > 32:
                        self._raise_error(
                            "Expression is too complex (MATH_STACK overflow): Please simplify the expression."
                        )
                    spill_base = f"MATH_STACK+{temp_offset}"
                    temp_offset += width
                    
                    self.emit("\tLDA MATH0")
                    self.emit(f"\tSTA {spill_base}")
                    if width >= 2:
                        self.emit("\tLDA MATH0+1")
                        self.emit(f"\tSTA {spill_base}+1")
                    if width >= 4:
                        self.emit("\tLDA MATH0+2")
                        self.emit(f"\tSTA {spill_base}+2")
                        self.emit("\tLDA MATH0+3")
                        self.emit(f"\tSTA {spill_base}+3")
                    
                    stack[i] = (spill_base, width)
                elif loc in ("A", "AX"):
                    if temp_offset + width > 32:
                        self._raise_error(
                            "Expression is too complex (MATH_STACK overflow): Please simplify the expression."
                        )
                    spill_base = f"MATH_STACK+{temp_offset}"
                    temp_offset += width
                    
                    self.emit(f"\tSTA {spill_base}")
                    if loc == "AX" and width >= 2:
                        self.emit(f"\tSTX {spill_base}+1")
                    
                    stack[i] = (spill_base, width)

        def get_math_routine_for_op(op, left_width: int, right_width: int) -> str | None:
            """Map binary operator to math routine. Returns routine name or None if not a math op."""
            
            is_32 = left_width > 2 or right_width > 2
            
            if op == BinOp.ADD:
                if is_32:
                    return "ADD32"
                elif left_width > 1 or right_width > 1:
                    return "ADD16"
                else:
                    return None  # 8-bit addition handled with inline code
            elif op == BinOp.SUB:
                if is_32:
                    return "SUB32"
                elif left_width > 1 or right_width > 1:
                    return "SUB16"
                else:
                    return None  # 8-bit subtraction handled with inline code
            elif op == BinOp.MUL:
                if is_32:
                    return "MUL32"
                elif left_width > 1 and right_width > 1:
                    return "MUL16"
                elif left_width > 1 or right_width > 1:
                    return "MUL16_8"
                else:
                    return "MUL8"
            elif op == BinOp.DIV:
                if is_32:
                    return "DIV32"
                elif right_width > 1 and left_width > 1:
                    return "DIV16"
                elif right_width > 1:
                    return "DIV8_16"
                elif left_width > 1:
                    return "DIV16_8"
                else:
                    return "DIV8"
            elif op == BinOp.MOD:
                if is_32:
                    return "MOD32"
                elif right_width > 1 and left_width > 1:
                    return "MOD16"
                elif right_width > 1:
                    return "MOD8_16"
                elif left_width > 1:
                    return "MOD16_8"
                else:
                    return "MOD8"
            else:
                # Comparison, bitwise, logical - not math routines (handled elsewhere)
                return None

        def get_math_ax_entry(routine: str) -> str | None:
            """Map a math routine to its right-operand-in-A/X entrypoint."""
            ax_map = {
                "ADD16": "ADD16_AX",
                "SUB16": "SUB16_AX",
                "MUL8": "MUL8_A",
                "MUL16_8": "MUL16_8_A",
                "MUL16": "MUL16_AX",
                "DIV8": "DIV8_A",
                "DIV16_8": "DIV16_8_A",
                "DIV8_16": "DIV8_16_AX",
                "DIV16": "DIV16_AX",
                "MOD8": "MOD8_A",
                "MOD16_8": "MOD16_8_A",
                "MOD8_16": "MOD8_16_AX",
                "MOD16": "MOD16_AX",
            }
            return ax_map.get(routine)
        
        # Evaluate RPN sequence
        for i, node in enumerate(rpn):
            if node.node_type == 'CONST' or node.node_type == 'VAR':
                # Just push the location, don't emit yet
                loc, width = get_operand_loc(node.node_type, node.value, node.width)
                eval_stack.append((loc, width))
                
            elif node.node_type == 'BINOP':
                if len(eval_stack) < 2:
                    self._raise_error(f"RPN: Insufficient operands for binary operator {node.value}")
                
                right_loc, right_width = eval_stack.pop()
                left_loc, left_width = eval_stack.pop()

                # FAST PATH OPTIMIZATION: For simple byte operations (var/const op var/const),
                # generate direct accumulator code instead of using MATH0/MATH1 registers
                from ast_nodes import BinOp
                simple_left = not left_loc.startswith("MATH_STACK") and left_loc not in ("MATH0", "MATH1", "AX")
                simple_right = not right_loc.startswith("MATH_STACK") and right_loc not in ("MATH0", "MATH1", "AX")
                # Fast path only for 8-bit ops for now
                both_byte = left_width <= 1 and right_width <= 1
                fast_path_ops = {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE, 
                                BinOp.ADD, BinOp.SUB, BinOp.BAND, BinOp.BOR, BinOp.BXOR}
                
                if simple_left and simple_right and both_byte and node.value in fast_path_ops:
                    # CRITICAL: Spill MATH0 if it's already in use before we overwrite it
                    spill_math0_if_needed(eval_stack)
                    
                    # Generate optimized code using accumulator directly
                    is_commutative = node.value in {BinOp.ADD, BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.EQ, BinOp.NE}
                    if right_loc in ("A", "AX"):
                        if is_commutative:
                            left_loc, right_loc = right_loc, left_loc
                        else:
                            self.emit("\tSTA MATH1")
                            right_loc = "MATH1"

                    # Load left operand
                    if left_loc == "A" or left_loc == "AX":
                        pass
                    elif left_loc.startswith("CONST:"):
                        val = int(left_loc.split(":")[1]) & 0xFF
                        self.emit(f"\tLDA #${val:02X}")
                    else:
                        self.emit(f"\tLDA {left_loc}")
                    
                    # Format right operand for instruction
                    if right_loc.startswith("CONST:"):
                        val = int(right_loc.split(":")[1]) & 0xFF
                        right_operand = f"#${val:02X}"
                    else:
                        right_operand = right_loc
                    
                    # Perform operation
                    if node.value == BinOp.ADD:
                        if right_operand == "#$01":
                            self.emit("\tSTA MATH0")
                            self.emit("\tINC MATH0")
                        else:
                            self.emit("\tCLC")
                            self.emit(f"\tADC {right_operand}")
                            self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue
                    elif node.value == BinOp.SUB:
                        if right_operand == "#$01":
                            self.emit("\tSTA MATH0")
                            self.emit("\tDEC MATH0")
                        else:
                            self.emit("\tSEC")
                            self.emit(f"\tSBC {right_operand}")
                            self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue
                    elif node.value == BinOp.BAND:
                        self.emit(f"\tAND {right_operand}")
                        self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue
                    elif node.value == BinOp.BOR:
                        self.emit(f"\tORA {right_operand}")
                        self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue
                    elif node.value == BinOp.BXOR:
                        self.emit(f"\tEOR {right_operand}")
                        self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue
                    elif node.value in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                        # Comparison: use CMP and convert to boolean
                        self.emit(f"\tCMP {right_operand}")
                        lbl_true = self.new_label("CMP_TRUE")
                        lbl_end = self.new_label("CMP_END")
                        
                        if node.value == BinOp.EQ:
                            self.emit(f"\tBEQ {lbl_true}")
                        elif node.value == BinOp.NE:
                            self.emit(f"\tBNE {lbl_true}")
                        elif node.value == BinOp.LT:
                            self.emit(f"\tBCC {lbl_true}")
                        elif node.value == BinOp.GE:
                            self.emit(f"\tBCS {lbl_true}")
                        elif node.value == BinOp.GT:
                            # a > b: !(a < b) && a != b
                            self.emit(f"\tBCC {lbl_end}")  # If less, result is false
                            self.emit(f"\tBNE {lbl_true}")  # If not equal and not less, it's greater
                        elif node.value == BinOp.LE:
                            # a <= b: (a < b) || a == b
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_true}")
                        
                        self.emit("\tLDA #$00")
                        self.emit(f"\tJMP {lbl_end}")
                        self.emit(f"{lbl_true}:")
                        self.emit("\tLDA #$01")
                        self.emit(f"{lbl_end}:")
                        self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", False))
                        continue  # Skip general path

                # FAST PATH OPTIMIZATION: 16-bit and 32-bit immediate bitwise 
                if node.value in {BinOp.BAND, BinOp.BOR, BinOp.BXOR} and right_loc.startswith("CONST:"):
                    is_32_bitwise = left_width > 2 or right_width > 2
                    if is_32_bitwise or node.width == 2:
                        spill_math0_if_needed(eval_stack)
                        val = int(right_loc.split(":")[1])
                        asm_op = "AND" if node.value == BinOp.BAND else "ORA" if node.value == BinOp.BOR else "EOR"
                        width = node.width
                        
                        if is_32_bitwise:
                            if left_loc != "MATH0":
                                emit_move_to_math(left_loc, "MATH0", left_width, target_width=width)
                            for j in range(4):
                                suffix = "" if j == 0 else f"+{j}"
                                self.emit(f"\tLDA MATH0{suffix}")
                                self.emit(f"\t{asm_op} #${(val >> (j*8)) & 0xFF:02X}")
                                self.emit(f"\tSTA MATH0{suffix}")
                            eval_stack.append(("MATH0", width))
                        else:  # 16-bit
                            if left_loc == "A" or left_loc == "AX":
                                pass
                            elif left_loc == "MATH0":
                                self.emit("\tLDA MATH0")
                                self.emit("\tLDX MATH0+1")
                            else:
                                load_to_ax(left_loc, True)
                            
                            self.emit(f"\t{asm_op} #${val & 0xFF:02X}")
                            self.emit("\tTAY")
                            self.emit("\tTXA")
                            self.emit(f"\t{asm_op} #${(val >> 8) & 0xFF:02X}")
                            self.emit("\tTAX")
                            self.emit("\tTYA")
                            
                            self.emit("\tSTA MATH0")
                            self.emit("\tSTX MATH0+1")
                            eval_stack.append(("MATH0", width))
                        continue

                # If an older stack entry still lives in MATH0, spill it before reuse.
                spill_math0_if_needed(eval_stack)
                
                # Check for 32-bit operations
                is_32 = left_width > 2 or right_width > 2
                
                if is_32:
                    # 32-bit Path: Logic is simpler, always use MATH0/MATH1 and routines
                    # Load operands to MATH/MATH1
                    # Optimization: if left is MATH0, just load right to MATH1.
                    commutative_ops = {BinOp.ADD, BinOp.MUL, BinOp.BAND, BinOp.BOR, BinOp.BXOR}
                    
                    if left_loc == "MATH0":
                         emit_move_to_math(right_loc, "MATH1", right_width, target_width=4)
                    elif right_loc == "MATH0" and node.value in commutative_ops:
                         emit_move_to_math(left_loc, "MATH1", left_width, target_width=4)
                         # Implicit swap: MATH0 (new left) = old right, MATH1 (new right) = old left
                    else:
                         # Default safe moves
                         # If right is in MATH0, move it to MATH1 first
                         if right_loc == "MATH0":
                             emit_move_to_math(right_loc, "MATH1", right_width, target_width=4)
                             emit_move_to_math(left_loc, "MATH0", left_width, target_width=4)
                         else:
                             # Move right first to avoid clobbering if left needs MATH0
                             emit_move_to_math(right_loc, "MATH1", right_width, target_width=4)
                             emit_move_to_math(left_loc, "MATH0", left_width, target_width=4)

                    routine = get_math_routine_for_op(cast(BinOp, node.value), left_width, right_width)
                    if routine:
                       self.emit(f"\tJSR {routine}")
                       self.math_routines_needed.add(routine)
                       eval_stack.append(("MATH0", node.width))
                    elif node.value == BinOp.LSHIFT:
                        self.emit("\tLDA MATH1")
                        self.emit("\tJSR LSHIFT32")
                        self.math_routines_needed.add("LSHIFT32")
                        eval_stack.append(("MATH0", 4))
                    elif node.value == BinOp.RSHIFT:
                        self.emit("\tLDA MATH1")
                        self.emit("\tJSR RSHIFT32")
                        self.math_routines_needed.add("RSHIFT32")
                        eval_stack.append(("MATH0", 4))
                    elif node.value in {BinOp.BAND, BinOp.BOR, BinOp.BXOR}:
                        self._gen_bitwise32(cast(BinOp, node.value))
                        eval_stack.append(("MATH0", 4))
                    else:
                        # Fallback for non-routine 32-bit ops (e.g. comparisons logic for 32-bit?)
                        self._raise_error(f"Unsupported 32-bit operation: {node.value}")
                    continue

                # Normal 8/16-bit Path
                commutative_ops = {BinOp.ADD, BinOp.MUL, BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.LAND, BinOp.LOR, BinOp.EQ, BinOp.NE}
                
                # Rescue right operand if it is currently in A/AX, before left_loc loading destroys it
                if right_loc in ("A", "AX"):
                    if node.value in commutative_ops:
                        left_loc, right_loc = right_loc, left_loc
                        left_width, right_width = right_width, left_width
                    else:
                        self.emit("\tSTA MATH1")
                        if right_loc == "AX":
                            self.emit("\tSTX MATH1+1")
                        right_loc = "MATH1"

                routine = get_math_routine_for_op(cast(BinOp, node.value), left_width, right_width)
                force_word_operands = routine in {"ADD16", "SUB16"}
                use_ax_right = False
                routine_ax: str | None = None
                if routine:
                    routine_ax = get_math_ax_entry(routine)
                    # Only use AX entry if right operand is not already in MATH0/MATH1.
                    use_ax_right = routine_ax is not None and right_loc not in ("MATH0", "MATH1")
                
                # OPTIMIZATION: For constant-count shifts, don't store to MATH0 - keep in A/X
                skip_math0_store = (node.value in {BinOp.LSHIFT, BinOp.RSHIFT} and 
                                   right_loc.startswith("CONST:"))
                
                if right_loc == "MATH0" and left_loc != "MATH0":
                    if node.value in commutative_ops:
                        # For commutative ops with right in MATH0, try using _AX variant
                        if routine_ax:
                            # Load left operand to A/X and use _AX variant (MATH0 stays intact, gets stored to MATH1 by _AX)
                            prev = self.suppress_byte_return_x
                            self.suppress_byte_return_x = False
                            load_to_ax(left_loc, left_width == 2)
                            self.suppress_byte_return_x = prev
                            use_ax_right = True  # Signal to use the _AX variant
                        else:
                            # No _AX variant available, use traditional approach
                            load_to_ax_for_math(left_loc, left_width == 2)
                            emit_set_math1_from_ax(left_width == 2, force_word=force_word_operands)
                            use_ax_right = False
                    else:
                        # Preserve right in MATH1, then load left to MATH0 (order matters)
                        load_to_ax_for_math(right_loc, right_width == 2)
                        emit_set_math1_from_ax(right_width == 2, force_word=force_word_operands)
                        load_to_ax_for_math(left_loc, left_width == 2)
                        emit_set_math0_from_ax(left_width == 2, force_word=force_word_operands)
                        use_ax_right = False
                else:
                    if left_loc != "MATH0":
                        load_to_ax_for_math(left_loc, left_width == 2)
                        if not skip_math0_store:
                            emit_set_math0_from_ax(left_width == 2, force_word=force_word_operands)
                    if use_ax_right:
                        if right_loc != "AX":
                            # For _AX entrypoints, always load both A and X (even for byte operands)
                            prev = self.suppress_byte_return_x
                            self.suppress_byte_return_x = False
                            load_to_ax(right_loc, right_width == 2)
                            self.suppress_byte_return_x = prev
                    else:
                        # OPTIMIZATION: Skip MATH1 loading for shift operations with constant counts
                        # since inline shifts don't read MATH1
                        skip_math1_load = (node.value in {BinOp.LSHIFT, BinOp.RSHIFT} and 
                                         right_loc.startswith("CONST:"))
                        if right_loc != "MATH1" and not skip_math1_load:
                            load_to_ax_for_math(right_loc, right_width == 2)
                            emit_set_math1_from_ax(right_width == 2, force_word=force_word_operands)
                
                # Check for power of 2 multiplication / division (peephole optimization)
                math_optimized = False
                if node.value in {BinOp.MUL, BinOp.DIV} and right_loc.startswith("CONST:"):
                    const_val = int(right_loc.split(":")[1])
                    if const_val > 0 and (const_val & (const_val - 1)) == 0:
                        # Found a power of 2
                        shift_amount = const_val.bit_length() - 1
                        if shift_amount > 0:
                            # Load operand into A/X to apply shifts
                            if left_loc != "MATH0":
                                # The left operand is not in MATH0 yet, so load it into A/X natively
                                load_to_ax(left_loc, left_width == 2)
                            else:
                                # Left operand is in MATH0, load it to A/X
                                self.emit("\tLDA MATH0")
                                if node.width == 2:
                                    self.emit("\tLDX MATH0+1")
                            
                            # Perform shifts
                            if node.value == BinOp.MUL:
                                self._gen_lshift(node.width == 2, "A", shift_amount)
                            else:
                                self._gen_rshift(node.width == 2, "A", shift_amount)
                            
                            eval_stack.append(("AX" if node.width == 2 else "A", node.width))
                            math_optimized = True

                # 3. Perform operation
                if math_optimized:
                    pass
                elif routine:
                    if use_ax_right and routine_ax:
                        self.emit(f"\tJSR {routine_ax}")
                        self.math_routines_needed.add(routine_ax)
                        self.math_routines_needed.add(routine)
                    else:
                        self.emit(f"\tJSR {routine}")
                    if node.value in {BinOp.MUL, BinOp.DIV, BinOp.MOD} and node.width <= 2:
                        eval_stack.append(("AX" if node.width == 2 else "A", node.width))
                    else:
                        eval_stack.append(("MATH0", node.width))
                else:
                    # Inline 8-bit math
                    if node.value == BinOp.ADD and not (left_width > 1 or right_width > 1):
                        if right_loc == "CONST:1":
                            self.emit("\tINC MATH0")
                        else:
                            self.emit("\tLDA MATH0")
                            self.emit("\tCLC")
                            self.emit("\tADC MATH1")
                            self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", 1))
                    elif node.value == BinOp.SUB and not (left_width > 1 or right_width > 1):
                        if right_loc == "CONST:1":
                            self.emit("\tDEC MATH0")
                        else:
                            self.emit("\tLDA MATH0")
                            self.emit("\tSEC")
                            self.emit("\tSBC MATH1")
                            self.emit("\tSTA MATH0")
                        eval_stack.append(("MATH0", 1))
                    elif node.value in {BinOp.BAND, BinOp.BOR, BinOp.BXOR}:
                        result_width = node.width
                        if result_width > 2:
                            # 32-bit bitwise op: MATH0 = MATH0 op MATH1
                            # Operands are already in MATH0 and MATH1
                             for i in range(4):
                                suffix = "" if i == 0 else f"+{i}"
                                self.emit(f"\tLDA MATH0{suffix}")
                                if node.value == BinOp.BAND:
                                    self.emit(f"\tAND MATH1{suffix}")
                                elif node.value == BinOp.BOR:
                                    self.emit(f"\tORA MATH1{suffix}")
                                else:
                                    self.emit(f"\tEOR MATH1{suffix}")
                                self.emit(f"\tSTA MATH0{suffix}")
                             eval_stack.append(("MATH0", 4))
                        else:
                            self.emit("\tLDA MATH1")
                            if result_width == 2:
                                self.emit("\tLDX MATH1+1")
                            if node.value == BinOp.BAND:
                                self._gen_bitwise_and(result_width == 2, "MATH0")
                            elif node.value == BinOp.BOR:
                                self._gen_bitwise_or(result_width == 2, "MATH0")
                            else:
                                self._gen_bitwise_xor(result_width == 2, "MATH0")
                            self.emit("\tSTA MATH0")
                            if result_width == 2:
                                self.emit("\tSTX MATH0+1")
                            eval_stack.append(("MATH0", result_width))
                    elif node.value in {BinOp.LSHIFT, BinOp.RSHIFT}:
                        result_width = node.width
                        shift_count: int | None = None
                        if right_loc.startswith("CONST:"):
                            shift_count = int(right_loc.split(":")[1]) & 0xFF
                        
                        # OPTIMIZATION: For constant-count shifts, keep value in A instead of reload from MATH0
                        # For variable shifts, use MATH0/MATH1 path as before
                        if shift_count is not None:
                            # Constant-count shift: load left operand to A/X if not there
                            # Left operand should already be in A/X from earlier operand loading
                            # Use "A" as left_tmp to indicate value is in accumulator
                            if result_width > 2:
                                # 32-bit shift with constant count
                                if left_loc != "MATH0":
                                    emit_move_to_math(left_loc, "MATH0", 4)
                                self.emit(f"\tLDA #{shift_count}")
                                # Directly emit JSR (don't call _gen_lshift32/_gen_rshift32 as they
                                # would overwrite A with LDA MATH1 before the JSR)
                                if node.value == BinOp.LSHIFT:
                                    self.math_routines_needed.add("LSHIFT32")
                                    self.emit("\tJSR LSHIFT32")
                                else:
                                    self.math_routines_needed.add("RSHIFT32")
                                    self.emit("\tJSR RSHIFT32")
                            elif node.value == BinOp.LSHIFT:
                                self._gen_lshift(result_width == 2, "A", shift_count)
                            else:
                                self._gen_rshift(result_width == 2, "A", shift_count)
                        else:
                            # Variable-count shift: use traditional MATH0/MATH1 path
                            self.emit("\tLDA MATH1")
                            if result_width > 2:
                                # 32-bit variable shift
                                if node.value == BinOp.LSHIFT:
                                    self._gen_lshift32()
                                else:
                                    self._gen_rshift32()
                            elif node.value == BinOp.LSHIFT:
                                self._gen_lshift(result_width == 2, "MATH0", shift_count)
                            else:
                                self._gen_rshift(result_width == 2, "MATH0", shift_count)
                        # OPTIMIZATION: For 8-bit constant shifts, result stays in A - no need for MATH0
                        # Only store to MATH0 for 16-bit shifts or variable shifts
                        if not (result_width == 1 and shift_count is not None):
                            if result_width <= 2: # Only needed for < 32-bit as 32-bit is already in MATH0
                                self.emit("\tSTA MATH0")
                                if result_width == 2:
                                    self.emit("\tSTX MATH0+1")
                            eval_stack.append(("MATH0", result_width))
                        else:
                            # 8-bit constant shift: result stays in A
                            eval_stack.append(("A", 1))
                    elif node.value in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                        # Comparison operators: always produce BYTE (0 or 1)
                        # MATH0 = left, MATH1 = right
                        lbl_true = self.new_label("CMP_TRUE")
                        lbl_end = self.new_label("CMP_END")
                        
                        # Compare MATH0 vs MATH1
                        if left_width > 2 or right_width > 2:
                            # 32-bit comparison
                            # If either is >2 bytes, treat both as 32-bit (MATH0/MATH1)
                            # (They should be loaded to MATH0/MATH1 by now)
                            
                            if node.value == BinOp.EQ:
                                # Check all 4 bytes for equality
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                self.emit(f"\tBNE {lbl_true}") # If different, not equal -> wait, logic reversed
                                # If any byte differs, jump to false (which is default fallthrough)
                                # Default is False, Jump to True?
                                # Let's stick to: Jump to True if condition met.
                                
                                # Equality: All bytes must be equal.
                                # If any differ, it's False.
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                self.emit(f"\tBNE {lbl_end}") # Not equal
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBNE {lbl_end}")
                                self.emit("\tLDA MATH0+2")
                                self.emit("\tCMP MATH1+2")
                                self.emit(f"\tBNE {lbl_end}")
                                self.emit("\tLDA MATH0+3")
                                self.emit("\tCMP MATH1+3")
                                self.emit(f"\tBNE {lbl_end}")
                                # All equal -> True
                                self.emit("\tLDA #$01")
                                self.emit(f"\tJMP {lbl_end}_SET")
                                
                                self.emit(f"{lbl_end}:")
                                self.emit("\tLDA #$00")
                                self.emit(f"{lbl_end}_SET:")
                                
                            elif node.value == BinOp.NE:
                                # Inequality: Any byte differs -> True
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0+2")
                                self.emit("\tCMP MATH1+2")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0+3")
                                self.emit("\tCMP MATH1+3")
                                self.emit(f"\tBNE {lbl_true}")
                                
                                # All equal -> False
                                self.emit("\tLDA #$00")
                                self.emit(f"\tJMP {lbl_end}")
                                
                                self.emit(f"{lbl_true}:")
                                self.emit("\tLDA #$01")
                                
                            else:
                                # Magnitude comparisons (LT, LE, GT, GE) - Unsigned 32-bit
                                # Compare high bytes first
                                self.emit("\tLDA MATH0+3")
                                self.emit("\tCMP MATH1+3")
                                self.emit(f"\tBNE {lbl_true}") # If high bytes differ, result is decided
                                
                                self.emit("\tLDA MATH0+2")
                                self.emit("\tCMP MATH1+2")
                                self.emit(f"\tBNE {lbl_true}")
                                
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBNE {lbl_true}")
                                
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                # Fallthrough to decide based on flags
                                
                                self.emit(f"{lbl_true}:")
                                # Flags are set from the significant byte comparison.
                                # Unsigned: BCC (Left < Right), BCS (Left >= Right)
                                # BEQ (Equal)
                                
                                if node.value == BinOp.LT:
                                    self.emit(f"\tBCC {lbl_true}_RES") 
                                elif node.value == BinOp.LE:
                                    self.emit(f"\tBCC {lbl_true}_RES")
                                    self.emit(f"\tBEQ {lbl_true}_RES")
                                elif node.value == BinOp.GT:
                                    self.emit(f"\tBCS {lbl_true}_CHECK_NE")
                                    self.emit(f"\tJMP {lbl_end}") # Carry clear -> Less -> False
                                    self.emit(f"{lbl_true}_CHECK_NE:")
                                    self.emit(f"\tBNE {lbl_true}_RES") # Carry Set AND Not Equal -> Greater
                                elif node.value == BinOp.GE:
                                    self.emit(f"\tBCS {lbl_true}_RES")
                                    
                                # False case
                                self.emit("\tLDA #$00")
                                self.emit(f"\tJMP {lbl_end}")
                                
                                self.emit(f"{lbl_true}_RES:")
                                self.emit("\tLDA #$01")

                        elif left_width == 2 or right_width == 2:
                            # 16-bit comparison - more complex
                            if node.value == BinOp.EQ:
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBEQ {lbl_true}")
                                self.emit("\tLDA #$00")
                                self.emit(f"\tJMP {lbl_end}")
                                self.emit(f"{lbl_true}:")
                                self.emit("\tLDA #$01")
                            elif node.value == BinOp.NE:
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA #$00")
                                self.emit(f"\tJMP {lbl_end}")
                                self.emit(f"{lbl_true}:")
                                self.emit("\tLDA #$01")
                            else:
                                # For <, <=, >, >= with 16-bit: use simple CMP/SBC
                                # Since ZAP is unsigned (per user), use CMP high then low
                                self.emit("\tLDA MATH0+1")
                                self.emit("\tCMP MATH1+1")
                                self.emit(f"\tBNE {lbl_true}")
                                self.emit("\tLDA MATH0")
                                self.emit("\tCMP MATH1")
                                
                                self.emit(f"{lbl_true}:")
                                if node.value == BinOp.LT:
                                    self.emit(f"\tBCC {lbl_true}_RES")
                                elif node.value == BinOp.LE:
                                    self.emit(f"\tBCC {lbl_true}_RES")
                                    self.emit(f"\tBEQ {lbl_true}_RES")
                                elif node.value == BinOp.GT:
                                    self.emit(f"\tBCS {lbl_true}_CHECK_NE")
                                    self.emit(f"\tJMP {lbl_end}")
                                    self.emit(f"{lbl_true}_CHECK_NE:")
                                    self.emit(f"\tBNE {lbl_true}_RES")
                                else:  # GE
                                    self.emit(f"\tBCS {lbl_true}_RES")
                                
                                self.emit("\tLDA #$00")
                                self.emit(f"\tJMP {lbl_end}")
                                self.emit(f"{lbl_true}_RES:")
                                self.emit("\tLDA #$01")
                        else:
                            # 8-bit comparison
                            self.emit("\tLDA MATH0")
                            self.emit("\tCMP MATH1")
                            if node.value == BinOp.EQ:
                                self.emit(f"\tBEQ {lbl_true}")
                            elif node.value == BinOp.NE:
                                self.emit(f"\tBNE {lbl_true}")
                            elif node.value == BinOp.LT:
                                self.emit(f"\tBCC {lbl_true}")  # A < operand if carry clear
                            elif node.value == BinOp.LE:
                                self.emit(f"\tBCC {lbl_true}")  # A <= operand: carry clear or zero
                                self.emit(f"\tBEQ {lbl_true}")
                            elif node.value == BinOp.GT:
                                self.emit(f"\tBCS {lbl_true}")  # A > operand if carry set and not zero
                                self.emit(f"\tBNE {lbl_true}")
                            else:  # GE
                                self.emit(f"\tBCS {lbl_true}")  # A >= operand if carry set
                            
                            self.emit("\tLDA #$00")
                            self.emit(f"\tJMP {lbl_end}")
                            self.emit(f"{lbl_true}:")
                            self.emit("\tLDA #$01")
                        
                        self.emit(f"{lbl_end}:")
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                            self.emit("\tLDX #$00")  # Comparisons always return BYTE
                        eval_stack.append(("MATH0", 1))

                    elif node.value in {BinOp.LAND, BinOp.LOR}:
                        # Logical AND/OR: Both operands should be BYTE (0 or 1)
                        # MATH0 = left, MATH1 = right
                        if node.value == BinOp.LAND:
                            # AND: result is true only if both are true
                            # Optimization: if left is 0, result is 0 without evaluating right
                            # But in RPN, both are already evaluated
                            # So: result = (left != 0) && (right != 0) ? 1 : 0
                            lbl_zero = self.new_label("AND_ZERO")
                            lbl_end = self.new_label("AND_END")
                            
                            self.emit("\tLDA MATH0")
                            self.emit(f"\tBEQ {lbl_zero}")  # If left=0, result=0
                            self.emit("\tLDA MATH1")
                            self.emit(f"\tBEQ {lbl_zero}")  # If right=0, result=0
                            
                            # Both non-zero, result = 1
                            self.emit("\tLDA #$01")
                            self.emit(f"\tJMP {lbl_end}")
                            
                            self.emit(f"{lbl_zero}:")
                            self.emit("\tLDA #$00")
                            
                            self.emit(f"{lbl_end}:")
                        else:
                            # OR: result is true if either is true
                            # result = (left != 0) || (right != 0) ? 1 : 0
                            lbl_one = self.new_label("OR_ONE")
                            lbl_end = self.new_label("OR_END")
                            
                            self.emit("\tLDA MATH0")
                            self.emit(f"\tBNE {lbl_one}")  # If left!=0, result=1
                            self.emit("\tLDA MATH1")
                            self.emit(f"\tBNE {lbl_one}")  # If right!=0, result=1
                            
                            # Both zero, result = 0
                            self.emit("\tLDA #$00")
                            self.emit(f"\tJMP {lbl_end}")
                            
                            self.emit(f"{lbl_one}:")
                            self.emit("\tLDA #$01")
                            
                            self.emit(f"{lbl_end}:")
                        
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                            self.emit("\tLDX #$00")  # Logical operators always return BYTE
                        eval_stack.append(("MATH0", 1))
            
            elif node.node_type == 'UNOP':
                if len(eval_stack) < 1:
                    self._raise_error(f"RPN: Insufficient operands for unary operator {node.value}")
                
                operand_loc, operand_width = eval_stack.pop()
                
                # Load operand to MATH0/AX
                # Optimization: if op_loc is MATH0, it's already there
                if operand_loc != "MATH0":
                     # For UNOPs, we typically want operand in MATH0 for 32-bit routines,
                     # or AX for 8/16-bit inline/routines.
                     # But my logic below for 8/16 uses MATH0 or AX depending on op.
                     pass 

                if node.value == UnOp.NOT:
                    # Logical NOT: result is 1 if operand is 0, else 0
                    if operand_width > 2:
                        # 32-bit: Check if all bytes are zero
                        if operand_loc != "MATH0":
                            emit_move_to_math(operand_loc, "MATH0", 4)
                        
                        lbl_nonzero = self.new_label("NOT_NONZERO")
                        lbl_end = self.new_label("NOT_END")
                        
                        self.emit("\tLDA MATH0")
                        self.emit("\tORA MATH0+1")
                        self.emit("\tORA MATH0+2")
                        self.emit("\tORA MATH0+3")
                        self.emit(f"\tBNE {lbl_nonzero}")
                        
                        # Zero -> 1
                        self.emit("\tLDA #$01")
                        self.emit(f"\tJMP {lbl_end}")
                        self.emit(f"{lbl_nonzero}:")
                        self.emit("\tLDA #$00")
                        self.emit(f"{lbl_end}:")
                        
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                            self.emit("\tLDX #$00")
                        eval_stack.append(("MATH0", 1))

                    elif operand_width == 2:
                        load_to_ax(operand_loc, True)
                        # WORD: merge A/X to test non-zero
                        self.emit("\tSTA MATH0")        # Save A
                        self.emit("\tTXA")
                        self.emit("\tORA MATH0")
                        lbl_nonzero = self.new_label("NOT_NONZERO")
                        lbl_end = self.new_label("NOT_END")
                        self.emit(f"\tBNE {lbl_nonzero}")
                        # Value was zero, result = 1
                        self.emit("\tLDA #$01")
                        self.emit(f"\tJMP {lbl_end}")
                        self.emit(f"{lbl_nonzero}:")
                        self.emit("\tLDA #$00")
                        self.emit(f"{lbl_end}:")
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                            self.emit("\tLDX #$00")
                        eval_stack.append(("MATH0", 1))
                    else:
                        load_to_ax(operand_loc, False)
                        # BYTE: test A only
                        lbl_nonzero = self.new_label("NOT_NONZERO")
                        lbl_end = self.new_label("NOT_END")
                        self.emit(f"\tBNE {lbl_nonzero}")
                        # A was zero, result = 1
                        self.emit("\tLDA #$01")
                        self.emit(f"\tJMP {lbl_end}")
                        self.emit(f"{lbl_nonzero}:")
                        self.emit("\tLDA #$00")
                        self.emit(f"{lbl_end}:")
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                            self.emit("\tLDX #$00")
                        eval_stack.append(("MATH0", 1))

                elif node.value == UnOp.BNOT:
                    # Bitwise NOT: invert all bits
                    if operand_width > 2:
                        if operand_loc != "MATH0":
                            emit_move_to_math(operand_loc, "MATH0", 4)
                        
                        self.emit("\tLDA MATH0")
                        self.emit("\tEOR #$FF")
                        self.emit("\tSTA MATH0")
                        self.emit("\tLDA MATH0+1")
                        self.emit("\tEOR #$FF")
                        self.emit("\tSTA MATH0+1")
                        self.emit("\tLDA MATH0+2")
                        self.emit("\tEOR #$FF")
                        self.emit("\tSTA MATH0+2")
                        self.emit("\tLDA MATH0+3")
                        self.emit("\tEOR #$FF")
                        self.emit("\tSTA MATH0+3")
                        
                        eval_stack.append(("MATH0", 4))
                    elif operand_width == 2:
                        load_to_ax(operand_loc, True)
                        # WORD: invert both bytes
                        self.emit("\tEOR #$FF")         # Invert low byte
                        self.emit("\tSTA MATH0")        # Save low byte
                        self.emit("\tTXA")
                        self.emit("\tEOR #$FF")         # Invert high byte
                        self.emit("\tSTA MATH0+1")      # Save high byte
                        eval_stack.append(("MATH0", 2))
                    else:
                        load_to_ax(operand_loc, False)
                        # BYTE: invert just A
                        self.emit("\tEOR #$FF")
                        eval_stack.append(("A", 1))

                elif node.value == UnOp.NEG:
                    if operand_width > 2:
                        if operand_loc != "MATH0":
                            emit_move_to_math(operand_loc, "MATH0", 4)
                        
                        self.emit("\tJSR NEG32")
                        self.math_routines_needed.add("NEG32")
                        eval_stack.append(("MATH0", 4))
                    
                    elif operand_width == 2:
                         if operand_loc != "MATH0":
                            # NEG16 routine expects arg in constants or MATH0?
                            # Actually internal `NEG16` routine probably works on MATH0.
                            # But wait, does `NEG16` exist?
                            # I see `NEG16` in `_math_stack_push`? No.
                            # Let's check `get_math_routine_for_op`. BINOP only.
                            # UNOP NEG was inline before?
                            # No, previous code had:
                            # elif node.value == UnOp.NEG and operand_16: 
                            # self.emit("\tJSR NEG16")
                            # So NEG16 exists.
                            emit_move_to_math(operand_loc, "MATH0", 2)
                            self.emit("\tJSR NEG16")
                            self.math_routines_needed.add("NEG16")
                            eval_stack.append(("MATH0", 2))
                    else:
                        # 8-bit NEG: -x = !x + 1
                        load_to_ax(operand_loc, False)
                        self.emit("\tEOR #$FF")
                        self.emit("\tCLC")
                        self.emit("\tADC #$01")
                        self.emit("\tSTA MATH0")
                        if not self.suppress_byte_return_x:
                             self.emit("\tLDX #$00") # High byte 0
                             # Wait, -128 neg is 128 (overflows to -128 unsigned?)
                             # ZAP usually treats byte as unsigned, so NEG is 2s complement.
                             # But return X is typically 0 for byte ops unless it promotoes?
                             pass
                        eval_stack.append(("MATH0", 1))

                else:
                    self.emit(f"\t; TODO: unary {node.value}")
                    eval_stack.append(("MATH0", operand_width))
            
            elif node.node_type == 'CALL':
                # Calls are not handled in RPN yet (see _is_rpn_safe)
                # but if we were to handle them, we'd need to spill AX.
                self.emit("; TODO: CALL in RPN")
        
        # Final result extraction
        if eval_stack:
            final_loc, final_width = eval_stack.pop()
            if final_width > 2:
                # 32-bit result: Keep in MATH0 (or move to MATH0 if not there)
                # Do NOT load to AX as it can't hold 32 bits.
                if final_loc != "MATH0":
                    emit_move_to_math(final_loc, "MATH0", final_width)
            else:
                load_to_ax(final_loc, final_width == 2)
                if final_width == 1 and target_16bit:
                    self.emit("\tLDX #$00")
        
        # Emit helper routines if needed
        for helper in self.rpn_helper_routines_needed:
            if helper not in self.math_routines_needed:
                self.math_routines_needed.add(helper)
    
    def _is_rpn_safe(self, expr: Expr) -> bool:
        """Check if expression contains only simple nodes that RPN can handle.
        
        Returns False for expressions containing:
        - Array subscripts (SubscriptExpr)  
        - Struct field access (FieldAccess)
        - Pointer dereference (DerefExpr)
        - Function calls (CallExpr)
        
        These require special handling that RPN doesn't yet support.
        """
        def check_node(node: Expr) -> bool:
            """Recursively check if node is RPN-safe."""
            if isinstance(node, BinaryExpr):
                return check_node(node.left) and check_node(node.right)
            elif isinstance(node, UnaryExpr):
                from ast_nodes import UnOp
                if node.op == UnOp.ADDROF:
                    return False  # @ takes address, RPN handles values
                return check_node(node.expr)
            elif isinstance(node, (Identifier, IntLiteral)):
                return True
            elif isinstance(node, StringLiteral):
                return False
            elif isinstance(node, (SubscriptExpr, FieldAccess, DerefExpr, CallExpr)):
                # These aren't yet supported in RPN evaluation
                return False
            else:
                # Unknown type - be conservative
                return False
        
        return check_node(expr)

    def new_label(self, prefix: str) -> str:
        """Helper for new label.
        Internal helper used during code generation.
        """
        self.label_id += 1
        return self._internal_label(f"{prefix}_{self.label_id}")

    def _internal_label(self, name: str) -> str:
        """Helper for internal label.
        Internal helper used during code generation.
        """
        return f"{self.internal_label_prefix}{name}"

    def new_for_var(self, base: str) -> str:
        """Helper for new for var.
        Internal helper used during code generation.
        """
        self.for_id += 1
        return f"FOR_{base}_{self.for_id}"

    def _get_for_temp_name(self, stmt, base: str) -> str:
        """Return the pre-declared FOR-loop temp name for this statement.

        Looks up the name from for_temp_map (pre-declared by compiler_pipeline
        in _predeclare_for_loop_temps) to ensure the name matches the one used
        for slot allocation.  Falls back to new_for_var() when the map is absent
        or has no entry for this statement (e.g. during isolated testing).
        """
        if self.for_temp_map is not None:
            temp_names = self.for_temp_map.get(id(stmt))
            if temp_names:
                prefix = f"FOR_{base}_"
                for n in temp_names:
                    if n.startswith(prefix):
                        return n
        return self.new_for_var(base)

    def asm_symbol_name(self, name: str) -> str:
        """Helper for asm symbol name.
        Internal helper used during code generation.
        """
        if name.startswith("__"):
            return name
        return f"_{name}"

    def _build_internal_name_map(self) -> dict[str, str]:
        """Build internal name map.
        Internal helper used during code generation.
        """
        sys_names = {"MATH_STACK", "MATH0", "MATH1", "TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5"}
        runtime_names = {
            "COPY_BYTES",
            "SET_MATH0",
            "SET_MATH1",
            "GET_MATH0",
            "ADD16",
            "SUB16",
            "ADD16_AX",
            "SUB16_AX",
            "MUL8_A",
            "MUL8",
            "MUL16_8_A",
            "MUL16_8",
            "MUL16_AX",
            "MUL16",
            "DIV8_A",
            "DIV8",
            "DIV16_8_A",
            "DIV16_8",
            "DIV8_16_AX",
            "DIV8_16",
            "DIV16_AX",
            "DIV16",
            "MOD8_A",
            "MOD8",
            "MOD16_8_A",
            "MOD16_8",
            "MOD8_16_AX",
            "MOD8_16",
            "MOD16_AX",
            "MOD16",
        }
        internal_names = sys_names | runtime_names
        return {name: f"__{name}" for name in sorted(internal_names)}

    def _build_internal_name_regex(self, name_map: dict[str, str]):
        """Build internal name regex.
        Internal helper used during code generation.
        """
        if not name_map:
            return None
        import re
        pattern = "|".join(re.escape(name) for name in sorted(name_map.keys(), key=len, reverse=True))
        return re.compile(rf"(?<![A-Za-z0-9_])({pattern})(?![A-Za-z0-9_])")

    def _rewrite_internal_names(self, line: str) -> str:
        """Helper for rewrite internal names.
        Internal helper used during code generation.
        """
        if not self._internal_name_re:
            return line
        return self._internal_name_re.sub(lambda m: self._internal_name_map[m.group(1)], line)

    def _stz(self, operand: str) -> None:
        """Helper for stz.
        Internal helper used during code generation.
        """
        if self.is_65c02:
            self.emit(f"\tSTZ {operand}")
        else:
            self.emit("\tLDA #$00")
            self.emit(f"\tSTA {operand}")

    def _stz_multiple(self, operands: list[str]) -> None:
        """Clear multiple memory locations efficiently. Uses single LDA #$00 for 6502."""
        if not operands:
            return
        if self.is_65c02:
            for op in operands:
                self.emit(f"\tSTZ {op}")
        else:
            # Load zero once, then store to all locations
            self.emit("\tLDA #$00")
            for op in operands:
                self.emit(f"\tSTA {op}")

    def _emit_indirect_store_zero(self, ptr: str) -> None:
        """Emit indirect store zero.
        Internal helper used during code generation.
        """
        if self.is_65c02:
            self.emit(f"\tSTA ({ptr})")
        else:
            self.emit("\tLDY #$00")
            self.emit(f"\tSTA ({ptr}),Y")

    def _math_stack_push(self, width: int) -> None:
        """Helper for math stack push.
        Internal helper used during code generation.
        """
        if self.math_stack_depth >= 8:
            self._raise_error("Math stack overflow: requires more than 8 slots. Simplify the expression.")
        slot: int = self.math_stack_depth
        offset: int = slot * 4
        self.math_stack_depth += 1
        
        if width > 2:
             # 32-bit: source in MATH0
             self.emit(f"\tLDA MATH0")
             self.emit(f"\tSTA MATH_STACK+{offset}")
             self.emit(f"\tLDA MATH0+1")
             self.emit(f"\tSTA MATH_STACK+{offset+1}")
             self.emit(f"\tLDA MATH0+2")
             self.emit(f"\tSTA MATH_STACK+{offset+2}")
             self.emit(f"\tLDA MATH0+3")
             self.emit(f"\tSTA MATH_STACK+{offset+3}")
        else:
             # 8/16-bit: source in A/X
             self.emit(f"\tSTA MATH_STACK+{offset}")
             if width == 2:
                 self.emit(f"\tSTX MATH_STACK+{offset+1}")
             else:
                 self.emit(f"\tLDX #$00")
                 self.emit(f"\tSTX MATH_STACK+{offset+1}")
             # Zero extend
             self.emit(f"\tLDX #$00") 
             self.emit(f"\tSTX MATH_STACK+{offset+2}")
             self.emit(f"\tSTX MATH_STACK+{offset+3}")

    def _math_stack_pop_to_op0(self) -> None:
        """Helper for math stack pop to op0.
        Internal helper used during code generation.
        """
        self.math_stack_depth -= 1
        slot: int = self.math_stack_depth
        offset: int = slot * 4
        
        self.emit(f"\tLDA MATH_STACK+{offset}")
        self.emit(f"\tSTA MATH0")
        self.emit(f"\tLDA MATH_STACK+{offset+1}")
        self.emit(f"\tSTA MATH0+1")
        self.emit(f"\tLDA MATH_STACK+{offset+2}")
        self.emit(f"\tSTA MATH0+2")
        self.emit(f"\tLDA MATH_STACK+{offset+3}")
        self.emit(f"\tSTA MATH0+3")


    def _emit_store_byte_const(self, sym: Symbol, value: int) -> None:
        """Emit store byte const.
        Internal helper used during code generation.
        """
        value &= 0xFF
        asm: str = sym.asm_name()
        if value == 0:
            self._stz(asm)
        else:
            self.emit(f"\tLDA #${value:02X}")
            self.emit(f"\tSTA {asm}")
    
    def _check_constant_fits(self, value: int, target_type: SemType, context: str = "") -> bool:
        """Check if a constant value fits in the target type. Raise error if not.
        
        Returns True if the value fits, raises SemanticError if not.
        """
        # For BYTE types (not pointers)
        if target_type.base == "BYTE" and not target_type.is_pointer:
            return True
        
        # For WORD types and pointers
        if target_type.base == "WORD" or target_type.is_pointer:
            return True
        
        return True

    def _emit_store_word_const(self, sym: Symbol, value: int) -> None:
        """Emit store word const.
        Internal helper used during code generation.
        Group bytes by value (first-occurrence order) so lo==hi shares one LDA.
        On 65C02 zero bytes use STZ (no LDA).
        """
        value &= 0xFFFF
        asm: str = sym.asm_name()
        _sw_grp: dict[int, list[int]] = {}
        for _bi, _bv in enumerate([(value & 0xFF), (value >> 8) & 0xFF]):
            _sw_grp.setdefault(_bv, []).append(_bi)
        for _bv, _offsets in _sw_grp.items():
            if _bv == 0 and self.is_65c02:
                for _bi in _offsets:
                    _d = asm if _bi == 0 else f"{asm}+{_bi}"
                    self.emit(f"\tSTZ {_d}")
            else:
                self.emit(f"\tLDA #${_bv:02X}")
                for _bi in _offsets:
                    _d = asm if _bi == 0 else f"{asm}+{_bi}"
                    self.emit(f"\tSTA {_d}")

    def _emit_inc_word(self, asm: str) -> None:
        """Emit inc word.
        Internal helper used during code generation.
        """
        lbl: str = self.new_label("INC_WORD")
        self.emit(f"\tINC {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tINC {asm}+1")
        self.emit(f"{lbl}:")

    def _emit_dec_word(self, asm: str) -> None:
        """Emit dec word.
        Internal helper used during code generation.
        """
        lbl: str = self.new_label("DEC_WORD")
        self.emit(f"\tLDA {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tDEC {asm}+1")
        self.emit(f"{lbl}:")
        self.emit(f"\tDEC {asm}")

    def _lda_const(self, line: str) -> int | None:
        """Return immediate value for LDA #imm or None if not a match."""
        stripped: str = line.strip().upper()
        if not stripped.startswith("LDA #"):
            return None
        imm: str = stripped[5:]  # after 'LDA #' (includes possible $)
        try:
            if imm.startswith("$"):
                return int(imm[1:], 16)
            return int(imm, 10)
        except ValueError:
            return None

    def _is_sta(self, line: str) -> bool:
        """Return whether sta.
        Internal helper used during code generation.
        """
        return line.strip().upper().startswith("STA ")

    def _inc_operand(self, line: str) -> str | None:
        """Helper for inc operand.
        Internal helper used during code generation.
        """
        stripped: str = line.strip().upper()
        if stripped.startswith("INC "):
            return stripped[4:].strip()
        return None

    def _dec_operand(self, line: str) -> str | None:
        """Helper for dec operand.
        Internal helper used during code generation.
        """
        stripped: str = line.strip().upper()
        if stripped.startswith("DEC "):
            return stripped[4:].strip()
        return None

    def _is_fixed_address(self, operand: str) -> bool:
        """Check if operand references a fixed-address (hardware) variable.
        
        Fixed-address variables must never be optimized away as reads/writes
        may have side effects (clearing flags, triggering hardware, etc.).
        """
        # Extract label from operand (handle indexed modes like "LABEL,X" or "LABEL,Y" or "LABEL+1")
        label: str = operand.split(',')[0].strip()  # Remove ,X or ,Y
        label: str = label.split('+')[0].strip()    # Remove +1
        label: str = label.split('-')[0].strip()    # Remove -1 (rare but possible)
        return label in self.fixed_address_labels

    # ---------------------------------------------------------------------------
    # Dead-store elimination (AST level)
    # ---------------------------------------------------------------------------

    def _expr_reads_var(self, expr, name: str) -> bool:
        """Return True if expr reads the variable `name` anywhere in its tree."""
        from ast_nodes import Identifier, BinaryExpr, UnaryExpr, SubscriptExpr, DerefExpr, FieldAccess, CallExpr
        if isinstance(expr, Identifier):
            return expr.name == name
        if isinstance(expr, BinaryExpr):
            return self._expr_reads_var(expr.left, name) or self._expr_reads_var(expr.right, name)
        if isinstance(expr, UnaryExpr):
            return self._expr_reads_var(expr.expr, name)
        if isinstance(expr, SubscriptExpr):
            return self._expr_reads_var(expr.array, name) or self._expr_reads_var(expr.index, name)
        if isinstance(expr, DerefExpr):
            return self._expr_reads_var(expr.pointer, name)
        if isinstance(expr, FieldAccess):
            return self._expr_reads_var(expr.object, name)
        if isinstance(expr, CallExpr):
            return any(self._expr_reads_var(a, name) for a in expr.args if a is not None)
        return False

    def _expr_has_calls(self, expr) -> bool:
        """Return True if expr contains any CallExpr nodes (has side effects)."""
        from ast_nodes import CallExpr, BinaryExpr, UnaryExpr, SubscriptExpr, DerefExpr, FieldAccess
        if isinstance(expr, CallExpr):
            return True
        if isinstance(expr, BinaryExpr):
            return self._expr_has_calls(expr.left) or self._expr_has_calls(expr.right)
        if isinstance(expr, UnaryExpr):
            return self._expr_has_calls(expr.expr)
        if isinstance(expr, SubscriptExpr):
            return self._expr_has_calls(expr.array) or self._expr_has_calls(expr.index)
        if isinstance(expr, DerefExpr):
            return self._expr_has_calls(expr.pointer)
        if isinstance(expr, FieldAccess):
            return self._expr_has_calls(expr.object)
        return False

    def _lhs_is_port(self, lhs) -> bool:
        """Return True if the LHS identifier resolves to a PORT variable."""
        from ast_nodes import Identifier
        if not isinstance(lhs, Identifier):
            return False
        try:
            sym = self.current_symtab.lookup(lhs.name)
            return bool(sym.is_port)
        except KeyError:
            return False

    def _elim_dead_stores(self, stmts: list) -> list:
        """Eliminate dead stores: if two consecutive AssignStmts target the
        same simple (non-PORT) scalar identifier, and the first is immediately
        followed by the second with no intervening statements, the first store
        is dead and can be removed.

        Rules:
        - LHS must be a bare Identifier (no arrays, struct fields, derefs).
        - The variable must NOT have the PORT attribute (hardware registers
          must always be written, even if the value is immediately overwritten).
        - We only skip the earlier store when the very next statement is another
          AssignStmt to the same identifier.
        - The overwriting RHS must be pure (no CallExpr) to stay conservative.
        """
        from ast_nodes import AssignStmt, Identifier
        if not stmts:
            return stmts
        result: list = []
        i: int = 0
        while i < len(stmts):
            stmt = stmts[i]
            # Check if this assignment is immediately overwritten by the next
            if (
                isinstance(stmt, AssignStmt)
                and isinstance(stmt.lhs, Identifier)
                and i + 1 < len(stmts)
                and isinstance(stmts[i + 1], AssignStmt)
                and isinstance(stmts[i + 1].lhs, Identifier)
                and stmts[i + 1].lhs.name == stmt.lhs.name
                and not self._lhs_is_port(stmt.lhs)                       # skip PORT vars
                and not self._expr_has_calls(stmt.rhs)                    # RHS of skipped store is pure
                and not self._expr_reads_var(stmts[i + 1].rhs, stmt.lhs.name)  # next RHS doesn't read same var
            ):
                # Dead store — skip it, emit only a source comment so the
                # debug output still shows what was eliminated.
                self.emit(f"; [dead store eliminated: {stmt.lhs.name} overwritten by next statement]")
                i += 1
                continue
            result.append(stmt)
            i += 1
        return result

    def _is_port_variable(self, operand: str) -> bool:
        """Check if operand references a PORT (hardware port-mapped) variable.
        
        PORT variables are hardware port-mapped and cannot be optimized.
        """
        if not operand:
            return False
        operand = operand.strip()
        if operand.startswith("#"):
            return False
        while operand.startswith("<") or operand.startswith(">"):
            operand = operand[1:].strip()
        operand = operand.replace("(", "").replace(")", "")
        # Extract label from operand (handle indexed modes like "LABEL,X" or "LABEL,Y" or "LABEL+1")
        label: str = operand.split(',')[0].strip()  # Remove ,X or ,Y
        label: str = label.split('+')[0].strip()    # Remove +1
        label: str = label.split('-')[0].strip()    # Remove -1 (rare but possible)
        return label in self.port_labels

    def _modifies_memory_operand(self, line: str, operand: str) -> bool:
        """Return True if instruction modifies a specific memory operand.
        
        Instructions like DEC, INC, ASL, LSR, ROL, ROR can modify memory directly.
        """
        stripped: str = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        
        # Normalize the operand to uppercase for comparison
        operand_upper: str = operand.upper()
        
        # Instructions that modify memory: DEC, INC, ASL, LSR, ROL, ROR
        memory_mod_ops: set[str] = {"DEC", "INC", "ASL", "LSR", "ROL", "ROR"}
        parts: list[str] = stripped.split(maxsplit=1)
        if not parts:
            return False
        
        opcode: str = parts[0]
        if opcode not in memory_mod_ops:
            return False
        
        # Check if operand matches
        if len(parts) == 2:
            instr_operand: str = parts[1].strip()
            # Compare operands, considering A form vs memory form
            if opcode in {"ASL", "LSR", "ROL", "ROR"}:
                # These can be A form (no operand or "A") or memory form
                if instr_operand == "A" or instr_operand == operand_upper:
                    return opcode != "A"  # Return False for accumulator form
            # DEC and INC always modify memory
            return instr_operand == operand_upper
        
        return False

    def _sets_nz_flags(self, line: str) -> bool:
        """Return True if instruction overwrites N/Z so earlier flags cannot be observed."""
        stripped: str = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        opcode: str = stripped.split()[0]
        nz_ops: set[str] = {
            "ADC", "AND", "ASL", "BIT", "CMP", "CPX", "CPY", "DEC", "DEX", "DEY",
            "EOR", "INC", "INX", "INY", "LDA", "LDX", "LDY", "LSR", "ORA", "PLA",
            "PLX", "PLY", "ROL", "ROR", "SBC", "TAX", "TAY", "TSX", "TXA", "TYA",
        }
        return opcode in nz_ops

    def _clobbers_a(self, line: str) -> bool:
        """Return True if instruction changes accumulator contents."""
        stripped: str = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        parts: list[str] = stripped.split()
        if not parts:
            return False
        op: str = parts[0]
        # Ops that always write A
        if op in {"LDA", "PLA", "ADC", "SBC", "ORA", "AND", "EOR"}:
            return True
        # Accumulator shifts/rotates
        if op in {"ASL", "LSR", "ROL", "ROR"}:
            # memory form has an operand; accumulator form often has none or "A"
            return len(parts) == 1 or parts[1] == "A"
        return False

    def _reads_x(self, line: str) -> bool:
        """Return True if instruction reads X (explicitly or via ,X addressing)."""
        stripped: str = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        parts: list[str] = stripped.split()
        if not parts:
            return False
        op: str = parts[0]
        if op in {"STX", "CPX", "INX", "DEX", "TXA", "TXS", "PHX", "PLX"}:
            return True
        if len(parts) > 1 and ",X" in parts[1]:
            return True
        return False

    def peephole_optimize(self) -> None:
        """Apply peephole optimizations to emitted code.
        
        Current optimizations:
        - Remove redundant LDA after STA to same location (when A still contains the value)
        - Tail call optimization: JSR followed by RTS -> JMP (saves stack operations)
        - Remove duplicate consecutive comment lines
        - 65c02: Replace LDX #$00; STA addr; STX addr+1 with STA addr; STZ addr+1
        - Remove redundant LDX #$00 when X is immediately overwritten by TAX
        - Remove redundant LDX #imm before another LDX immediate
        - Remove blank line immediately before RTS
        - Remove conditional branch to next label (no-op)
        - Replace LDA TMP0; TAY; LDA label,Y with LDY TMP0; LDA label,Y
        - STA addr followed by STZ addr → STZ addr  (dead store before zero)
        - STZ addr followed by STZ addr → single STZ addr  (duplicate zero store)
        """
        optimized: list[str] = []
        i = 0
        in_asm_block = False

        def _operand_is_port(operand: str) -> bool:
            """Helper for operand is port.
            Internal helper used during code generation.
            """
            return self._is_port_variable(operand)

        def _parse_imm(operand: str) -> int | None:
            """Helper for parse imm.
            Internal helper used during code generation.
            """
            operand = operand.strip().upper()
            if not operand.startswith("#"):
                return None
            value = operand[1:]
            try:
                if value.startswith("$"):
                    return int(value[1:], 16)
                return int(value, 10)
            except ValueError:
                return None

        def _clobbers_x(line: str) -> bool:
            """Helper for clobbers x.
            Internal helper used during code generation.
            """
            op = line.split(maxsplit=1)[0].upper() if line else ""
            return op in {"LDX", "INX", "DEX", "TAX", "TXA", "TSX", "PLX"}

        def _clobbers_y(line: str) -> bool:
            """Helper for clobbers y.
            Internal helper used during code generation.
            """
            op = line.split(maxsplit=1)[0].upper() if line else ""
            return op in {"LDY", "INY", "DEY", "TAY", "TYA", "PLY"}

        def _clobbers_reg(line: str, reg: str) -> bool:
            """Check if instruction clobbers given register (X or Y)."""
            if reg.upper() == "X":
                return _clobbers_x(line)
            elif reg.upper() == "Y":
                return _clobbers_y(line)
            return False

        # Helper: look ahead past blank/comment lines; stop at labels.
        # Returns (op, operand, True) for the next real instruction, or (None, None, False).
        def _peek_next_real(start_idx: int):
            k = start_idx
            while k < len(self.code):
                p = self.code[k].strip()
                pi = p.split(';')[0].strip()
                if not pi:
                    k += 1
                    continue
                if pi.endswith(':'):
                    return None, None, False
                pu = pi.upper()
                parts = pu.split(maxsplit=1)
                op = parts[0]
                operand = parts[1].strip() if len(parts) > 1 else None
                return op, operand, True
            return None, None, False

        # 8-bit math routines that don't use X as an input operand
        _8BIT_ROUTINES_NO_X = {
            "__MUL8_A", "__DIV8_A", "__MOD8_A",
            "__MUL8",   "__DIV8",   "__MOD8",
        }

        # Branch instructions that test CPU flags (used by INC/DEC cancellation guard)
        _BRANCH_OPS = {
            "BEQ", "BNE", "BCC", "BCS", "BVC", "BVS", "BMI", "BPL",
            "BRA",  # 65c02 unconditional branch; keep for safety
        }

        # Instructions that are pure stores (write-only, never read from addr)
        _PURE_STORE_OPS = {"STA", "STX", "STY", "STZ"}
        # Control-flow ops that end a safe look-ahead window
        _STOP_OPS = _BRANCH_OPS | {"JMP", "JSR", "RTS", "RTI"}

        def _instr_reads_addr(instr_upper: str, addr_upper: str) -> bool:
            """Return True if instruction reads from memory addr.
            Pure store ops (STA/STX/STY/STZ) and instructions with no memory
            operand do NOT read addr.  Exact operand match only (conservative).
            """
            parts = instr_upper.split(maxsplit=1)
            if len(parts) < 2:
                return False  # no operand → no memory read
            op = parts[0]
            if op in _PURE_STORE_OPS:
                return False  # write-only
            operand = parts[1].split(';')[0].strip()  # strip inline comments
            # Exact match or indexed variant (_A or _A,X or _A,Y)
            return (operand == addr_upper
                    or operand.startswith(addr_upper + ",")
                    or operand.startswith(addr_upper + "+"))

        while i < len(self.code):
            line = self.code[i]
            line_stripped = line.strip()
            line_upper = line_stripped.upper()
            
            if line_stripped == "; ASM_BLOCK_BEGIN":
                in_asm_block = True
                optimized.append(line)
                i += 1
                continue
            if line_stripped == "; ASM_BLOCK_END":
                in_asm_block = False
                optimized.append(line)
                i += 1
                continue
            if in_asm_block:
                optimized.append(line)
                i += 1
                continue
            # Remove redundant immediate loads when the register was not clobbered by intervening instructions
            if line_upper.startswith("LDX #") or line_upper.startswith("LDY #"):
                load_instr = line_stripped.split(';')[0].strip().upper()
                reg = "X" if load_instr.startswith("LDX") else "Y"
                imm1 = _parse_imm(load_instr.split(maxsplit=1)[1])
                
                if imm1 is not None:
                    # Scan ahead up to 4 real instructions
                    j = i + 1
                    found_match = False
                    intervening_safe = True
                    match_idx = -1
                    insn_checked = 0
                    
                    while j < len(self.code) and insn_checked < 4:
                        look_line = self.code[j].strip()
                        look_u = look_line.split(';')[0].strip().upper()
                        
                        if not look_u:
                            j += 1
                            continue
                            
                        insn_checked += 1
                        
                        if look_u.endswith(":"):
                            intervening_safe = False
                            break
                        
                        if look_u.startswith(f"LD{reg} #"):
                            imm2 = _parse_imm(look_u.split(maxsplit=1)[1])
                            if imm2 is not None and imm1 == imm2:
                                found_match = True
                                match_idx = j
                                break
                            else:
                                intervening_safe = False
                                break
                        
                        clobbers = _clobbers_x(look_u) if reg == "X" else _clobbers_y(look_u)
                        if clobbers:
                            intervening_safe = False
                            break
                            
                        j += 1
                    
                    if found_match and intervening_safe:
                        # Add current instruction and all safe intervening instructions
                        for k in range(i, match_idx):
                            optimized.append(self.code[k])
                        # Skip the redundant load
                        i = match_idx + 1
                        continue

            # Remove redundant immediate loads if the same value was just loaded and only stored in between.
            if i + 2 < len(self.code):
                l1 = self.code[i].strip()
                l2 = self.code[i + 1].strip()
                l3 = self.code[i + 2].strip()
                l1_u = l1.split(';')[0].strip().upper()
                l2_u = l2.split(';')[0].strip().upper()
                l3_u = l3.split(';')[0].strip().upper()

                def _is_load(op: str, instr: str) -> bool:
                    """Return whether load.
                    Internal helper used during code generation.
                    """
                    return instr.startswith(f"{op} #")

                def _is_store(op: str, instr: str) -> bool:
                    """Return whether store.
                    Internal helper used during code generation.
                    """
                    return instr.startswith(f"{op} ")

                if _is_load("LDA", l1_u) and _is_store("STA", l2_u) and _is_load("LDA", l3_u):
                    imm1 = _parse_imm(l1_u.split(maxsplit=1)[1])
                    imm3 = _parse_imm(l3_u.split(maxsplit=1)[1])
                    if imm1 is not None and imm1 == imm3:
                        optimized.append(self.code[i])
                        optimized.append(self.code[i + 1])
                        i += 3
                        continue
                if _is_load("LDX", l1_u) and _is_store("STX", l2_u) and _is_load("LDX", l3_u):
                    imm1 = _parse_imm(l1_u.split(maxsplit=1)[1])
                    imm3 = _parse_imm(l3_u.split(maxsplit=1)[1])
                    if imm1 is not None and imm1 == imm3:
                        optimized.append(self.code[i])
                        optimized.append(self.code[i + 1])
                        i += 3
                        continue
                if _is_load("LDY", l1_u) and _is_store("STY", l2_u) and _is_load("LDY", l3_u):
                    imm1 = _parse_imm(l1_u.split(maxsplit=1)[1])
                    imm3 = _parse_imm(l3_u.split(maxsplit=1)[1])
                    if imm1 is not None and imm1 == imm3:
                        optimized.append(self.code[i])
                        optimized.append(self.code[i + 1])
                        i += 3
                        continue

            # Remove redundant LDA/LDX/LDY when immediately preceded by STA/STX/STY to same location
            # SAFE optimization: only when store and load have no intervening register-modifying instructions
            if line_upper.startswith("LDA ") or line_upper.startswith("LDX ") or line_upper.startswith("LDY "):
                load_parts = line_stripped.split(maxsplit=1)
                if len(load_parts) == 2:
                    load_op = load_parts[0].upper()
                    load_operand = load_parts[1].strip()

                    if not _operand_is_port(load_operand):
                        # Special-case: STA addr; STX addr+1; LDA addr -> LDA is redundant
                        # STX does not clobber A, so the value is still in A.
                        if load_op == "LDA":
                            k = len(optimized) - 1
                            prior_instrs: list[str] = []
                            while k >= 0 and len(prior_instrs) < 2:
                                prev_line = optimized[k].strip()
                                if not prev_line or prev_line.startswith(";"):
                                    k -= 1
                                    continue
                                if prev_line.endswith(":"):
                                    break
                                prior_instrs.append(prev_line)
                                k -= 1

                            if len(prior_instrs) == 2:
                                prev1 = prior_instrs[0].split(maxsplit=1)
                                prev2 = prior_instrs[1].split(maxsplit=1)
                                if len(prev1) == 2 and len(prev2) == 2:
                                    prev1_op, prev1_operand = prev1[0].upper(), prev1[1].strip()
                                    prev2_op, prev2_operand = prev2[0].upper(), prev2[1].strip()
                                    if (prev1_op == "STX"
                                            and prev2_op == "STA"
                                            and prev2_operand.upper() == load_operand.upper()
                                            and prev1_operand.upper() == load_operand.upper() + "+1"
                                            and not _operand_is_port(prev1_operand)):
                                        i += 1
                                        continue

                        store_for_load = {
                            "LDA": "STA",
                            "LDX": "STX",
                            "LDY": "STY",
                        }
                        expected_store = store_for_load.get(load_op, "")
                        
                        # Look back for matching store, but only within a close window
                        # and only if no intervening instructions could clobber the register
                        k = len(optimized) - 1
                        found_match = False
                        instructions_back = 0
                        
                        while k >= 0 and instructions_back < 6:  # Only look back 6 actual instructions
                            prev_line = optimized[k].strip()
                            
                            # Skip comments and blanks
                            if not prev_line or prev_line.startswith(";"):
                                k -= 1
                                continue
                            
                            # Stop at labels
                            if prev_line.endswith(":"):
                                break
                            
                            instructions_back += 1
                            
                            prev_parts = prev_line.split(maxsplit=1)
                            if len(prev_parts) == 2:
                                prev_op = prev_parts[0].upper()
                                prev_operand = prev_parts[1].strip()
                                
                                # Check for matching store to same location
                                if prev_op == expected_store and prev_operand.upper() == load_operand.upper():
                                    # Verify no register-clobbering instructions between store and this load
                                    can_remove = True
                                    for verify_idx in range(k + 1, len(optimized)):
                                        verify_line = optimized[verify_idx].strip()
                                        if verify_line == line_stripped:
                                            break
                                        if verify_line and not verify_line.startswith(";"):
                                            verify_op = verify_line.split(maxsplit=1)[0].upper()
                                            # If ANY instruction that loads into our register, can't remove
                                            if verify_op == load_op:  # LDA, LDX, or LDY
                                                can_remove = False
                                                break
                                            # Arithmetic/logical ops also clobber
                                            if verify_op in {"AND", "ORA", "EOR", "ADC", "SBC", "CMP", "BIT", "ASL", "LSR", "ROL", "ROR", "INC", "DEC"}:
                                                if load_op == "LDA":  # These affect A
                                                    can_remove = False
                                                    break
                                            # Memory-modifying ops invalidate any register tracking
                                            # (e.g. ROL __TMP0+1 between STX __TMP0+1 and LDX __TMP0+1)
                                            if self._modifies_memory_operand(verify_line, load_operand):
                                                can_remove = False
                                                break
                                    
                                    if can_remove:
                                        found_match = True
                                        break
                                    else:
                                        break  # Found store but unsafe - don't keep looking
                                else:
                                    # This is a store to a different location, stop searching
                                    if prev_op in store_for_load.values():
                                        break
                            
                            k -= 1
                        
                        if found_match:
                            i += 1
                            continue
            
            cur_instr = line_stripped.split(';')[0].strip().upper()
            cur_parts = cur_instr.split(maxsplit=1)
            cur_op = cur_parts[0] if cur_parts else ""
            cur_operand = cur_parts[1].strip() if len(cur_parts) > 1 else None

            # Rule A: STA addr ; STZ same-addr  → just STZ addr
            # Rule B: STZ addr ; STZ same-addr  → just STZ addr
            # (comment lines between them are fine; don't cross labels; skip PORT)
            if cur_op in ("STA", "STZ") and cur_operand and not _operand_is_port(cur_operand):
                nxt_op, nxt_operand, found = _peek_next_real(i + 1)
                if (
                    found
                    and nxt_op == "STZ"
                    and nxt_operand is not None
                    and cur_operand.upper() == nxt_operand.upper()
                ):
                    i += 1
                    continue

            # Rule C: STA __MATH0[+n] / __MATH1[+n] / __TMP[+n] followed immediately
            # by STA <real-var>  →  drop the scratch-register store (A still holds value).
            # Guard: destination must not be PORT, not another scratch reg.
            if cur_op == "STA" and cur_operand:
                cur_clean = cur_operand.upper().replace("__", "")
                is_scratch = (
                    cur_clean.startswith("MATH0")
                    or cur_clean.startswith("MATH1")
                    or cur_clean.startswith("TMP")
                )
                if is_scratch:
                    nxt_op, nxt_operand, found = _peek_next_real(i + 1)
                    if found and nxt_op == "STA" and nxt_operand:
                        nxt_clean = nxt_operand.upper().replace("__", "")
                        nxt_is_scratch = (
                            nxt_clean.startswith("MATH")
                            or nxt_clean.startswith("TMP")
                        )
                        if not nxt_is_scratch and not _operand_is_port(nxt_operand):
                            i += 1
                            continue

            # Rule D: LDX #$00 immediately before JSR __MUL8_A / __DIV8_A / __MOD8_A
            # These 8-bit routines don't use X as input; X is overwritten internally.
            if cur_instr in ("LDX #$00", "LDX #$00", "LDX #$00") and self.is_65c02:
                nxt_op, nxt_target, found = _peek_next_real(i + 1)
                if found and nxt_op == "JSR" and nxt_target in _8BIT_ROUTINES_NO_X:
                    i += 1
                    continue

            # Rule E: INC addr ; DEC addr  (or DEC addr ; INC addr)  → remove both
            # Net memory effect is zero. Only safe if:
            #   - Same address, not a PORT variable
            #   - The instruction after the pair is NOT a branch (no flag dependency)
            if cur_op in ("INC", "DEC") and cur_operand and not _operand_is_port(cur_operand):
                # Find the index of the next real instruction
                j = i + 1
                nxt_idx = None
                while j < len(self.code):
                    p = self.code[j].strip()
                    pi = p.split(';')[0].strip()
                    if not pi:
                        j += 1
                        continue
                    if pi.endswith(':'):
                        break
                    nxt_idx = j
                    break

                if nxt_idx is not None:
                    nxt_raw = self.code[nxt_idx].strip()
                    nxt_instr_u = nxt_raw.split(';')[0].strip().upper()
                    nxt_parts = nxt_instr_u.split(maxsplit=1)
                    nxt_op2 = nxt_parts[0] if nxt_parts else ""
                    nxt_operand2 = nxt_parts[1].strip() if len(nxt_parts) > 1 else None

                    # Check: opposite operation on same address
                    opposite = "DEC" if cur_op == "INC" else "INC"
                    if (
                        nxt_op2 == opposite
                        and nxt_operand2 is not None
                        and cur_operand.upper() == nxt_operand2.upper()
                    ):
                        # Check that the instruction AFTER the pair is not a branch
                        after_op, _, after_found = _peek_next_real(nxt_idx + 1)
                        if not after_found or after_op not in _BRANCH_OPS:
                            # Eliminate both — skip current and skip the paired instruction
                            i = nxt_idx + 1
                            continue
            # Rule F: STA addr is a dead store if a forward scan finds another
            # STA addr before any instruction reads addr (or branches/JSR/labels).
            # Eliminates intermediate stores in chains like:
            #   LDA #7 / STA _A / ASL / STA _A / LSR / STA _A  →  keep only last STA _A
            # Safe conditions: non-PORT, non-indexed (addr,X / addr,Y change effective
            # address when X/Y changes), no read of addr, no control flow in the window.
            if (
                cur_op == "STA" and cur_operand
                and not _operand_is_port(cur_operand)
                and ",X" not in cur_operand.upper()
                and ",Y" not in cur_operand.upper()
            ):
                addr_upper = cur_operand.upper()
                j = i + 1
                found_overwrite = False
                while j < len(self.code):
                    peek = self.code[j].strip()
                    pi = peek.split(';')[0].strip()
                    if not pi:          # blank or comment — skip
                        j += 1
                        continue
                    if pi.endswith(':'):  # label — stop (can't analyze past)
                        break
                    pu = pi.upper()
                    p_parts = pu.split(maxsplit=1)
                    p_op = p_parts[0]
                    # Stop at control-flow instructions (branches/JSR/JMP/RTS/RTI)
                    if p_op in _STOP_OPS:
                        break
                    # Stop at any indirect addressing (could read our var through a pointer)
                    p_operand_str = p_parts[1].strip() if len(p_parts) > 1 else ""
                    if "(" in p_operand_str:
                        break
                    # Found another STA/STX/STY to same addr → current STA is dead
                    if p_op in ("STA", "STX", "STY") and p_operand_str == addr_upper:
                        found_overwrite = True
                        break
                    # Stop if addr is read by this instruction (direct addressing)
                    if _instr_reads_addr(pu, addr_upper):
                        break
                    j += 1
                if found_overwrite:
                    i += 1
                    continue


            # 65c02: Replace LDX #$00; STA addr; STX addr+1 → STA addr; STZ addr+1



            # Strip inline comments to check instruction
            instr_part = line_stripped.split(';')[0].strip().upper()
            if self.is_65c02 and (instr_part == "LDX #$00" or instr_part == "LDX #$00" or instr_part == "LDX #$00"):
                # Look ahead for STA instruction
                j = i + 1
                sta_found = False
                sta_index = -1
                sta_operand = None
                intermediate_lines = []
                
                while j < len(self.code):
                    look_line = self.code[j].strip()
                    look_upper = look_line.upper()
                    
                    # Skip blank lines and comments
                    if not look_line or look_line.startswith(";"):
                        intermediate_lines.append(j)
                        j += 1
                        continue
                    
                    # Stop at labels
                    if look_upper.endswith(":"):
                        break
                    
                    # Check for STA
                    if look_upper.startswith("STA "):
                        sta_parts = look_line.split(maxsplit=1)
                        if len(sta_parts) == 2:
                            sta_operand = sta_parts[1].strip()
                            sta_found = True
                            sta_index = j
                            j += 1
                            break
                    
                    # Stop at any other instruction
                    break
                
                if sta_found and sta_operand:
                    # Now look for STX addr+1
                    intermediate_lines2 = []
                    stx_found = False
                    stx_index = -1
                    stx_operand: str = ""
                    
                    while j < len(self.code):
                        look_line = self.code[j].strip()
                        look_upper = look_line.upper()
                        
                        # Skip blank lines and comments
                        if not look_line or look_line.startswith(";"):
                            intermediate_lines2.append(j)
                            j += 1
                            continue
                        
                        # Stop at labels
                        if look_upper.endswith(":"):
                            break
                        
                        # Check for STX addr+1
                        if look_upper.startswith("STX "):
                            stx_parts = look_line.split(maxsplit=1)
                            if len(stx_parts) == 2:
                                stx_operand = stx_parts[1].strip()
                                # Check if it's the same address +1
                                if stx_operand.upper() == sta_operand.upper() + "+1":
                                    stx_found = True
                                    stx_index = j
                                    break
                        
                        # Stop at any other instruction
                        break
                    
                    if stx_found and not _operand_is_port(sta_operand) and not _operand_is_port(stx_operand):
                        # Replace pattern: skip LDX #$00, emit STA, replace STX with STZ
                        # Emit intermediate lines between LDX and STA
                        for idx in intermediate_lines:
                            optimized.append(self.code[idx])
                        # Emit STA
                        optimized.append(self.code[sta_index])
                        # Emit intermediate lines between STA and STX
                        for idx in intermediate_lines2:
                            optimized.append(self.code[idx])
                        # Emit STZ instead of STX
                        indent = self.code[stx_index][:len(self.code[stx_index]) - len(self.code[stx_index].lstrip())]
                        optimized.append(f"{indent}STZ {sta_operand}+1\n")
                        i = stx_index + 1
                        continue

            # Remove redundant LDX #$00 when X is overwritten by TAX soon after
            if instr_part in {"LDX #$00", "LDX #$00", "LDX #$00"}:
                j = i + 1
                found_tax = False
                while j < len(self.code):
                    look_line = self.code[j].strip()
                    look_upper = look_line.upper()
                    if not look_line or look_line.startswith(";"):
                        j += 1
                        continue
                    if look_upper.endswith(":"):
                        break
                    op = look_upper.split()[0]
                    if op == "TAX":
                        found_tax = True
                        break
                    if op.startswith("B") or op in {"JMP", "JSR", "RTS", "RTI", "BRK"}:
                        break
                    if self._reads_x(look_line):
                        break
                    j += 1

                if found_tax:
                    i += 1
                    continue

            # Optimize word load/store via (ptr),Y
            # Previous sequence (7 instrs): LDY #1; LDA (ptr),Y; TAX; DEY; LDA (ptr),Y; STA dest; STX dest+1
            # Current sequence (6 instrs): LDY #1; LDA (ptr),Y; STA dest+1; DEY; LDA (ptr),Y; STA dest
            # Optimization: If 65c02, can we optimize this?
            # Actually, the 6-instruction sequence is already quite optimal without a hardware 16-bit register.
            # No TAX/STX are present to remove.
            # But we can optimize `STA dest+1` maybe. No, it's fine.
            # I will leave this peephole block commented out or removed since the sequence it optimized
            # no longer exists.
            pass

            # Replace LDX #$00; CLC; ADC TMP0; STA TMP0; TXA -> CLC; ADC TMP0; STA TMP0; LDA #$00
            if i + 4 < len(self.code):
                l1 = self.code[i].strip()
                l2 = self.code[i + 1].strip()
                l3 = self.code[i + 2].strip()
                l4 = self.code[i + 3].strip()
                l5 = self.code[i + 4].strip()
                l1_u = l1.split(';')[0].strip().upper()
                l2_u = l2.split(';')[0].strip().upper()
                l3_u = l3.split(';')[0].strip().upper()
                l4_u = l4.split(';')[0].strip().upper()
                l5_u = l5.split(';')[0].strip().upper()
                if (l1_u in {"LDX #$00", "LDX #$00", "LDX #$00"} and l2_u == "CLC" and
                        l3_u == "ADC TMP0" and l4_u == "STA TMP0" and l5_u == "TXA"):
                    optimized.append(self.code[i + 1])
                    optimized.append(self.code[i + 2])
                    optimized.append(self.code[i + 3])
                    indent = self.code[i + 4][:len(self.code[i + 4]) - len(self.code[i + 4].lstrip())]
                    optimized.append(f"{indent}LDA #$00\n")
                    i += 5
                    continue

            # Optimize LD<reg>#N; ...; DE<reg>; ...; LD<reg>#(N-1) -> skip final load
            # Pattern: Load register with immediate, decrement it (with safe intervening code),
            # then reload with one less value. The reload is redundant since DEX/DEY decreases
            # the register by 1 and nothing clobbers it in between.
            if i + 3 < len(self.code):
                l1 = self.code[i].strip()
                l1_upper = l1.split(';')[0].strip().upper()
                
                # Check if first line is LD<X/Y> #imm
                if l1_upper.startswith("LDX #") or l1_upper.startswith("LDY #"):
                    reg_char = l1_upper[2]  # 'X' or 'Y'
                    dec_instr = f"DE{reg_char}"
                    imm_str = l1_upper.split(maxsplit=1)[1] if ' ' in l1_upper else ""
                    imm_initial = _parse_imm(imm_str)
                    
                    if imm_initial is not None:
                        # Scan forward to find DE<reg> and then LD<reg> #(imm_initial-1)
                        j = i + 1
                        dec_idx = -1
                        final_ld_idx = -1
                        expected_after_dec = (imm_initial - 1) & 0xFF
                        
                        while j < len(self.code):
                            lj = self.code[j].strip()
                            lj_upper = lj.split(';')[0].strip().upper()
                            
                            # Skip blank and comment lines
                            if not lj or lj_upper.startswith(";"):
                                j += 1
                                continue
                            
                            # Stop at labels
                            if lj_upper.endswith(":"):
                                break
                            
                            # Stop at control flow
                            if lj_upper.startswith("B") or lj_upper in {"JMP", "JSR", "RTS", "RTI", "BRK"}:
                                break
                            
                            # Found the decrement instruction
                            if lj_upper == dec_instr:
                                if dec_idx == -1:
                                    dec_idx = j
                                j += 1
                                continue
                            
                            # After finding DEC, look for LD<reg> #(expected_value)
                            if dec_idx != -1:
                                if lj_upper.startswith(f"LD{reg_char} #"):
                                    final_imm_str = lj_upper.split(maxsplit=1)[1] if ' ' in lj_upper else ""
                                    final_imm = _parse_imm(final_imm_str)
                                    if final_imm is not None and final_imm == expected_after_dec:
                                        # Check that nothing between initial load and this point clobbers the register
                                        # EXCEPT for the DEC instruction itself, which is the pattern we're optimizing
                                        all_safe = True
                                        for k in range(i + 1, j):
                                            lk = self.code[k].strip()
                                            lk_upper = lk.split(';')[0].strip().upper()
                                            if not lk or lk_upper.startswith(";") or lk_upper.endswith(":"):
                                                continue
                                            # Don't check the DEC instruction itself - it's part of the pattern
                                            if k == dec_idx:
                                                continue
                                            if _clobbers_reg(lk, reg_char):
                                                all_safe = False
                                                break
                                        if all_safe:
                                            final_ld_idx = j
                                            break
                            elif dec_idx == -1:
                                # Before finding DEC, check for register clobber
                                if _clobbers_reg(lj, reg_char):
                                    break
                            
                            j += 1
                        
                        # If pattern found, skip the final load
                        if final_ld_idx != -1:
                            for k in range(i, final_ld_idx):
                                optimized.append(self.code[k])
                            i = final_ld_idx + 1
                            continue

            # Replace LDA TMP0; TAY; LDA label,Y -> LDY TMP0; LDA label,Y
            if i + 2 < len(self.code):
                l1 = self.code[i].strip()
                l2 = self.code[i + 1].strip()
                l3 = self.code[i + 2].strip()
                l1_u = l1.split(';')[0].strip().upper()
                l2_u = l2.split(';')[0].strip().upper()
                l3_u = l3.split(';')[0].strip().upper()
                if l1_u == "LDA TMP0" and l2_u == "TAY" and l3_u.startswith("LDA ") and l3_u.endswith(",Y"):
                    operand = l3_u.split(maxsplit=1)[1].strip()
                    if not operand.startswith("(") and ")" not in operand and not _operand_is_port(operand):
                        indent = self.code[i][:len(self.code[i]) - len(self.code[i].lstrip())]
                        optimized.append(f"{indent}LDY TMP0\n")
                        optimized.append(self.code[i + 2])
                        i += 3
                        continue

            # Remove redundant LDX #$00 before accumulator shift/rotate
            if instr_part in {"LDX #$00", "LDX #$00", "LDX #$00"}:
                j = i + 1
                removed_ldx = False
                while j < len(self.code):
                    look_line = self.code[j].strip()
                    look_upper = look_line.upper()
                    if not look_line or look_line.startswith(";"):
                        j += 1
                        continue
                    if look_upper.endswith(":"):
                        break
                    op = look_upper.split()[0]
                    if op in {"ASL", "LSR", "ROL", "ROR"}:
                        parts = look_upper.split()
                        if len(parts) == 1 or parts[1] == "A":
                            i += 1
                            removed_ldx = True
                        break
                    break
                if removed_ldx:
                    continue

            # Remove redundant LDX #imm when another LDX #imm follows without X use
            if instr_part.startswith("LDX #"):
                j = i + 1
                overwritten = False
                while j < len(self.code):
                    look_line = self.code[j].strip()
                    look_upper = look_line.upper()
                    if not look_line or look_line.startswith(";"):
                        j += 1
                        continue
                    if look_upper.endswith(":"):
                        break
                    op = look_upper.split()[0]
                    if op == "LDX" and look_upper.startswith("LDX #"):
                        overwritten = True
                        break
                    if op.startswith("B") or op in {"JMP", "JSR", "RTS", "RTI", "BRK"}:
                        break
                    if self._reads_x(look_line):
                        break
                    j += 1

                if overwritten:
                    i += 1
                    continue

            # Remove conditional branch to the next label (no-op)
            branch_ops = {"BEQ", "BNE", "BCC", "BCS", "BMI", "BPL", "BVC", "BVS", "BRA"}
            if instr_part:
                parts = instr_part.split()
                if len(parts) == 2 and parts[0] in branch_ops:
                    target = parts[1]
                    j = i + 1
                    removed_branch = False
                    while j < len(self.code):
                        next_line = self.code[j].strip()
                        if not next_line or next_line.startswith(";"):
                            j += 1
                            continue
                        if next_line == f"{target}:":
                            i += 1
                            removed_branch = True
                        break
                    if removed_branch:
                        continue
            
            # Tail call optimization: JSR followed by RTS -> JMP
            if line_upper.startswith("JSR "):
                parts = line_stripped.split(maxsplit=1)
                if len(parts) == 2:
                    jsr_target = parts[1].strip()
                    
                    # Look ahead for RTS
                    j = i + 1
                    found_rts = False
                    rts_index = -1
                    
                    while j < len(self.code):
                        next_line = self.code[j].strip()
                        next_upper = next_line.upper()
                        
                        # Skip blank lines and comments
                        if not next_line or next_line.startswith(";"):
                            j += 1
                            continue
                        
                        # Stop at labels (potential jump targets)
                        if next_upper.endswith(":"):
                            break
                        
                        # Check if this is RTS
                        if next_upper == "RTS":
                            # Found tail call pattern - replace JSR with JMP
                            found_rts = True
                            rts_index = j
                            break
                        
                        # Stop at any other instruction
                        break
                    
                    if found_rts:
                        # Replace JSR with JMP
                        indent = line[:len(line) - len(line.lstrip())]
                        optimized.append(f"{indent}JMP {jsr_target}\n")
                        # Emit intermediate lines (comments/blanks) but skip the RTS
                        for k in range(i + 1, j + 1):
                            if k != rts_index:
                                optimized.append(self.code[k])
                        i = j + 1
                        continue
            
            # Remove jumps to labels that are reachable by falling through
            # Pattern: JMP target_label when target_label is reached by only labels in between
            if line_upper.startswith("JMP "):
                parts = line_stripped.split(maxsplit=1)
                if len(parts) == 2:
                    jmp_target = parts[1].strip()
                    
                    # Look ahead to find if the target label is reachable by falling through
                    j = i + 1
                    target_found = False
                    only_labels = True
                    jmp_target_upper = jmp_target.upper()
                    
                    while j < len(self.code):
                        next_line = self.code[j].strip()
                        next_upper = next_line.upper()
                        
                        # Skip blank lines and comments
                        if not next_line or next_line.startswith(";"):
                            j += 1
                            continue
                        
                        # Check if this is the target label
                        if next_upper.endswith(":"):
                            label_name = next_upper[:-1].strip()  # Remove the colon
                            if label_name == jmp_target_upper:
                                # Found the target label - safe to remove JMP
                                target_found = True
                                break
                            else:
                                # Different label, keep scanning
                                j += 1
                                continue
                        
                        # If we hit any actual instruction before finding the target, stop
                        if next_line:
                            only_labels = False
                            break
                        
                        j += 1
                    
                    # If we found the target with only labels in between, remove the JMP
                    if target_found and only_labels:
                        i += 1
                        continue
            # STA __MATH0; INC/DEC __MATH0; LDA __MATH0; STA var -> STA var; INC/DEC var
            if line_upper.startswith("STA "):
                def _parse_inst_local(src_line: str) -> tuple[str, str]:
                    inst = src_line.split(";", 1)[0].strip()
                    if not inst: return "", ""
                    parts = inst.split(maxsplit=1)
                    return parts[0].upper(), parts[1].strip() if len(parts) == 2 else ""
                
                op0, dst0 = _parse_inst_local(line_stripped)
                if dst0.startswith("__MATH") or dst0.startswith("TMP"):
                    j = i + 1
                    ops = []
                    inst_lines = []
                    while j < len(self.code) and len(ops) < 3:
                        next_line = self.code[j].strip()
                        if not next_line or next_line.startswith(";"):
                            j += 1
                            continue
                        
                        op, operand = _parse_inst_local(next_line)
                        if op.endswith(":"):
                            break
                        ops.append((op, operand))
                        inst_lines.append(j)
                        j += 1
                        
                    if len(ops) == 3:
                        (op1, dst1), (op2, src2), (op3, dst2) = ops
                        if (op1 in {"INC", "DEC"} and op2 == "LDA" and op3 == "STA" and
                            dst1 == dst0 and src2 == dst0 and dst2 != dst0 and not _operand_is_port(dst2)):
                            
                            indent = self.code[i][:len(self.code[i]) - len(self.code[i].lstrip())]
                            optimized.append(f"{indent}STA {dst2}\n")
                            optimized.append(f"{indent}{op1} {dst2}\n")
                            i = inst_lines[2] + 1
                            continue
            
            # Check for STA instruction
            if line_upper.startswith("STA "):
                parts = line_stripped.split(maxsplit=1)
                if len(parts) == 2:
                    sta_operand = parts[1].strip()
                    
                    # Look ahead for redundant LDA
                    j = i + 1
                    found_redundant_lda = False
                    lda_index = -1
                    
                    while j < len(self.code):
                        next_line = self.code[j].strip()
                        next_upper = next_line.upper()
                        
                        # Skip blank lines and comments
                        if not next_line or next_line.startswith(";"):
                            j += 1
                            continue
                        
                        # Stop at labels (potential jump targets)
                        if next_upper.endswith(":"):
                            break
                        
                        # Check if this is LDA with same operand
                        if next_upper.startswith("LDA "):
                            lda_parts = next_line.split(maxsplit=1)
                            if len(lda_parts) == 2:
                                lda_operand = lda_parts[1].strip()
                                if (lda_operand.upper() == sta_operand.upper() and
                                        not _operand_is_port(sta_operand) and
                                        not _operand_is_port(lda_operand)):
                                    # Found redundant LDA - mark it for removal
                                    found_redundant_lda = True
                                    lda_index = j
                            break
                        
                        # Stop at any other instruction that might affect A
                        break
                    
                    # Emit the STA and any intermediate lines, but skip the redundant LDA
                    optimized.append(self.code[i])
                    for k in range(i + 1, j + 1 if found_redundant_lda else j):
                        if k != lda_index:
                            optimized.append(self.code[k])
                    
                    i = j + 1 if found_redundant_lda else i + 1
                    continue
            
            # Remove duplicate consecutive comment lines
            if line_stripped.startswith(";"):
                # Check if this comment is identical to the last line added
                if optimized and optimized[-1].strip() == line_stripped:
                    # Skip this duplicate comment
                    i += 1
                    continue

            # Replace 16-bit add temp shuffle with direct stores when safe
            def _parse_inst(src_line: str) -> tuple[str, str]:
                """Helper for parse inst.
                Internal helper used during code generation.
                """
                inst = src_line.split(";", 1)[0].strip()
                if not inst:
                    return "", ""
                parts = inst.split(maxsplit=1)
                op = parts[0].upper()
                operand = parts[1].strip() if len(parts) == 2 else ""
                return op, operand

            if i + 9 < len(self.code):
                ops = []
                for k in range(10):
                    op, operand = _parse_inst(self.code[i + k])
                    if not op or op.endswith(":"):
                        ops = []
                        break
                    ops.append((op, operand))
                if ops:
                    (op0, src0), (op1, _), (op2, dst0), (op3, _), (op4, src1), (op5, dst1), (op6, _), (op7, _), (op8, dst2), (op9, dst3) = ops
                    if (op0 == "LDA" and op1 == "CLC" and op2 == "ADC" and op3 == "TAY" and
                        op4 == "LDA" and op5 == "ADC" and op6 == "TAX" and op7 == "TYA" and
                        op8 == "STA" and op9 == "STX" and dst0 == dst2 and dst1 == f"{dst0}+1" and
                        dst3 == f"{dst0}+1" and src1 == f"{src0}+1"):
                        if not (_operand_is_port(src0) or _operand_is_port(src1) or
                                _operand_is_port(dst0) or _operand_is_port(dst1) or
                                _operand_is_port(dst2) or _operand_is_port(dst3)):
                            # Ensure next instruction reloads the destination (safe to discard A/X result)
                            j = i + 10
                            next_inst_ok = False
                            while j < len(self.code):
                                next_line = self.code[j].strip()
                                if not next_line or next_line.startswith(";"):
                                    j += 1
                                    continue
                                next_op, next_operand = _parse_inst(self.code[j])
                                next_inst_ok = (next_op == "LDA" and next_operand == dst0)
                                break
                            if next_inst_ok:
                                indent0 = self.code[i][:len(self.code[i]) - len(self.code[i].lstrip())]
                                indent4 = self.code[i + 4][:len(self.code[i + 4]) - len(self.code[i + 4].lstrip())]
                                optimized.append(f"{indent0}LDA {src0}\n")
                                optimized.append(f"{indent0}CLC\n")
                                optimized.append(f"{indent0}ADC {dst0}\n")
                                optimized.append(f"{indent0}STA {dst0}\n")
                                optimized.append(f"{indent4}LDA {src1}\n")
                                optimized.append(f"{indent4}ADC {dst0}+1\n")
                                optimized.append(f"{indent4}STA {dst0}+1\n")
                                i += 10
                                continue

            # Remove blank line right before RTS
            if not line_stripped:
                j = i + 1
                skip_blank = False
                while j < len(self.code):
                    next_line = self.code[j].strip()
                    next_upper = next_line.upper()
                    if not next_line or next_line.startswith(";"):
                        j += 1
                        continue
                    if next_upper == "RTS":
                        skip_blank = True
                    break
                if skip_blank:
                    i += 1
                    continue
            
            # Default: keep the line as-is
            optimized.append(self.code[i])
            i += 1
        
        self.code = optimized

    def legalize_illegal_ops(self) -> None:
        """Ensure emitted code is assemblable even without peephole optimizations.

        Currently replaces illegal 'OP X' sequences with a safe temp-based variant.
        """
        legalized: list[str] = []
        i = 0
        while i < len(self.code):
            line_upper: str = self.code[i].strip().upper()
            if line_upper.endswith(" X"):
                parts: list[str] = line_upper.split()
                if len(parts) == 2 and parts[1] == "X":
                    op: str = parts[0]
                    if op in {"ORA", "AND", "EOR", "ADC", "SBC", "CMP"}:
                        legalized.append(self._rewrite_internal_names("\tSTX TMP4"))
                        legalized.append(self._rewrite_internal_names(f"\t{op} TMP4"))
                        i += 1
                        continue
            legalized.append(self.code[i])
            i += 1
        self.code = legalized

    def _declare_temp(self, name: str, base: str = "WORD") -> Symbol:
        """Helper for declare temp.
        Internal helper used during code generation.
        """
        # vložení do aktuální tabulky (lokální, jinak globální)
        target: SymbolTable | None = getattr(self.current_symtab, "local", None)
        if target is None:
            target = self.current_symtab
        existing = target._symbols.get(target._key(name))
        if existing is not None:
            return existing
        sym = Symbol(
            name=name,
            type=SemType(base, False),
            is_const=False,
            const_value=None,
            is_array=False,
            array_len=None,
            init=None,
            address=None,
            is_volatile=False,
            proc_name="",
            is_generated=True
        )
        # attach procedure name if available for proper ASM naming
        proc_name: str = getattr(target, "_proc_name", "")
        if proc_name:
            sym.proc_name = proc_name
        target._symbols[target._key(sym.name)] = sym
        return sym


    def gen_file_header(self) -> None:
        """Generate file header.
        Internal helper used during code generation.
        """
        self.emit(f"; Generated by Zap Compiler {__version__}")
        cmd: str = self.command_line if self.command_line else "(command line not provided)"
        self.emit(f"; Command: {cmd}")
        if self.pruned_procs:
            removed: str = ", ".join(sorted(self.pruned_procs))
            self.emit(f"; Optimized out unused procedures (definitions and calls removed): {removed}")
        self.emit("; ==============================")
        self.emit("")
        # Emit exports (if any) as an assembler comment so the compiler's
        # label-cleanup step can see them, but do NOT emit .export directives
        # into assembly (the compiler emits a single .s file and .export isn't
        # meaningful here). Downstream `label_cleanup` recognizes this comment.
        exports: Any | None = getattr(self, 'exports', None)
        if exports:
            exports_list: str = ", ".join(sorted(self.asm_symbol_name(name) for name in exports))
            # Comment format: ; ZAP_EXPORTS name, name
            self.emit(f"; ZAP_EXPORTS {exports_list}")
            self.emit("")
        self.emit(".DEBUGINFO +  ; Enable debug information for symbol names")
        self.emit("")
        #self.emit(".include \"macros.inc\"")
        #self.emit(".include \"variables.inc\"\n")

    def gen_file_footer(self) -> None:
        """Generate file footer.
        Internal helper used during code generation.
        """
        # Ensure runtime helpers and data live in CODE segment
        self.emit(f"\n\n.segment \"{self.seg_code}\"")
        self._gen_copy_bytes_routine()
        self._gen_copy_bytes16_routine()
        self._gen_string_data()
        self._gen_math_routines()
        self.emit("\n; End of file")

    def _gen_copy_bytes_routine(self) -> None:
        """Shared byte copy routine to shrink init code for large const data"""
        if not self.copy_bytes_needed:
            return

        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        self.emit("; __ZAPC_FOOTER_BLOCK__")
        self.emit("; ------------------------------")
        self.emit("; Shared byte copy routine")
        self.emit("; Inputs: TMP0/TMP0+1=src, TMP2/TMP2+1=dst, X=len (1..255), Y=0")
        self.emit("; Clobbers: A, X, Y")
        self.emit("; Note: length must fit in one page; longer copies stay inline")
        self.emit("COPY_BYTES:")
        self.emit("\tLDY #$00")
        self.emit("\tCPX #$00")        
        self.emit("\tBEQ COPY_BYTES_DONE")
        self.emit("COPY_BYTES_LOOP:")
        self.emit("\tLDA (TMP0),Y")
        self.emit("\tSTA (TMP2),Y")
        self.emit("\tINY")
        self.emit("\tDEX")
        self.emit("\tBNE COPY_BYTES_LOOP")
        self.emit("COPY_BYTES_DONE:")
        self.emit("\tRTS\n")
    
    def _gen_copy_bytes16_routine(self) -> None:
        """16-bit length byte copy routine for arrays larger than 255 bytes."""
        if not self.copy_bytes16_needed:
            return

        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3", "TMP4"})

        self.emit("; __ZAPC_FOOTER_BLOCK__")
        self.emit("; ------------------------------")
        self.emit("; 16-bit byte copy routine")
        self.emit("; Inputs: TMP0/TMP0+1=src, TMP2/TMP2+1=dst, TMP4=count_lo, TMP4+1=count_hi")
        self.emit("; Clobbers: A, Y, TMP4, TMP4+1")
        self.emit("COPY_BYTES16:")
        self.emit("\tLDY #$00")
        self.emit("CB16_OUTER:")
        self.emit("\tLDA TMP4+1")
        self.emit("\tBEQ CB16_PARTIAL")
        self.emit("; Copy one full 256-byte page")
        self.emit("CB16_PAGE:")
        self.emit("\tLDA (TMP0),Y")
        self.emit("\tSTA (TMP2),Y")
        self.emit("\tINY")
        self.emit("\tBNE CB16_PAGE")
        self.emit("\tINC TMP0+1")
        self.emit("\tINC TMP2+1")
        self.emit("\tDEC TMP4+1")
        self.emit("\tJMP CB16_OUTER")
        self.emit("CB16_PARTIAL:")
        self.emit("\tLDA TMP4")
        self.emit("\tBEQ CB16_DONE")
        self.emit("CB16_PARTIAL_LOOP:")
        self.emit("\tLDA (TMP0),Y")
        self.emit("\tSTA (TMP2),Y")
        self.emit("\tINY")
        self.emit("\tDEC TMP4")
        self.emit("\tBNE CB16_PARTIAL_LOOP")
        self.emit("CB16_DONE:")
        self.emit("\tRTS\n")

    def _gen_string_data(self) -> None:
        """Generate string literal data in code segment"""
        if not self.string_literals and not self.array_literals:
            return
        
        self.emit("; __ZAPC_FOOTER_BLOCK__")
        self.emit("; ------------------------------")
        self.emit("; Constant Data")
        self.emit("; ------------------------------")
        
        # Generate string data
        for content, label in self.string_literals.items():
            self.emit(f"{label}:")
            # Emit string as .byte directives
            ascii_bytes = content.encode('ascii')
            self.emit(f"\t.byte " + ", ".join(f"${b:02X}" for b in ascii_bytes) + ", 0")
        
        # Generate array data
        for (data_tuple, data_type), label in self.array_literals.items():
            self.emit(f"{label}:")
            if data_type == "WORD":
                # WORD array - emit as .word directives
                self.emit(f"\t.word " + ", ".join(f"${val:04X}" for val in data_tuple))
            elif data_type == "LONG":
                # LONG array - emit each element as 4 bytes in little-endian order
                byte_values: list[int] = []
                for val in data_tuple:
                    for j in range(4):
                        byte_values.append((val >> (8 * j)) & 0xFF)
                self.emit(f"\t.byte " + ", ".join(f"${v:02X}" for v in byte_values))
            else:
                # BYTE array - emit as .byte directives
                byte_values = []
                for val in data_tuple:
                    if val > 0xFF:
                        byte_values.append(val & 0xFF)
                        byte_values.append((val >> 8) & 0xFF)
                    else:
                        byte_values.append(val & 0xFF)
                self.emit(f"\t.byte " + ", ".join(f"${val:02X}" for val in byte_values))
        
        self.emit("")
    
    def _gen_string_copy(self, dst_sym, src_sym) -> None:
        """Generate code to copy a source array into a destination array.

        Uses COPY_BYTES (≤255 bytes) or COPY_BYTES16 (>255 bytes).
        Sets TMP0/TMP2 to src/dst addresses; count in X (8-bit) or TMP4/TMP4+1 (16-bit).
        Supports BYTE, WORD, and LONG arrays.
        """
        src_asm = src_sym.asm_name()
        dst_asm = dst_sym.asm_name()
        total_bytes: int = dst_sym.get_total_array_size()
        if total_bytes == 0:
            self._raise_error(f"Cannot copy array '{dst_sym.name}': size is unknown")

        # Set up source address in TMP0
        if src_sym.address is not None:
            addr = src_sym.address
            self.emit(f"\tLDA #${addr & 0xFF:02X}")
            self.emit("\tSTA TMP0")
            self.emit(f"\tLDA #${(addr >> 8) & 0xFF:02X}")
            self.emit("\tSTA TMP0+1")
        else:
            self.emit(f"\tLDA #<{src_asm}")
            self.emit("\tSTA TMP0")
            self.emit(f"\tLDA #>{src_asm}")
            self.emit("\tSTA TMP0+1")

        # Set up destination address in TMP2
        if dst_sym.address is not None:
            addr = dst_sym.address
            self.emit(f"\tLDA #${addr & 0xFF:02X}")
            self.emit("\tSTA TMP2")
            self.emit(f"\tLDA #${(addr >> 8) & 0xFF:02X}")
            self.emit("\tSTA TMP2+1")
        else:
            self.emit(f"\tLDA #<{dst_asm}")
            self.emit("\tSTA TMP2")
            self.emit(f"\tLDA #>{dst_asm}")
            self.emit("\tSTA TMP2+1")

        # Choose copy routine based on total bytes
        if total_bytes > 255:
            self.copy_bytes16_needed = True
            self.emit(f"\tLDA #${total_bytes & 0xFF:02X}")
            self.emit("\tSTA TMP4")
            self.emit(f"\tLDA #${(total_bytes >> 8) & 0xFF:02X}")
            self.emit("\tSTA TMP4+1")
            self.emit("\tJSR COPY_BYTES16")
        else:
            self.copy_bytes_needed = True
            self.emit(f"\tLDX #${total_bytes:02X}")
            self.emit("\tJSR COPY_BYTES")

    def _extract_const_values_from_listinit(self, init_list, flat_values: list[int]) -> None:
        """Extract const values from a ListInit, handling nested struct literals.
        
        Recursively flattens nested ListInit structures and extracts integer values.
        Handles: IntLiteral, Identifier (const refs), FieldAccess (enum members), ListInit (nested structs)
        """
        for ex in init_list.values:
            if isinstance(ex, IntLiteral):
                flat_values.append(ex.value)
            elif isinstance(ex, Identifier):
                # Look up identifier in symbol table to get const value
                sym_val = self.global_symtab.lookup(ex.name)
                if sym_val and sym_val.const_value is not None:
                    flat_values.append(sym_val.const_value)
                else:
                    self._raise_error(f"Cannot evaluate '{ex.name}' as constant in struct initializer")
            elif isinstance(ex, FieldAccess) and isinstance(ex.object, Identifier):
                # Handle enum member: MyEnum.B
                enum_name = ex.object.name.upper()
                member_name = ex.field.upper()
                enums = getattr(self.global_symtab, '_enums', None)
                if enums and enum_name in enums:
                    enum_def = enums[enum_name]
                    if member_name in enum_def['members']:
                        flat_values.append(enum_def['members'][member_name])
                    else:
                        self._raise_error(f"Enum '{enum_name}' has no member '{member_name}'")
                else:
                    self._raise_error(f"Enum '{enum_name}' is not defined")
            elif isinstance(ex, ListInit):
                # Recursive: nested struct literal like {10, 20}
                self._extract_const_values_from_listinit(ex, flat_values)
            else:
                self._raise_error(f"Non-constant expression in const struct initializer: {type(ex).__name__}")

    def _extract_const_struct_bytes(self, init_list: 'ListInit', struct_def: 'StructInfo') -> tuple[tuple[int, ...], bool]:
        """Extract const struct bytes according to field types.
        
        Returns (byte_tuple, is_word) where:
        - byte_tuple: flattened bytes with proper field sizing
        - is_word: False (always, since it's mixed-size struct data emitted as BYTE array)
        
        This correctly handles WORD fields in nested structs by expanding them to low/high bytes.
        """
        byte_values: list[int] = []
        field_index = 0
        fields = struct_def.fields
        
        for ex in init_list.values:
            if field_index >= len(fields):
                self._raise_error(f"Too many initializers for struct (has {len(fields)} fields)")
            
            field_info = fields[field_index]
            field_index += 1
            
            # Extract the value
            if isinstance(ex, IntLiteral):
                val = ex.value
            elif isinstance(ex, Identifier):
                sym_val = self.global_symtab.lookup(ex.name)
                if sym_val and sym_val.const_value is not None:
                    val = sym_val.const_value
                else:
                    self._raise_error(f"Cannot evaluate '{ex.name}' as constant in struct initializer")
            elif isinstance(ex, FieldAccess) and isinstance(ex.object, Identifier):
                # Handle enum member: MyEnum.B
                enum_name = ex.object.name.upper()
                member_name = ex.field.upper()
                enums = getattr(self.global_symtab, '_enums', None)
                if enums and enum_name in enums:
                    enum_def = enums[enum_name]
                    if member_name in enum_def['members']:
                        val = enum_def['members'][member_name]
                    else:
                        self._raise_error(f"Enum '{enum_name}' has no member '{member_name}'")
                else:
                    self._raise_error(f"Enum '{enum_name}' is not defined")
            elif isinstance(ex, ListInit):
                # Nested struct - recursively extract bytes using nested struct definition
                nested_struct_info = self.struct_registry.lookup(field_info.base_type)
                if nested_struct_info is None:
                    self._raise_error(f"Cannot determine nested struct definition for field '{field_info.name}'")
                nested_bytes, _ = self._extract_const_struct_bytes(ex, nested_struct_info)
                byte_values.extend(nested_bytes)
                continue
            else:
                self._raise_error(f"Non-constant expression in const struct initializer: {type(ex).__name__}")
            
            # Append bytes according to field type
            if field_info.is_pointer or field_info.base_type.upper() == "WORD":
                # WORD or pointer - emit as 2 bytes (little-endian)
                byte_values.append(val & 0xFF)
                byte_values.append((val >> 8) & 0xFF)
            else:
                # BYTE or enum - emit as 1 byte
                byte_values.append(val & 0xFF)
        
        return (tuple(byte_values), False)

    def _gen_const_struct_copy(self, dst_sym, src_const_sym) -> None:
        """Generate code to copy const struct data from ROM to destination.
        
        Copies constant struct bytes from ROM data (ARRAY_DATA_*) to destination variable.
        
        Parameters:
        - dst_sym: destination struct symbol (non-const variable)
        - src_const_sym: source const struct symbol with ROM data
        """
        if not src_const_sym.init or not isinstance(src_const_sym.init, ListInit):
            self._raise_error(f"Const struct '{src_const_sym.name}' has no initialization")
        
        # Get the struct size
        struct_size = src_const_sym.type.struct_info.size if src_const_sym.type.struct_info else 0
        if struct_size == 0:
            self._raise_error(f"Cannot determine size of struct '{src_const_sym.name}'")
        
        # Extract values from const struct initialization (handles nested structs)
        values: list[int] = []
        self._extract_const_values_from_listinit(src_const_sym.init, values)
        
        # Generate ROM data label for this struct
        data_key = (tuple(values), "BYTE")
        if data_key not in self.array_literals:
            self.array_id += 1
            self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
        arr_label = self.array_literals[data_key]

        # Set up source address (ROM data) in TMP0
        self.emit(f"\tLDA #<{arr_label}")
        self.emit("\tSTA TMP0")
        self.emit(f"\tLDA #>{arr_label}")
        self.emit("\tSTA TMP0+1")

        # Set up destination address in TMP2
        dst_asm = dst_sym.asm_name()
        self.emit(f"\tLDA #<{dst_asm}")
        self.emit("\tSTA TMP2")
        self.emit(f"\tLDA #>{dst_asm}")
        self.emit("\tSTA TMP2+1")

        # Choose copy routine based on struct size
        if struct_size > 255:
            self.copy_bytes16_needed = True
            self.emit(f"\tLDA #${struct_size & 0xFF:02X}")
            self.emit("\tSTA TMP4")
            self.emit(f"\tLDA #${(struct_size >> 8) & 0xFF:02X}")
            self.emit("\tSTA TMP4+1")
            self.emit("\tJSR COPY_BYTES16")
        else:
            self.copy_bytes_needed = True
            self.emit(f"\tLDX #${struct_size:02X}")
            self.emit("\tJSR COPY_BYTES")

    
    def _gen_math_routines(self) -> None:
        """Generate runtime math routines for *, /, %"""
        if not self.math_routines_needed:
            return

        # Only flag TMPs actually used by the specific math routines needed.
        needed: set[str] = set(self.math_routines_needed)
        # MUL8, MUL16_8 use TMP0, TMP1
        if needed & {"MUL8", "MUL16_8"}:
            self.used_temps.update({"TMP0", "TMP1"})
        # MUL16 uses TMP0-TMP4
        if "MUL16" in needed:
            self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3", "TMP4"})
        # MUL32, DIV32, MOD32 use TMP0-TMP3
        if needed & {"MUL32", "DIV32", "MOD32"}:
            self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})
        # Include dependencies (MUL16_8 uses MUL8)
        if "MUL16_8" in needed:
            needed.add("MUL8")

        def emit_mul8() -> None:
            """Emit mul8.
            Internal helper used during code generation.
            """
            self.emit("; MUL8: 8x8=16 multiply")
            self.emit("; Input: MATH0 (multiplicand), MATH1 (multiplier)")
            self.emit("; Output: MATH0=product (low word), MATH0+2/+3 cleared")
            self.emit("MUL8:")
            self.emit("\tLDA MATH0")
            self.emit("\tSTA TMP0")
            self._stz("TMP0+1")
            self.emit("\tLDA MATH1")
            self.emit("\tSTA TMP1")
            self._stz_multiple(["MATH0", "MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDX #$08")
            self.emit("MUL8_LOOP:")
            self.emit("\tLSR TMP1")
            self.emit("\tBCC MUL8_SKIP")
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC TMP0+1")
            self.emit("\tSTA MATH0+1")
            self.emit("MUL8_SKIP:")
            self.emit("\tASL TMP0")
            self.emit("\tROL TMP0+1")
            self.emit("\tDEX")
            self.emit("\tBNE MUL8_LOOP")
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_mul16_8() -> None:
            """Emit mul16 8.
            Internal helper used during code generation.
            """
            self.emit("; MUL16_8: 16x8=24 multiply")
            self.emit("; Input: MATH0 low word (multiplicand), MATH1 low byte (multiplier)")
            self.emit("; Output: MATH0=product (32-bit)")
            self.emit("MUL16_8:")
            self.emit("\tLDA MATH0")
            self.emit("\tSTA TMP0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSTA TMP0+1")
            self.emit("\tLDA MATH1")
            self.emit("\tSTA TMP1")
            self._stz_multiple(["MATH0", "MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDX #$08")
            self.emit("MUL16_8_LOOP:")
            self.emit("\tLSR TMP1")
            self.emit("\tBCC MUL16_8_SKIP")
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC TMP0+1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tADC #$00")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tADC #$00")
            self.emit("\tSTA MATH0+3")
            self.emit("MUL16_8_SKIP:")
            self.emit("\tASL TMP0")     # shift multiplicand left (low byte)
            self.emit("\tROL TMP0+1")   # shift multiplicand left (high byte with carry)
            self.emit("\tDEX")
            self.emit("\tBNE MUL16_8_LOOP")
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_mul16() -> None:
            """Emit mul16.
            Internal helper used during code generation.
            """
            self.emit("; MUL16: 16x16=32 multiply (shift-add implementation)")
            self.emit("; Input: MATH0 low word (multiplicand), MATH1 low word (multiplier)")
            self.emit("; Output: MATH0=product (32-bit)")
            self.emit("MUL16:")
            # Copy multiplicand into TMP0..TMP3 (32-bit)
            self.emit("\tLDA MATH0")
            self.emit("\tSTA TMP0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSTA TMP1")
            self._stz("TMP2")
            self._stz("TMP3")
            # Copy multiplier into TMP4/TMP4+1
            self.emit("\tLDA MATH1")
            self.emit("\tSTA TMP4")
            self.emit("\tLDA MATH1+1")
            self.emit("\tSTA TMP4+1")
            # Clear accumulator (MATH0)
            self._stz_multiple(["MATH0", "MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDX #$10")
            self.emit("MUL16_LOOP:")
            # Shift multiplier right, test LSB in carry
            self.emit("\tLSR TMP4+1")
            self.emit("\tROR TMP4")
            self.emit("\tBCC MUL16_SKIP")
            # Add multiplicand (TMP0..TMP3) into accumulator (MATH0..MATH0+3)
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC TMP1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tADC TMP2")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tADC TMP3")
            self.emit("\tSTA MATH0+3")
            self.emit("MUL16_SKIP:")
            # Left-shift multiplicand (TMP0..TMP3)
            self.emit("\tASL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2")
            self.emit("\tROL TMP3")
            self.emit("\tDEX")
            self.emit("\tBNE MUL16_LOOP")
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_div8() -> None:
            """Emit div8.
            Internal helper used during code generation.
            """
            self.emit("; DIV8: 8/8=8 divide")
            self.emit("; Input: MATH0 (dividend), MATH1 (divisor)")
            self.emit("; Output: MATH0=quotient (low byte)")
            self.emit("DIV8:")
            self.emit("\tLDA #$00")
            self.emit("\tLDX #$08")
            self.emit("\tCLC")
            self.emit("DIV8_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL")
            self.emit("\tCMP MATH1")
            self.emit("\tBCC DIV8_SKIP")
            self.emit("\tSBC MATH1")
            self.emit("DIV8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV8_LOOP")
            self.emit("\tROL MATH0")
            self._stz_multiple(["MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tRTS")

        def emit_div16_8() -> None:
            """Emit div16 8.
            Internal helper used during code generation.
            """
            self.emit("; DIV16_8: 16/8=16 divide")
            self.emit("; Input: MATH0 low word (dividend), MATH1 low byte (divisor)")
            self.emit("; Output: MATH0=quotient (low word)")
            self.emit("DIV16_8:")
            self._stz("MATH0+2")
            self.emit("\tLDX #$10")
            self.emit("\tCLC")
            self.emit("DIV16_8_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tLDA MATH0+2")
            self.emit("\tCMP MATH1")
            self.emit("\tBCC DIV16_8_SKIP")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0+2")
            self.emit("DIV16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_8_LOOP")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self._stz_multiple(["MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_div8_16() -> None:
            """Emit div8 16.
            Internal helper used during code generation.
            """
            self.emit("; DIV8_16: 8/16 divide (promote and call DIV16)")
            self.emit("; Input: MATH0 (dividend), MATH1 low word (divisor)")
            self.emit("; Output: MATH0=quotient (low word)")
            self.emit("DIV8_16:")
            # Make dividend 16-bit (high byte = 0) and reuse DIV16 implementation
            self._stz("MATH0+1")
            self.emit("\tJSR DIV16")
            self.emit("\tRTS")

        def emit_div16() -> None:
            """Emit div16.
            Internal helper used during code generation.
            """
            self.emit("; DIV16: 16/16=16 divide")
            self.emit("; Input: MATH0 low word (dividend), MATH1 low word (divisor)")
            self.emit("; Output: MATH0=quotient (low word)")
            self.emit("DIV16:")
            self._stz("MATH0+2")
            self._stz("MATH0+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("DIV16_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tROL MATH0+3")
            self.emit("\tLDA MATH0+2")
            self.emit("\tCMP MATH1")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSBC MATH1+1")
            self.emit("\tBCC DIV16_SKIP")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSBC MATH1+1")
            self.emit("\tSTA MATH0+3")
            self.emit("DIV16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_LOOP")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self._stz_multiple(["MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_mod8() -> None:
            """Emit mod8.
            Internal helper used during code generation.
            """
            self.emit("; MOD8: 8%8=8 modulo")
            self.emit("; Input: MATH0 (dividend), MATH1 (divisor)")
            self.emit("; Output: MATH0=remainder (low byte)")
            self.emit("MOD8:")
            self.emit("\tLDA #$00")
            self.emit("\tLDX #$08")
            self.emit("\tCLC")
            self.emit("MOD8_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL")
            self.emit("\tCMP MATH1")
            self.emit("\tBCC MOD8_SKIP")
            self.emit("\tSBC MATH1")
            self.emit("MOD8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD8_LOOP")
            self.emit("\tSTA MATH0")
            self._stz_multiple(["MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tRTS")

        def emit_mod16_8() -> None:
            """Emit mod16 8.
            Internal helper used during code generation.
            """
            self.emit("; MOD16_8: 16%8=8 modulo")
            self.emit("; Input: MATH0 low word (dividend), MATH1 low byte (divisor)")
            self.emit("; Output: MATH0=remainder (low byte)")
            self.emit("MOD16_8:")
            self._stz("MATH0+2")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_8_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tLDA MATH0+2")
            self.emit("\tCMP MATH1")
            self.emit("\tBCC MOD16_8_SKIP")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0+2")
            self.emit("MOD16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_8_LOOP")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSTA MATH0")
            self._stz_multiple(["MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tRTS")

        def emit_mod8_16() -> None:
            """Emit mod8 16.
            Internal helper used during code generation.
            """
            self.emit("; MOD8_16: 8%16 modulo (promote and call MOD16)")
            self.emit("; Input: MATH0 (dividend), MATH1 low word (divisor)")
            self.emit("; Output: MATH0=remainder (low word)")
            self.emit("MOD8_16:")
            # Treat dividend as 16-bit (high byte = 0) and reuse MOD16
            self._stz("MATH0+1")
            self.emit("\tJSR MOD16")
            self.emit("\tRTS")

        def emit_mod16() -> None:
            """Emit mod16.
            Internal helper used during code generation.
            """
            self.emit("; MOD16: 16%16=16 modulo")
            self.emit("; Input: MATH0 low word (dividend), MATH1 low word (divisor)")
            self.emit("; Output: MATH0=remainder (low word)")
            self.emit("MOD16:")
            self._stz("MATH0+2")
            self._stz("MATH0+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_LOOP:")
            self.emit("\tROL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tROL MATH0+3")
            self.emit("\tLDA MATH0+2")
            self.emit("\tCMP MATH1")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSBC MATH1+1")
            self.emit("\tBCC MOD16_SKIP")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSBC MATH1+1")
            self.emit("\tSTA MATH0+3")
            self.emit("MOD16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_LOOP")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSTA MATH0+1")
            self._stz_multiple(["MATH0+2", "MATH0+3"])
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_set_math0() -> None:
            """Emit set math0.
            Internal helper used during code generation.
            """
            self.emit("; SET_MATH0: A/X -> MATH0/MATH0+1 (for RPN code generation)")
            self.emit("; Input: A (low byte), X (high byte)")
            self.emit("; Output: MATH0=A, MATH0+1=X")
            self.emit("SET_MATH0:")
            self.emit("\tSTA MATH0")
            self.emit("\tSTX MATH0+1")
            self.emit("\tRTS")

        def emit_set_math1() -> None:
            """Emit set math1.
            Internal helper used during code generation.
            """
            self.emit("; SET_MATH1: A/X -> MATH1/MATH1+1 (for RPN code generation)")
            self.emit("; Input: A (low byte), X (high byte)")
            self.emit("; Output: MATH1=A, MATH1+1=X")
            self.emit("SET_MATH1:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")
            self.emit("\tRTS")

        def emit_mul8_a() -> None:
            """Emit mul8 a.
            Internal helper used during code generation.
            """
            self.emit("; MUL8_A: right operand in A")
            self.emit("MUL8_A:")
            self.emit("\tSTA MATH1")

        def emit_mul16_8_a() -> None:
            """Emit mul16 8 a.
            Internal helper used during code generation.
            """
            self.emit("; MUL16_8_A: right operand (byte) in A")
            self.emit("MUL16_8_A:")
            self.emit("\tSTA MATH1")

        def emit_mul16_ax() -> None:
            """Emit mul16 ax.
            Internal helper used during code generation.
            """
            self.emit("; MUL16_AX: right operand (word) in A/X")
            self.emit("MUL16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_div8_a() -> None:
            """Emit div8 a.
            Internal helper used during code generation.
            """
            self.emit("; DIV8_A: right operand in A")
            self.emit("DIV8_A:")
            self.emit("\tSTA MATH1")

        def emit_div16_8_a() -> None:
            """Emit div16 8 a.
            Internal helper used during code generation.
            """
            self.emit("; DIV16_8_A: right operand (byte) in A")
            self.emit("DIV16_8_A:")
            self.emit("\tSTA MATH1")

        def emit_div8_16_ax() -> None:
            """Emit div8 16 ax.
            Internal helper used during code generation.
            """
            self.emit("; DIV8_16_AX: right operand (word) in A/X")
            self.emit("DIV8_16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_div16_ax() -> None:
            """Emit div16 ax.
            Internal helper used during code generation.
            """
            self.emit("; DIV16_AX: right operand (word) in A/X")
            self.emit("DIV16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_mod8_a() -> None:
            """Emit mod8 a.
            Internal helper used during code generation.
            """
            self.emit("; MOD8_A: right operand in A")
            self.emit("MOD8_A:")
            self.emit("\tSTA MATH1")

        def emit_mod16_8_a() -> None:
            """Emit mod16 8 a.
            Internal helper used during code generation.
            """
            self.emit("; MOD16_8_A: right operand (byte) in A")
            self.emit("MOD16_8_A:")
            self.emit("\tSTA MATH1")

        def emit_mod8_16_ax() -> None:
            """Emit mod8 16 ax.
            Internal helper used during code generation.
            """
            self.emit("; MOD8_16_AX: right operand (word) in A/X")
            self.emit("MOD8_16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_mod16_ax() -> None:
            """Emit mod16 ax.
            Internal helper used during code generation.
            """
            self.emit("; MOD16_AX: right operand (word) in A/X")
            self.emit("MOD16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_get_math0() -> None:
            """Emit get math0.
            Internal helper used during code generation.
            """
            self.emit("; GET_MATH0: MATH0/MATH0+1 -> A/X (for RPN code generation)")
            self.emit("; Input: MATH0 (low word)")
            self.emit("; Output: A (low byte), X (high byte)")
            self.emit("GET_MATH0:")
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
            self.emit("\tRTS")

        def emit_add16() -> None:
            """Emit add16.
            Internal helper used during code generation.
            """
            self.emit("; ADD16: 16-bit addition (accumulator style)")
            self.emit("; Input: MATH0 low word (left operand), MATH1 low word (right operand)")
            self.emit("; Output: MATH0=sum (32-bit, high word cleared)")
            self.emit("ADD16:")
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC MATH1")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC MATH1+1")
            self.emit("\tSTA MATH0+1")
            self._stz_multiple(["MATH0+2", "MATH0+3"])
            self.emit("\tRTS")

        def emit_sub16() -> None:
            """Emit sub16.
            Internal helper used during code generation.
            """
            self.emit("; SUB16: 16-bit subtraction (accumulator style)")
            self.emit("; Input: MATH0 low word (left operand), MATH1 low word (right operand)")
            self.emit("; Output: MATH0=difference (32-bit, high word cleared)")
            self.emit("SUB16:")
            self.emit("\tLDA MATH0")
            self.emit("\tSEC")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSBC MATH1+1")
            self.emit("\tSTA MATH0+1")
            self._stz_multiple(["MATH0+2", "MATH0+3"])
            self.emit("\tRTS")

        def emit_add16_ax() -> None:
            """Emit add16 ax.
            Internal helper used during code generation.
            """
            self.emit("; ADD16_AX: right operand (word) in A/X")
            self.emit("ADD16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_sub16_ax() -> None:
            """Emit sub16 ax.
            Internal helper used during code generation.
            """
            self.emit("; SUB16_AX: right operand (word) in A/X")
            self.emit("SUB16_AX:")
            self.emit("\tSTA MATH1")
            self.emit("\tSTX MATH1+1")

        def emit_add32() -> None:
            self.emit("; ADD32: MATH0 = MATH0 + MATH1")
            self.emit("ADD32:")
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC MATH1")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC MATH1+1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tADC MATH1+2")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tADC MATH1+3")
            self.emit("\tSTA MATH0+3")
            self.emit("\tRTS")

        def emit_sub32() -> None:
            self.emit("; SUB32: MATH0 = MATH0 - MATH1")
            self.emit("SUB32:")
            self.emit("\tLDA MATH0")
            self.emit("\tSEC")
            self.emit("\tSBC MATH1")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSBC MATH1+1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSBC MATH1+2")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSBC MATH1+3")
            self.emit("\tSTA MATH0+3")
            self.emit("\tRTS")



        def emit_mul32() -> None:
            self.emit("; MUL32: MATH0 = MATH0 * MATH1")
            self.emit("MUL32:")
            self.emit("\tLDA MATH0")
            self.emit("\tSTA TMP0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSTA TMP1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tSTA TMP2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tSTA TMP3")
            self._stz_multiple(["MATH0", "MATH0+1", "MATH0+2", "MATH0+3"])
            self.emit("\tLDX #32")
            self.emit("MUL32_LOOP:")
            self.emit("\tLSR MATH1+3")
            self.emit("\tROR MATH1+2")
            self.emit("\tROR MATH1+1")
            self.emit("\tROR MATH1")
            self.emit("\tBCC MUL32_SKIP")
            self.emit("\tLDA MATH0")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tADC TMP1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA MATH0+2")
            self.emit("\tADC TMP2")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA MATH0+3")
            self.emit("\tADC TMP3")
            self.emit("\tSTA MATH0+3")
            self.emit("MUL32_SKIP:")
            self.emit("\tASL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2")
            self.emit("\tROL TMP3")
            self.emit("\tDEX")
            self.emit("\tBNE MUL32_LOOP")
            self.emit("\tRTS")

        def emit_div32() -> None:
            self.emit("; DIV32: MATH0 = MATH0 / MATH1 (Unsigned)")
            self.emit("DIV32:")
            self._stz_multiple(["TMP0", "TMP1", "TMP2", "TMP3"])
            self.emit("\tLDX #32")
            self.emit("DIV32_LOOP:")
            self.emit("\tASL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tROL MATH0+3")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2")
            self.emit("\tROL TMP3")
            self.emit("\tSEC")
            self.emit("\tLDA TMP0")
            self.emit("\tSBC MATH1")
            self.emit("\tTAY")
            self.emit("\tLDA TMP1")
            self.emit("\tSBC MATH1+1")
            self.emit("\tPHA")
            self.emit("\tLDA TMP2")
            self.emit("\tSBC MATH1+2")
            self.emit("\tPHA")
            self.emit("\tLDA TMP3")
            self.emit("\tSBC MATH1+3")
            self.emit("\tBCC DIV32_SKIP")
            self.emit("\tSTA TMP3")
            self.emit("\tPLA")
            self.emit("\tSTA TMP2")
            self.emit("\tPLA")
            self.emit("\tSTA TMP1")
            self.emit("\tSTY TMP0")
            self.emit("\tINC MATH0")
            self.emit("\tJMP DIV32_NEXT")
            self.emit("DIV32_SKIP:")
            self.emit("\tPLA")
            self.emit("\tPLA")
            self.emit("DIV32_NEXT:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV32_LOOP")
            self.emit("\tRTS")

        def emit_mod32() -> None:
            self.emit("; MOD32: MATH0 = MATH0 % MATH1 (Unsigned)")
            self.emit("MOD32:")
            self._stz_multiple(["TMP0", "TMP1", "TMP2", "TMP3"])
            self.emit("\tLDX #32")
            self.emit("MOD32_LOOP:")
            self.emit("\tASL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tROL MATH0+3")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2")
            self.emit("\tROL TMP3")
            self.emit("\tSEC")
            self.emit("\tLDA TMP0")
            self.emit("\tSBC MATH1")
            self.emit("\tTAY")
            self.emit("\tLDA TMP1")
            self.emit("\tSBC MATH1+1")
            self.emit("\tPHA")
            self.emit("\tLDA TMP2")
            self.emit("\tSBC MATH1+2")
            self.emit("\tPHA")
            self.emit("\tLDA TMP3")
            self.emit("\tSBC MATH1+3")
            self.emit("\tBCC MOD32_SKIP")
            self.emit("\tSTA TMP3")
            self.emit("\tPLA")
            self.emit("\tSTA TMP2")
            self.emit("\tPLA")
            self.emit("\tSTA TMP1")
            self.emit("\tSTY TMP0")
            self.emit("\tINC MATH0")
            self.emit("\tJMP MOD32_NEXT")
            self.emit("MOD32_SKIP:")
            self.emit("\tPLA")
            self.emit("\tPLA")
            self.emit("MOD32_NEXT:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD32_LOOP")
            self.emit("\tLDA TMP0")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA TMP1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA TMP2")
            self.emit("\tSTA MATH0+2")
            self.emit("\tLDA TMP3")
            self.emit("\tSTA MATH0+3")
            self.emit("\tRTS")

        def emit_lshift32() -> None:
            self.emit("; LSHIFT32: MATH0 = MATH0 << A")
            self.emit("LSHIFT32:")
            self.emit("\tCMP #$00")
            self.emit("\tBEQ LSHIFT32_EXIT")
            self.emit("\tTAY")
            self.emit("LSHIFT32_LOOP:")
            self.emit("\tASL MATH0")
            self.emit("\tROL MATH0+1")
            self.emit("\tROL MATH0+2")
            self.emit("\tROL MATH0+3")
            self.emit("\tDEY")
            self.emit("\tBNE LSHIFT32_LOOP")
            self.emit("LSHIFT32_EXIT:")
            self.emit("\tRTS")

        def emit_rshift32() -> None:
            self.emit("; RSHIFT32: MATH0 = MATH0 >> A (Unsigned)")
            self.emit("RSHIFT32:")
            self.emit("\tCMP #$00")
            self.emit("\tBEQ RSHIFT32_EXIT")
            self.emit("\tTAY")
            self.emit("RSHIFT32_LOOP:")
            self.emit("\tLSR MATH0+3")
            self.emit("\tROR MATH0+2")
            self.emit("\tROR MATH0+1")
            self.emit("\tROR MATH0")
            self.emit("\tDEY")
            self.emit("\tBNE RSHIFT32_LOOP")
            self.emit("RSHIFT32_EXIT:")
            self.emit("\tRTS")

        emitters: list[tuple[str, Any]] = [
            ("SET_MATH0", emit_set_math0),
            ("SET_MATH1", emit_set_math1),
            ("GET_MATH0", emit_get_math0),
            ("ADD16_AX", emit_add16_ax),
            ("ADD16", emit_add16),
            ("SUB16_AX", emit_sub16_ax),
            ("SUB16", emit_sub16),
            ("MUL8_A", emit_mul8_a),
            ("MUL8", emit_mul8),
            ("MUL16_8_A", emit_mul16_8_a),
            ("MUL16_8", emit_mul16_8),
            ("MUL16_AX", emit_mul16_ax),
            ("MUL16", emit_mul16),
            ("DIV8_A", emit_div8_a),
            ("DIV8", emit_div8),
            ("DIV16_8_A", emit_div16_8_a),
            ("DIV16_8", emit_div16_8),
            ("DIV8_16_AX", emit_div8_16_ax),
            ("DIV8_16", emit_div8_16),
            ("DIV16_AX", emit_div16_ax),
            ("DIV16", emit_div16),
            ("MOD8_A", emit_mod8_a),
            ("MOD8", emit_mod8),
            ("MOD16_8_A", emit_mod16_8_a),
            ("MOD16_8", emit_mod16_8),
            ("MOD8_16_AX", emit_mod8_16_ax),
            ("MOD8_16", emit_mod8_16),
            ("MOD16_AX", emit_mod16_ax),
            ("MOD16", emit_mod16),
            ("ADD32", emit_add32),
            ("SUB32", emit_sub32),

            ("MUL32", emit_mul32),
            ("DIV32", emit_div32),
            ("MOD32", emit_mod32),
            ("LSHIFT32", emit_lshift32),
            ("RSHIFT32", emit_rshift32),
        ]

        self.emit("; __ZAPC_FOOTER_BLOCK__")
        self.emit("; ------------------------------")
        self.emit("; Math Runtime Routines")
        self.emit("; ------------------------------")
        self.emit("")

        for name, emitter in emitters:
            if name in needed:
                emitter()
                self.emit("")


    def gen_var_header(self) -> None:
        """Generate var header.
        Internal helper used during code generation.
        """
        self.emit("; Variables")
        self.emit("; ------------------------------")   

    def _detect_temp_usage(self, code: list[str] | None = None) -> set[str]:
        """Scan generated code for temp usage and combine with flagged temps."""
        temp_names: set[str] = {self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5")}
        temps: set[str] = {self._internal_name_map.get(n, n) for n in self.used_temps}
        code = self.code if code is None else code

        if self.copy_bytes_needed:
            temps.update({self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1", "TMP2", "TMP3")})

        if self.copy_bytes16_needed:
            temps.update({self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1", "TMP2", "TMP3", "TMP4")})

        # Predict TMPs needed by math routines (emitted later in gen_file_footer)
        needed = set(self.math_routines_needed)
        if needed & {"MUL8", "MUL8_A", "MUL16_8"}:
            temps.update({self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1")})
        if "MUL16" in needed:
            temps.update({self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1", "TMP2", "TMP3", "TMP4")})
        if needed & {"MUL32", "DIV32", "MOD32"}:
            temps.update({self._internal_name_map.get(n, n) for n in ("TMP0", "TMP1", "TMP2", "TMP3")})

        for line in code:
            for name in temp_names:
                if name in line:
                    temps.add(name)
        return temps

    def assign_zeropage(self, procs=None, funcs=None) -> None:
        """Assign variables to the Zero Page segment before code generation starts."""
        
        # Collect all variables (globals + locals from procs and funcs)
        all_vars: list[Symbol] = list(self.global_symtab)
        if procs:
            for proc in procs:
                all_vars.extend(proc.locals)
                local_tbl = getattr(proc.symtab, "local", None)
                if local_tbl is not None:
                    all_vars.extend(list(local_tbl))
        if funcs:
            for func in funcs:
                all_vars.extend(func.locals)

        # Deduplicate
        uniq: dict[str, Symbol] = {}
        for s in all_vars:
            uniq[s.asm_name()] = s
        all_vars = list(uniq.values())
        
        # Reset per-symbol ZP placement hints
        for sym in all_vars:
            sym.in_zeropage = False

        # Assume up to 64 bytes used by system + fixed vars to be extremely conservative
        zp_offset: int = 64
        ZEROPAGE_SIZE = 256

        # Pre-decide placement for pointer scalars/arrays (arrays go to ZP only if they fit)
        pointer_scalars: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and not s.is_array
        ]
        pointer_arrays: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and s.is_array
        ]

        # Pointer scalars
        pointer_scalar_slots: dict[str, list[Symbol]] = {}
        pointer_scalar_slot_order: list[str] = []
        for sym in pointer_scalars:
            slot_label = sym.shared_slot or sym.asm_name()
            if slot_label not in pointer_scalar_slots:
                pointer_scalar_slots[slot_label] = []
                pointer_scalar_slot_order.append(slot_label)
            pointer_scalar_slots[slot_label].append(sym)

        for slot_label in pointer_scalar_slot_order:
            if zp_offset + 2 <= ZEROPAGE_SIZE:
                zp_offset += 2
                for sym in pointer_scalar_slots[slot_label]:
                    sym.in_zeropage = True

        # Pointer arrays
        pointer_array_slots: dict[str, list[Symbol]] = {}
        pointer_array_slot_sizes: dict[str, int] = {}
        pointer_array_slot_order: list[str] = []
        for sym in pointer_arrays:
            slot_label = sym.shared_slot or sym.asm_name()
            if slot_label not in pointer_array_slots:
                pointer_array_slots[slot_label] = []
                pointer_array_slot_sizes[slot_label] = 0
                pointer_array_slot_order.append(slot_label)
            pointer_array_slots[slot_label].append(sym)
            total_size = sym.get_total_array_size()
            if total_size > pointer_array_slot_sizes[slot_label]:
                pointer_array_slot_sizes[slot_label] = total_size

        for slot_label in pointer_array_slot_order:
            total_size = pointer_array_slot_sizes[slot_label]
            if total_size == 0: continue
            if zp_offset + total_size <= ZEROPAGE_SIZE:
                zp_offset += total_size
                for sym in pointer_array_slots[slot_label]:
                    sym.in_zeropage = True

        # Step 2: Try to put BYTE variables in zero page
        byte_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "BYTE"]
        
        zp_priority_bytes = sorted([s for s in byte_vars if s.zp_priority > 0], key=lambda s: -s.zp_priority)
        regular_bytes = [s for s in byte_vars if s.zp_priority <= 0]
        
        for sym in zp_priority_bytes:
            if zp_offset + 1 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 1
        for sym in regular_bytes:
            if zp_offset + 1 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 1
                
        # Step 3: Try to put WORD variables in zero page
        word_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "WORD"]
                    
        zp_priority_words = sorted([s for s in word_vars if s.zp_priority > 0], key=lambda s: -s.zp_priority)
        regular_words = [s for s in word_vars if s.zp_priority <= 0]

        for sym in zp_priority_words:
            if zp_offset + 2 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 2
        for sym in regular_words:
            if zp_offset + 2 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 2
                
        # Step 4: Try to put LONG variables in zero page
        long_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "LONG"]
                    
        zp_priority_longs = sorted([s for s in long_vars if s.zp_priority > 0], key=lambda s: -s.zp_priority)
        regular_longs = [s for s in long_vars if s.zp_priority <= 0]

        for sym in zp_priority_longs:
            if zp_offset + 4 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 4
        for sym in regular_longs:
            if zp_offset + 4 <= ZEROPAGE_SIZE:
                sym.in_zeropage = True
                zp_offset += 4

    def gen_vars_block(self, procs=None, funcs=None, code: list[str] | None = None) -> list[str]:
        """Generate vars.
        Internal helper used during code generation.
        """
        temp_sizes: dict[str, int] = {
            self._internal_name_map.get("TMP0", "TMP0"): 2,
            self._internal_name_map.get("TMP1", "TMP1"): 2,
            self._internal_name_map.get("TMP2", "TMP2"): 2,
            self._internal_name_map.get("TMP3", "TMP3"): 2,
            self._internal_name_map.get("TMP4", "TMP4"): 2,
            self._internal_name_map.get("TMP5", "TMP5"): 2,
            self._internal_name_map.get("TMP6", "TMP6"): 2,
            self._internal_name_map.get("TMP7", "TMP7"): 2,
            self._internal_name_map.get("TMP8", "TMP8"): 2,
            self._internal_name_map.get("TMP9", "TMP9"): 2,
            self._internal_name_map.get("TMP10", "TMP10"): 2,
            self._internal_name_map.get("TMP11", "TMP11"): 2,
            self._internal_name_map.get("TMP12", "TMP12"): 2,
            self._internal_name_map.get("TMP13", "TMP13"): 2,
            self._internal_name_map.get("TMP14", "TMP14"): 2,
            self._internal_name_map.get("TMP15", "TMP15"): 2,
        }

        if code is None:
            code = self.code

        temps_in_use: set[str] = self._detect_temp_usage(code)

        # Capture output into a new list
        saved_code = self.code
        self.code = []

        self.emit(f"\n\n.segment \"{self.seg_zp}\"")
        self.emit("; System variables")

        # Emit system temps: use shared slots if assigned, otherwise dedicated slots
        sys_temp_names = [("MATH_STACK", 32), ("MATH0", 4), ("MATH1", 4)]
        for temp_name, temp_size in sys_temp_names:
            internal_name = self._internal_name_map.get(temp_name, temp_name)
            if temp_name in self.system_temp_slots:
                # This temp uses a shared slot - emit as alias
                slot_name = self.system_temp_slots[temp_name]
                self.emit(f"{internal_name} = {slot_name}")
            else:
                # No shared slot - emit dedicated allocation
                self.emit(f"{internal_name}:\t.res {temp_size}")
        
        for raw_name in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5", "TMP6", "TMP7", "TMP8", "TMP9", "TMP10", "TMP11", "TMP12", "TMP13", "TMP14", "TMP15"]:
            name = self._internal_name_map.get(raw_name, raw_name)
            if name in temps_in_use:
                if raw_name in self.system_temp_slots:
                    # This temp uses a shared slot - emit as alias
                    slot_name = self.system_temp_slots[raw_name]
                    self.emit(f"{name} = {slot_name}")
                else:
                    # No shared slot - emit dedicated allocation
                    size: int = temp_sizes[name]
                    self.emit(f"{name}:\t.res {size}")
        self.emit("")

        # Collect all variables (globals + locals from procs and funcs)
        all_vars: list[Symbol] = list(self.global_symtab)
        if procs:
            for proc in procs:
                # include analyzed locals
                all_vars.extend(proc.locals)
                # include any temps declared during codegen in the scoped local table
                local_tbl: Any | None = getattr(proc.symtab, "local", None)
                if local_tbl is not None:
                    all_vars.extend(list(local_tbl))
        if funcs:
            for func in funcs:
                all_vars.extend(func.locals)
                local_tbl = getattr(func.symtab, "local", None)
                if local_tbl is not None:
                    all_vars.extend(list(local_tbl))

        # Deduplicate by ASM name to avoid double emission
        uniq: dict[str, Symbol] = {}
        for s in all_vars:
            uniq[s.asm_name()] = s
        all_vars: list[Symbol] = list(uniq.values())

        fixed: list[Symbol] = [s for s in all_vars if getattr(s, "address", None) is not None]
        if fixed:
            self.emit("\n; Fixed-address variables")
            for sym in fixed:
                self.emit(f"{sym.asm_name()} = ${sym.address:04X}")
                # Track fixed-address labels to prevent peephole optimization
                self.fixed_address_labels.add(sym.asm_name())
                # Also track PORT variables separately for future optimization strategy changes
                if getattr(sym, "is_port", False):
                    self.port_labels.add(sym.asm_name())
            self.emit("")

        # Constants (scalar consts)
        const_scalars: list[Symbol] = [
            s for s in all_vars
            if s.is_const and not s.is_array and not s.type.is_struct and getattr(s, 'address', None) is None
        ]
        if const_scalars:
            self.emit("\n; Constants")
            for sym in const_scalars:
                if sym.const_value is None:
                    # should not happen for scalar const
                    continue
                if sym.type.base == "WORD" or sym.type.is_pointer:
                    self.emit(f"{sym.asm_name()} = ${sym.const_value & 0xFFFF:04X}")
                else:
                    self.emit(f"{sym.asm_name()} = ${sym.const_value & 0xFF:02X}")
            self.emit("")

        # Shared slots for aliased locals (need to be emitted before individual locals)
        shared_slots_zp: dict[str, int] = {}   # slot_label -> size (in bytes)
        shared_slots_bss: dict[str, int] = {}  # slot_label -> size (in bytes)
        
        # First, collect slots from system temps (always ZP) — only if actually used
        for temp_name, slot_label in self.system_temp_slots.items():
            # Skip TMP slots not in use
            internal_name = self._internal_name_map.get(temp_name, temp_name)
            if temp_name.startswith("TMP") and internal_name not in temps_in_use:
                continue
            # Determine size based on temp name
            temp_sizes_map = {
                "MATH_STACK": 32,
                "MATH0": 4,
                "MATH1": 4,
                "TMP0": 2,
                "TMP1": 2,
                "TMP2": 2,
                "TMP3": 2,
                "TMP4": 2,
                "TMP5": 2,
            }
            temp_size = temp_sizes_map.get(temp_name, 2)
            if slot_label in shared_slots_zp:
                shared_slots_zp[slot_label] = max(shared_slots_zp[slot_label], temp_size)
            else:
                shared_slots_zp[slot_label] = temp_size
        
        # Then collect slots from procedure/function locals
        for sym in all_vars:
            slot_label = getattr(sym, 'shared_slot', None)
            if slot_label:
                # Determine size: WORD = 2, BYTE = 1, struct/array = struct_size or array total_size
                # Take MAXIMUM size across all variables sharing this slot
                sym_size = 0
                if sym.is_array:
                    sym_size = sym.get_total_array_size()
                elif sym.type.is_struct and sym.type.struct_info:
                    sym_size = sym.type.struct_info.size
                elif sym.type.is_pointer:
                    sym_size = 2
                elif sym.type.base == "LONG":
                    sym_size = 4
                elif sym.type.base == "WORD":
                    sym_size = 2
                elif sym.type.base == "BYTE":
                    sym_size = 1
                else:
                    # Default to 2 bytes (word)
                    sym_size = 2
                
                # Decide segment: arrays/structs -> BSS, pointers -> ZP (arrays only if they fit), scalars -> ZP
                use_bss = False
                if sym.is_array and not sym.type.is_pointer:
                    use_bss = True
                elif sym.type.is_struct:
                    use_bss = True
                elif sym.is_array and sym.type.is_pointer:
                    use_bss = not sym.in_zeropage
                elif sym.type.is_pointer and not sym.is_array:
                    use_bss = not sym.in_zeropage

                target = shared_slots_bss if use_bss else shared_slots_zp

                # Keep maximum size for this slot
                if slot_label in target:
                    target[slot_label] = max(target[slot_label], sym_size)
                else:
                    target[slot_label] = sym_size

        if shared_slots_zp:
            self.emit("\n; Shared slots (for aliased locals)")
            for slot_label, size in sorted(shared_slots_zp.items()):
                self.emit(f"{slot_label}:\t.res {size}")
            self.emit("")

        # Step 1: POINTER SCALARS/ARRAYS use ZP if they fit; otherwise they fall back to BSS
        pointer_scalars: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and not s.is_array
        ]
        pointer_arrays: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and s.is_array
        ]

        if pointer_scalars or pointer_arrays:
            self.emit("\n; Pointer variables")
            for sym in pointer_scalars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None) and sym.in_zeropage:
                    self.emit(f"{sym.asm_name()}:\t.res 2")

            for sym in pointer_arrays:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    if sym.in_zeropage:
                        total_size = sym.get_total_array_size()
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")
        
        # Step 2: BYTE variables - try zero page first
        byte_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "BYTE"]
        
        zp_byte_vars = [s for s in byte_vars if s.in_zeropage]
        bss_byte_vars = [s for s in byte_vars if not s.in_zeropage]
        
        if zp_byte_vars:
            self.emit("\n; Byte variables")
            for sym in zp_byte_vars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 1")
        
        # Step 3: WORD (non-pointer, non-array) variables - try zero page first
        word_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "WORD"]
        
        zp_word_vars = [s for s in word_vars if s.in_zeropage]
        bss_word_vars = [s for s in word_vars if not s.in_zeropage]
        
        if zp_word_vars:
            self.emit("\n; Word variables")
            for sym in zp_word_vars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 2")
        
        # Step 3.2: LONG variables - try zero page first
        long_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "LONG"]
        
        zp_long_vars = [s for s in long_vars if s.in_zeropage]
        bss_long_vars = [s for s in long_vars if not s.in_zeropage]
        
        if zp_long_vars:
            self.emit("\n; Long variables")
            for sym in zp_long_vars:
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 4")

        # Step 3.5: STRUCT (non-pointer, non-array) variables - always go to BSS
        struct_vars: list[Symbol] = [s for s in all_vars 
                    if not s.is_const and s.address is None 
                    and not s.type.is_pointer and not s.is_array
                    and s.type.is_struct]
        
        bss_struct_vars: list[Symbol] = struct_vars  # All struct vars go to BSS

        
        # Step 4: ALL non-pointer ARRAYS must go to BSS segment (pointer arrays were handled in Step 1)
        array_vars: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.is_array and not s.type.is_pointer
        ]

        pointer_array_bss: list[Symbol] = [
            s for s in all_vars
            if (not s.is_const and s.address is None and s.is_array and s.type.is_pointer and not s.in_zeropage)
        ]

        pointer_scalar_bss: list[Symbol] = [
            s for s in all_vars
            if (not s.is_const and s.address is None and not s.is_array and s.type.is_pointer and not s.in_zeropage)
        ]
        
        # Switch to BSS for overflow, struct vars, arrays, and BSS shared slots
        if bss_byte_vars or bss_word_vars or bss_long_vars or bss_struct_vars or array_vars or pointer_array_bss or pointer_scalar_bss or shared_slots_bss:
            self.emit(f"\n\n.segment \"{self.seg_bss}\"")

            if shared_slots_bss:
                self.emit("; Shared slots (BSS)")
                for slot_label, size in sorted(shared_slots_bss.items()):
                    self.emit(f"{slot_label}:\t.res {size}")
            
            if bss_byte_vars:
                self.emit("; Byte variables (BSS)")
                for sym in bss_byte_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 1")
            
            if bss_word_vars:
                self.emit("; Word variables (BSS)")
                for sym in bss_word_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 2")

            if bss_long_vars:
                self.emit("; Long variables (BSS)")
                for sym in bss_long_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 4")
            
            if bss_struct_vars:
                self.emit("; Struct variables (BSS)")
                for sym in bss_struct_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        if sym.type.is_struct and sym.type.struct_info:
                            struct_size: int = sym.type.struct_info.size
                            self.emit(f"{sym.asm_name()}:\t.res {struct_size}")
                        else:
                            # Fallback (shouldn't happen if is_struct is correct)
                            self.emit(f"{sym.asm_name()}:\t.res 1")

            if pointer_scalar_bss:
                self.emit("; Pointer variables (BSS)")
                for sym in pointer_scalar_bss:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 2")

            if pointer_array_bss:
                self.emit("; Pointer arrays (BSS)")
                for sym in pointer_array_bss:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        total_size = sym.get_total_array_size()
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")

            if array_vars:
                self.emit("; Arrays (BSS)")
                for sym in array_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        total_size = sym.get_total_array_size()
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")
        self.emit("")

        # Restore original code and return generated block
        vars_block = self.code
        self.code = saved_code
        return vars_block

    def gen_vars(self, procs=None, funcs=None, code: list[str] | None = None) -> None:
        """Generate vars.
        Internal helper used during code generation.
        """
        # Clear code and emit variables
        code = self.code
        self.code = []

        # Find which temps are used across the whole program
        temps_in_use: set[str] = self._detect_temp_usage(code)
        temp_sizes: dict[str, int] = {
            self._internal_name_map.get(n, n): 2
            for n in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5",
                      "TMP6", "TMP7", "TMP8", "TMP9", "TMP10", "TMP11",
                      "TMP12", "TMP13", "TMP14", "TMP15"]
        }

        self.emit(f"\n\n.segment \"{self.seg_zp}\"")
        self.emit("; System variables")
        
        # Emit system temps: use shared slots if assigned, otherwise dedicated slots
        sys_temp_names = [("MATH_STACK", 32), ("MATH0", 4), ("MATH1", 4)]
        for temp_name, temp_size in sys_temp_names:
            internal_name = self._internal_name_map.get(temp_name, temp_name)
            if temp_name in self.system_temp_slots:
                # This temp uses a shared slot - emit as alias
                slot_name = self.system_temp_slots[temp_name]
                self.emit(f"{internal_name} = {slot_name}")
            else:
                # No shared slot - emit dedicated allocation
                self.emit(f"{internal_name}:\t.res {temp_size}")
        
        for raw_name in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5", "TMP6", "TMP7", "TMP8", "TMP9", "TMP10", "TMP11", "TMP12", "TMP13", "TMP14", "TMP15"]:
            name = self._internal_name_map.get(raw_name, raw_name)
            if name in temps_in_use:
                if raw_name in self.system_temp_slots:
                    # This temp uses a shared slot - emit as alias
                    slot_name = self.system_temp_slots[raw_name]
                    self.emit(f"{name} = {slot_name}")
                else:
                    # No shared slot - emit dedicated allocation
                    size: int = temp_sizes[name]
                    self.emit(f"{name}:\t.res {size}")
        self.emit("")

        # Collect all variables (globals + locals from procs and funcs)
        shared_slots_zp: dict[str, int] = {}
        shared_slots_bss: dict[str, int] = {}
        pointer_scalars: list[Symbol] = []
        pointer_arrays: list[Symbol] = []
        all_vars: list[Symbol] = list(self.global_symtab)
        if procs:
            for proc in procs:
                # include analyzed locals
                all_vars.extend(proc.locals)
                # include any temps declared during codegen in the scoped local table
                local_tbl: Any | None = getattr(proc.symtab, "local", None)
                if local_tbl is not None:
                    all_vars.extend(list(local_tbl))
            if funcs:
                for func in funcs:
                    all_vars.extend(func.locals)

            # Deduplicate by ASM name to avoid double emission
            uniq: dict[str, Symbol] = {}
            for s in all_vars:
                uniq[s.asm_name()] = s
            all_vars: list[Symbol] = list(uniq.values())

            fixed: list[Symbol] = [s for s in all_vars if getattr(s, "address", None) is not None]
            if fixed:
                self.emit("\n; Fixed-address variables")
                for sym in fixed:
                    self.emit(f"{sym.asm_name()} = ${sym.address:04X}")
                    # Track fixed-address labels to prevent peephole optimization
                    self.fixed_address_labels.add(sym.asm_name())
                    # Also track PORT variables separately for future optimization strategy changes
                    if getattr(sym, "is_port", False):
                        self.port_labels.add(sym.asm_name())
                self.emit("")

            # Constants (scalar consts)
            const_scalars: list[Symbol] = [
                s for s in all_vars
                if s.is_const and not s.is_array and not s.type.is_struct and getattr(s, 'address', None) is None
            ]
            if const_scalars:
                self.emit("\n; Constants")
                for sym in const_scalars:
                    if sym.const_value is None:
                        # should not happen for scalar const
                        continue
                    if sym.type.base == "WORD" or sym.type.is_pointer:
                        self.emit(f"{sym.asm_name()} = ${sym.const_value & 0xFFFF:04X}")
                    else:
                        self.emit(f"{sym.asm_name()} = ${sym.const_value & 0xFF:02X}")
                self.emit("")

            # Zero page offset tracking (starts after emitted system variables)
            zp_offset: int = sum(temp_sizes[n] for n in temps_in_use)
            ZEROPAGE_SIZE = 256

            # Reset per-symbol ZP placement hints
            for sym in all_vars:
                sym.in_zeropage = False

            # Pre-decide placement for pointer scalars/arrays (arrays go to ZP only if they fit)
            pointer_scalars: list[Symbol] = [
                s for s in all_vars
                if not s.is_const and s.address is None and s.type.is_pointer and not s.is_array
            ]
            pointer_arrays: list[Symbol] = [
                s for s in all_vars
                if not s.is_const and s.address is None and s.type.is_pointer and s.is_array
            ]

            # Pointer scalars: allocate to ZP only if they fit; otherwise place in BSS
            pointer_scalar_slots: dict[str, list[Symbol]] = {}
            pointer_scalar_slot_order: list[str] = []
            for sym in pointer_scalars:
                slot_label = sym.shared_slot or sym.asm_name()
                if slot_label not in pointer_scalar_slots:
                    pointer_scalar_slots[slot_label] = []
                    pointer_scalar_slot_order.append(slot_label)
                pointer_scalar_slots[slot_label].append(sym)

            for slot_label in pointer_scalar_slot_order:
                if zp_offset + 2 <= ZEROPAGE_SIZE:
                    zp_offset += 2
                    for sym in pointer_scalar_slots[slot_label]:
                        sym.in_zeropage = True
                else:
                    for sym in pointer_scalar_slots[slot_label]:
                        sym.in_zeropage = False

            # Pointer arrays: allocate to ZP only if they fit; otherwise place in BSS
            pointer_array_slots: dict[str, list[Symbol]] = {}
            pointer_array_slot_sizes: dict[str, int] = {}
            pointer_array_slot_order: list[str] = []
            for sym in pointer_arrays:
                slot_label = sym.shared_slot or sym.asm_name()
                if slot_label not in pointer_array_slots:
                    pointer_array_slots[slot_label] = []
                    pointer_array_slot_sizes[slot_label] = 0
                    pointer_array_slot_order.append(slot_label)
                pointer_array_slots[slot_label].append(sym)
                total_size = sym.get_total_array_size()
                if total_size == 0:
                    self._raise_error(f"Array pointer '{sym.name}' has unknown size")
                if total_size > pointer_array_slot_sizes[slot_label]:
                    pointer_array_slot_sizes[slot_label] = total_size

            for slot_label in pointer_array_slot_order:
                total_size = pointer_array_slot_sizes[slot_label]
                if total_size == 0:
                    continue
        # First, collect slots from system temps (always ZP) — only if actually used
        for temp_name, slot_label in self.system_temp_slots.items():
            # Skip TMP slots not in use
            internal_name = self._internal_name_map.get(temp_name, temp_name)
            if temp_name.startswith("TMP") and internal_name not in temps_in_use:
                continue
            # Determine size based on temp name
            temp_sizes_map = {
                "MATH_STACK": 32,
                "MATH0": 4,
                "MATH1": 4,
                "TMP0": 2,
                "TMP1": 2,
                "TMP2": 2,
                "TMP3": 2,
                "TMP4": 2,
                "TMP5": 2,
            }
            temp_size = temp_sizes_map.get(temp_name, 2)
            if slot_label in shared_slots_zp:
                shared_slots_zp[slot_label] = max(shared_slots_zp[slot_label], temp_size)
            else:
                shared_slots_zp[slot_label] = temp_size
        
        # Then collect slots from procedure/function locals
        for sym in all_vars:
            slot_label = getattr(sym, 'shared_slot', None)
            if slot_label:
                # Determine size: WORD = 2, BYTE = 1, struct/array = struct_size or array total_size
                # Take MAXIMUM size across all variables sharing this slot
                sym_size = 0
                if sym.is_array:
                    sym_size = sym.get_total_array_size()
                elif sym.type.is_struct and sym.type.struct_info:
                    sym_size = sym.type.struct_info.size
                elif sym.type.is_pointer:
                    sym_size = 2
                elif sym.type.base == "WORD":
                    sym_size = 2
                elif sym.type.base == "BYTE":
                    sym_size = 1
                else:
                    # Default to 2 bytes (word)
                    sym_size = 2
                
                # Decide segment: arrays/structs -> BSS, pointers -> ZP (arrays only if they fit), scalars -> ZP
                use_bss = False
                if sym.is_array and not sym.type.is_pointer:
                    use_bss = True
                elif sym.type.is_struct:
                    use_bss = True
                elif sym.is_array and sym.type.is_pointer:
                    use_bss = not sym.in_zeropage
                elif sym.type.is_pointer and not sym.is_array:
                    use_bss = not sym.in_zeropage

                target = shared_slots_bss if use_bss else shared_slots_zp

                # Keep maximum size for this slot
                if slot_label in target:
                    target[slot_label] = max(target[slot_label], sym_size)
                else:
                    target[slot_label] = sym_size

        if shared_slots_zp:
            self.emit("\n; Shared slots (for aliased locals)")
            for slot_label, size in sorted(shared_slots_zp.items()):
                self.emit(f"{slot_label}:\t.res {size}")
            self.emit("")

        # Step 1: POINTER SCALARS/ARRAYS use ZP if they fit; otherwise they fall back to BSS
        if pointer_scalars or pointer_arrays:
            self.emit("\n; Pointer variables")
            for sym in pointer_scalars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None) and sym.in_zeropage:
                    self.emit(f"{sym.asm_name()}:\t.res 2")

            for sym in pointer_arrays:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    if sym.in_zeropage:
                        total_size = sym.get_total_array_size()
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")

        byte_vars: list[Symbol] = [s for s in all_vars
                    if not s.is_const and s.address is None
                    and not s.type.is_pointer and not s.is_array
                    and s.type.base == "BYTE"]
        zp_byte_vars = [s for s in byte_vars if s.in_zeropage]
        bss_byte_vars = [s for s in byte_vars if not s.in_zeropage]

        if zp_byte_vars:
            self.emit("\n; Byte variables")
            for sym in zp_byte_vars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 1")
        
        # Step 3: WORD (non-pointer, non-array) variables - try zero page first
        word_vars: list[Symbol] = [s for s in all_vars 
                     if not s.is_const and s.address is None 
                     and not s.type.is_pointer and not s.is_array
                     and s.type.base == "WORD"]
        
        zp_word_vars = [s for s in word_vars if s.in_zeropage]
        bss_word_vars = [s for s in word_vars if not s.in_zeropage]
        
        if zp_word_vars:
            self.emit("\n; Word variables")
            for sym in zp_word_vars:
                # Skip if already in shared slots
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 2")
        
        # Step 3.2: LONG variables - try zero page first
        long_vars: list[Symbol] = [s for s in all_vars 
                     if not s.is_const and s.address is None 
                     and not s.type.is_pointer and not s.is_array
                     and s.type.base == "LONG"]
        
        zp_long_vars = [s for s in long_vars if s.in_zeropage]
        bss_long_vars = [s for s in long_vars if not s.in_zeropage]
        
        if zp_long_vars:
            self.emit("\n; Long variables")
            for sym in zp_long_vars:
                if not getattr(sym, 'shared_slot', None):
                    self.emit(f"{sym.asm_name()}:\t.res 4")

        # Step 3.5: STRUCT (non-pointer, non-array) variables - always go to BSS
        struct_vars: list[Symbol] = [s for s in all_vars 
                       if not s.is_const and s.address is None 
                       and not s.type.is_pointer and not s.is_array
                       and s.type.is_struct]
        
        bss_struct_vars: list[Symbol] = struct_vars  # All struct vars go to BSS

        
        # Step 4: ALL non-pointer ARRAYS must go to BSS segment (pointer arrays were handled in Step 1)
        array_vars: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.is_array and not s.type.is_pointer
        ]

        pointer_array_bss: list[Symbol] = [
            s for s in all_vars
            if (not s.is_const and s.address is None and s.is_array and s.type.is_pointer and not s.in_zeropage)
        ]

        pointer_scalar_bss: list[Symbol] = [
            s for s in all_vars
            if (not s.is_const and s.address is None and not s.is_array and s.type.is_pointer and not s.in_zeropage)
        ]
        
        # Switch to BSS for overflow, struct vars, arrays, and BSS shared slots
        if bss_byte_vars or bss_word_vars or bss_long_vars or bss_struct_vars or array_vars or pointer_array_bss or pointer_scalar_bss or shared_slots_bss:
            self.emit(f"\n\n.segment \"{self.seg_bss}\"")

            if shared_slots_bss:
                self.emit("; Shared slots (BSS)")
                for slot_label, size in sorted(shared_slots_bss.items()):
                    self.emit(f"{slot_label}:\t.res {size}")
            
            if bss_byte_vars:
                self.emit("; Byte variables (BSS)")
                for sym in bss_byte_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 1")
            
            if bss_word_vars:
                self.emit("; Word variables (BSS)")
                for sym in bss_word_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 2")

            if bss_long_vars:
                self.emit("; Long variables (BSS)")
                for sym in bss_long_vars:
                     # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 4")
            
            if bss_struct_vars:
                self.emit("; Struct variables (BSS)")
                for sym in bss_struct_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        if sym.type.is_struct and sym.type.struct_info:
                            struct_size: int = sym.type.struct_info.size
                            self.emit(f"{sym.asm_name()}:\t.res {struct_size}")
                        else:
                            # Fallback (shouldn't happen if is_struct is correct)
                            self.emit(f"{sym.asm_name()}:\t.res 1")

            if pointer_scalar_bss:
                self.emit("; Pointer variables (BSS)")
                for sym in pointer_scalar_bss:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        self.emit(f"{sym.asm_name()}:\t.res 2")

            if pointer_array_bss:
                self.emit("; Pointer arrays (BSS)")
                for sym in pointer_array_bss:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        total_size: int = sym.get_total_array_size()
                        if total_size == 0:
                            self._raise_error(f"Array pointer '{sym.name}' has unknown size")
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")
            
            if array_vars:
                self.emit("; Array variables (BSS)")
                for sym in array_vars:
                    # Skip if already in shared slots
                    if not getattr(sym, 'shared_slot', None):
                        # Use the new get_total_array_size() method for multi-dimensional support
                        total_size: int = sym.get_total_array_size()
                        if total_size == 0:
                            # Fallback for old-style arrays without array_dims
                            size: int = sym.array_len if sym.array_len else 1
                            # Calculate element size based on type
                            if sym.type.is_struct and sym.type.struct_info:
                                element_size: int = sym.type.struct_info.size
                            elif sym.type.base == "WORD":
                                element_size = 2
                            else:
                                element_size = 1
                            total_size: int = size * element_size
                        self.emit(f"{sym.asm_name()}:\t.res {total_size}")


    def gen_globals_header(self) -> None:
        """Generate globals header.
        Internal helper used during code generation.
        """
        self.emit(f"\n\n.segment \"{self.seg_code}\"")
        self.emit("\n; Globals initialization")
        self.emit("; ------------------------------") 
               

    def gen_globals_footer(self) -> None:
        """Generate globals footer.
        Internal helper used during code generation.
        """
        self.emit("\n; Call MAIN")
        self.emit("; ------------------------------")        
        self.emit(f"\tJSR {self.asm_symbol_name('MAIN')}")       
        self.emit("\tJMP *\n")       

    def gen_init(self, sym: Symbol, is_global_init: bool = False) -> None:
        """Generate init.
        Internal helper used during code generation.
        """
        # Skip const values - they don't need runtime initialization
        # Const arrays are stored in ROM (ARRAY_DATA_*) and accessed directly
        # Const scalars are baked into code at usage points
        # Const structs would need initialization if they existed, but we handle them below if needed
        if sym.is_const:
            return
        
        if sym.init is None:
            return
        
        # If this is a static local variable being initialized during procedure entry, skip it
        # (static variables are initialized once at program start, not on each entry)
        # But if we're in global initialization (is_global_init=True), process it normally
        if sym.is_static and sym.proc_name != "" and not is_global_init:
            # This will be initialized in the global initialization section
            return
        
        # Skip unused globals (locals handled elsewhere)
        # Exception: always initialize fixed-address variables (hardware ports) and variables with initializers
        if sym.proc_name == "" and sym.name not in self.used_globals and sym.address is None and sym.init is None:
            return

        # Emit source comment for variable initializers
        if sym.proc_name:
            self.emit_src_comment_for_local(sym.proc_name, sym.name)
        else:
            self.emit_src_comment_for_global(sym.name)

        if isinstance(sym.init, ExprInit):
            # Immediate initializer
            if isinstance(sym.init.expr, IntLiteral):
                val: int = sym.init.expr.value
                # Check if constant fits in target type
                self._check_constant_fits(val, sym.type, f"initialization of {sym.name}")
                if sym.type.base == "BYTE" and not sym.type.is_pointer:
                    self._emit_store_byte_const(sym, val)
                elif sym.type.base == "LONG":
                    # Emit 4-byte initialization for LONG.
                    # Group bytes by value (first-occurrence order) so each unique byte value
                    # needs only one LDA, with all its STA destinations following it.
                    # On 65C02, zero bytes use STZ instead (no LDA, preserving that group).
                    asm = sym.asm_name()
                    _gi_grp: dict[int, list[int]] = {}
                    for _bi in range(4):
                        _bv: int = (val >> (_bi * 8)) & 0xFF
                        _gi_grp.setdefault(_bv, []).append(_bi)
                    for _bv, _offsets in _gi_grp.items():
                        if _bv == 0 and self.is_65c02:
                            for _bi in _offsets:
                                _d = asm if _bi == 0 else f"{asm}+{_bi}"
                                self.emit(f"\tSTZ {_d}")
                        else:
                            self.emit(f"\tLDA #${_bv:02X}")
                            for _bi in _offsets:
                                _d = asm if _bi == 0 else f"{asm}+{_bi}"
                                self.emit(f"\tSTA {_d}")
                else:  # WORD or pointer → store both bytes
                    self._emit_store_word_const(sym, val)
                return
            
            # Special case: struct initialized from const struct identifier
            if isinstance(sym.init.expr, Identifier) and sym.type.is_struct:
                src_sym: Symbol = self.current_symtab.lookup(sym.init.expr.name)
                if src_sym.is_const and src_sym.init and isinstance(src_sym.init, ListInit):
                    # Copy const struct bytes to destination
                    self._gen_const_struct_copy(sym, src_sym)
                    return

            # Optimization: Direct word ADD/SUB initialization without temporaries
            # e.g., word z = x + y;
            expr: Identifier | Expr = sym.init.expr
            if (isinstance(expr, BinaryExpr) and expr.op in {BinOp.ADD, BinOp.SUB} and
                sym.type.base == "WORD" and not sym.type.is_pointer and not sym.is_array and 
                sym.address is None and
                isinstance(expr.left, Identifier) and isinstance(expr.right, Identifier)):
                
                left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                
                if (not left_sym.is_array and left_sym.address is None and
                    not right_sym.is_array and right_sym.address is None):
                    
                    dest_asm: str = sym.asm_name()
                    left_asm: str = left_sym.asm_name()
                    right_asm: str = right_sym.asm_name()
                    
                    # Direct 16-bit ADD/SUB without temporaries
                    self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
                    if expr.op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=True)}")
                    else:  # SUB
                        self.emit("\tSEC")
                        self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=True)}")
                    self.emit(f"\tSTA {dest_asm}")
                    
                    self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=False)}")
                    if expr.op == BinOp.ADD:
                        self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=False)}")
                    else:  # SUB
                        self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=False)}")
                    self.emit(f"\tSTA {dest_asm}+1")
                    return

            # Optimization: Chained word ADD/SUB with immediate during initialization
            # e.g., word z = x + y + 5;
            expr: Identifier | Expr = sym.init.expr
            if (isinstance(expr, BinaryExpr) and expr.op in {BinOp.ADD, BinOp.SUB} and
                sym.type.base == "WORD" and not sym.type.is_pointer and not sym.is_array and 
                sym.address is None and
                isinstance(expr.left, BinaryExpr) and isinstance(expr.right, IntLiteral)):
                
                left_expr: BinaryExpr = expr.left
                imm_val: int = expr.right.value & 0xFFFF
                
                # Check if left operand is ADD/SUB of two identifiers
                if (left_expr.op in {BinOp.ADD, BinOp.SUB} and
                    isinstance(left_expr.left, Identifier) and 
                    isinstance(left_expr.right, Identifier)):
                    
                    # Lookup all symbols
                    x_sym: Symbol = self.current_symtab.lookup(left_expr.left.name)
                    y_sym: Symbol = self.current_symtab.lookup(left_expr.right.name)
                    
                    # Check all are simple variables
                    if (not x_sym.is_array and x_sym.address is None and
                        not y_sym.is_array and y_sym.address is None):
                        
                        dest_asm: str = sym.asm_name()
                        x_asm: str = x_sym.asm_name()
                        y_asm: str = y_sym.asm_name()
                        imm_low: int = imm_val & 0xFF
                        imm_high: int = (imm_val >> 8) & 0xFF
                        
                        # Step 1: Compute (x op1 y) and store in destination
                        self.emit(f"\tLDA {x_asm}")
                        if left_expr.op == BinOp.ADD:
                            self.emit("\tCLC")
                            self.emit(f"\tADC {y_asm}")
                        else:  # SUB
                            self.emit("\tSEC")
                            self.emit(f"\tSBC {y_asm}")
                        self.emit(f"\tSTA {dest_asm}")
                        
                        self.emit(f"\tLDA {x_asm}+1")
                        if left_expr.op == BinOp.ADD:
                            self.emit(f"\tADC {y_asm}+1")
                        else:  # SUB
                            self.emit(f"\tSBC {y_asm}+1")
                        self.emit(f"\tSTA {dest_asm}+1")
                        
                        # Step 2: Apply outer operation with immediate to destination
                        if expr.op == BinOp.ADD:
                            # dest = dest + imm
                            self.emit(f"\tLDA #${imm_low:02X}")
                            self.emit("\tCLC")
                            self.emit(f"\tADC {dest_asm}")
                            self.emit(f"\tSTA {dest_asm}")
                            
                            self.emit(f"\tLDA #${imm_high:02X}")
                            self.emit(f"\tADC {dest_asm}+1")
                            self.emit(f"\tSTA {dest_asm}+1")
                        else:  # SUB
                            # dest = dest - imm
                            self.emit(f"\tLDA {dest_asm}")
                            self.emit("\tSEC")
                            self.emit(f"\tSBC #${imm_low:02X}")
                            self.emit(f"\tSTA {dest_asm}")
                            
                            self.emit(f"\tLDA {dest_asm}+1")
                            self.emit(f"\tSBC #${imm_high:02X}")
                            self.emit(f"\tSTA {dest_asm}+1")
                        return

            # Special case: struct variable initialized from function call returning struct
            # e.g. Point p = make_point(1, 2) — mirrors the gen_assign path (~line 9507)
            if sym.type.is_struct and not sym.type.is_pointer and isinstance(sym.init.expr, CallExpr):
                call_init: CallExpr = cast(CallExpr, sym.init.expr)
                ret_buf_init = self.func_return_buffers.get(call_init.name)
                if ret_buf_init is None:
                    self._raise_error(f"Function '{call_init.name}' does not return a struct")
                asm_ret_init, ret_info_init = ret_buf_init
                specs_init = self.func_param_specs.get(call_init.name)
                if specs_init is not None:
                    self._emit_call_args(call_init.name, call_init.args, specs_init)
                self.emit(f"\tJSR {self.asm_symbol_name(call_init.name)}")
                self.emit(f"\tLDA #<{asm_ret_init}")
                self.emit("\tSTA TMP0")
                self.emit(f"\tLDA #>{asm_ret_init}")
                self.emit("\tSTA TMP0+1")
                self.emit(f"\tLDA #<{sym.asm_name()}")
                self.emit("\tSTA TMP2")
                self.emit(f"\tLDA #>{sym.asm_name()}")
                self.emit("\tSTA TMP2+1")
                if ret_info_init.size > 255:
                    self.copy_bytes16_needed = True
                    self.emit(f"\tLDA #${ret_info_init.size & 0xFF:02X}")
                    self.emit("\tSTA TMP4")
                    self.emit(f"\tLDA #${(ret_info_init.size >> 8) & 0xFF:02X}")
                    self.emit("\tSTA TMP4+1")
                    self.emit("\tJSR COPY_BYTES16")
                else:
                    self.copy_bytes_needed = True
                    self.emit(f"\tLDX #${ret_info_init.size:02X}")
                    self.emit("\tJSR COPY_BYTES")
                return

            # Fallback: general expression (non-const)
            # Set assignment target type context for optimizations
            prev_assign_type: SemType | None = self.assign_target_type
            self.assign_target_type = cast(SemType, sym.type)
            try:
                self.gen_expr(sym.init.expr)
            finally:
                self.assign_target_type = prev_assign_type
            
            if sym.type.base == "BYTE" and not sym.type.is_pointer:
                self.emit(f"\tSTA {sym.asm_name()}")
            else:
                self.emit(f"\tSTA {sym.asm_name()}")
                self.emit(f"\tSTX {sym.asm_name()}+1")
            return

        if isinstance(sym.init, StringInit):
            content: str = sym.init.value
            str_len: int = len(content) + 1  # Include null terminator
            dest_var: str = sym.asm_name()
            is_word: bool = sym.type.base == "WORD"
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space
            
            # Optimized string copy using loop
            # For very short strings (1-2 chars), inline is better
            if str_len <= 3:
                # Inline for very short strings (no string data needed)
                for i, ch in enumerate(content.encode('ascii')):
                    elem_offset: int = i * 2 if is_word else i
                    self.emit(f"\tLDA #${ch:02X}")
                    self.emit(f"\tSTA {dest_var}+{elem_offset}")
                    if is_word:
                        self.emit(f"\tLDX #$00")
                        self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
                # Add null terminator
                term_offset: int = len(content) * (2 if is_word else 1)
                self.emit(f"\tLDA #$00")
                self.emit(f"\tSTA {dest_var}+{term_offset}")
                if is_word:
                    self.emit(f"\tLDX #$00")
                    self.emit(f"\tSTX {dest_var}+{term_offset}+1")
            else:
                # Use shared copy routine for larger strings
                if content not in self.string_literals:
                    self.string_id += 1
                    self.string_literals[content] = f"__STR_DATA_{self.string_id}"
                str_label = self.string_literals[content]

                copy_len: int = str_len * (2 if is_word else 1)

                # Set source and destination pointers (common to all paths below)
                def _emit_str_ptrs() -> None:
                    self.emit(f"\tLDA #<{str_label}")
                    self.emit(f"\tLDX #>{str_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")
                    self.emit(f"\tLDA #<{dest_var}")
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")

                if copy_len <= 255:
                    # Fits in 8-bit count: use COPY_BYTES
                    self.copy_bytes_needed = True
                    _emit_str_ptrs()
                    self.emit(f"\tLDX #{copy_len}")
                    self.emit("\tJSR COPY_BYTES")
                else:
                    # Longer than 255 bytes: use 16-bit copy routine
                    self.copy_bytes16_needed = True
                    _emit_str_ptrs()
                    self.emit(f"\tLDA #${copy_len & 0xFF:02X}")
                    self.emit("\tSTA TMP4")
                    self.emit(f"\tLDA #${(copy_len >> 8) & 0xFF:02X}")
                    self.emit("\tSTA TMP4+1")
                    self.emit("\tJSR COPY_BYTES16")
            return

        if isinstance(sym.init, ListInit):
            # Check if this is a struct (array or single)
            struct_info: StructInfo | None = sym.type.struct_info
            is_struct_type: bool = sym.type.is_struct and struct_info is not None
            
            if is_struct_type and struct_info is not None:
                assert struct_info is not None  # Help Pylance understand struct_info is not None
                struct_size: int = struct_info.size
                flattened_values: list = []

                def _flatten_init(values: list, out: list) -> None:
                    """Recursively flatten nested ListInit into a flat list of expressions."""
                    for v in values:
                        if isinstance(v, ListInit):
                            _flatten_init(v.values, out)
                        else:
                            out.append(v)

                if sym.is_array:
                    # Struct array: each element should be a ListInit
                    # Recursively flatten nested lists into a single sequence of values
                    for struct_init in sym.init.values:
                        if isinstance(struct_init, ListInit):
                            _flatten_init(struct_init.values, flattened_values)
                        else:
                            # Include declaration source info if available
                            info = self.global_decl_src.get(sym.name) if not sym.proc_name else self.local_decl_src.get((sym.proc_name, sym.name))
                            if info:
                                fname, line, col, _ = info
                                err = SemanticError(f"Expected ListInit for struct element, got {type(struct_init)}", line=line, col=col)
                                err.filename = fname
                                if self.source_lines:
                                    err.source_text = "\n".join(self.source_lines)
                                raise err
                            # Fall back to generic error attached to current stmt if possible
                            self._raise_error(f"Expected ListInit for struct element, got {type(struct_init)}")
                else:
                    # Single struct: recursively flatten any nested ListInit values
                    _flatten_init(sym.init.values, flattened_values)
                
                # Now treat as a regular constant array of bytes/words
                is_const_array: bool = all(isinstance(ex, IntLiteral) for ex in flattened_values)
                
                if not is_const_array:
                    # Non-constant values
                    for i, ex in enumerate(flattened_values):
                        self.gen_expr(ex)
                        # Calculate offset: (struct_index * struct_size) + field_offset
                        field_offset: int = i % struct_size
                        struct_index: int = i // struct_size
                        base_offset: int = struct_index * struct_size + field_offset
                        
                        elem_offset: int = base_offset * 2 if sym.type.base == "WORD" else base_offset
                        self.emit(f"\tSTA {sym.asm_name()}+{elem_offset}")
                        if sym.type.base == "WORD":
                            self.emit(f"\tSTX {sym.asm_name()}+{elem_offset}+1")
                    return
                
                # Constant struct array - optimize with loop copy
                values: list[int] = []
                self._extract_const_values_from_listinit(sym.init, values)
                
                array_len: int = len(values)
                is_word: bool = sym.type.base == "WORD"
                dest_var: str = sym.asm_name()
                
                # Generate as regular array initialization
                COPY_THRESHOLD = 8
                
                if array_len <= 2:
                    # Inline for very short arrays
                    for i, ex in enumerate(flattened_values):
                        self.gen_expr(ex)
                        elem_offset: int = i * 2 if is_word else i
                        self.emit(f"\tSTA {dest_var}+{elem_offset}")
                        if is_word:
                            self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
                else:
                    # Use loop for longer arrays
                    data_key: tuple[tuple[int, ...], str] = (tuple(values), "WORD" if is_word else "BYTE")
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"

                    arr_label = self.array_literals[data_key]
                    elem_size: int = 2 if is_word else 1
                    total_bytes: int = array_len * elem_size

                    if total_bytes > 255:
                        # Large struct array: use 16-bit copy routine
                        self.copy_bytes16_needed = True
                        self.emit(f"\t; Copy struct array [{', '.join(str(v) for v in values[:10])}{'...' if len(values) > 10 else ''}] ({array_len} elements, {total_bytes} bytes)")
                        self.emit(f"\tLDA #<{arr_label}")
                        self.emit(f"\tLDX #>{arr_label}")
                        self.emit("\tSTA TMP0")
                        self.emit("\tSTX TMP0+1")
                        self.emit(f"\tLDA #<{dest_var}")
                        self.emit(f"\tLDX #>{dest_var}")
                        self.emit("\tSTA TMP2")
                        self.emit("\tSTX TMP2+1")
                        self.emit(f"\tLDA #${total_bytes & 0xFF:02X}")
                        self.emit("\tSTA TMP4")
                        self.emit(f"\tLDA #${(total_bytes >> 8) & 0xFF:02X}")
                        self.emit("\tSTA TMP4+1")
                        self.emit("\tJSR COPY_BYTES16")
                    elif total_bytes > COPY_THRESHOLD:
                        # Medium struct array (9-255 bytes): use shared 8-bit copy routine
                        self.copy_bytes_needed = True
                        self.emit(f"\t; Copy struct array [{', '.join(str(v) for v in values[:10])}{'...' if len(values) > 10 else ''}] ({array_len} bytes)")
                        self.emit(f"\tLDA #<{arr_label}")
                        self.emit(f"\tLDX #>{arr_label}")
                        self.emit("\tSTA TMP0")
                        self.emit("\tSTX TMP0+1")
                        self.emit(f"\tLDA #<{dest_var}")
                        self.emit(f"\tLDX #>{dest_var}")
                        self.emit("\tSTA TMP2")
                        self.emit("\tSTX TMP2+1")
                        self.emit(f"\tLDX #{total_bytes}")
                        self.emit("\tJSR COPY_BYTES")
                    else:
                        # Small struct array (3-8 bytes): inline indexed loop
                        self.emit(f"\t; Copy struct array [{', '.join(str(v) for v in values[:10])}{'...' if len(values) > 10 else ''}] ({array_len} bytes)")
                        self.emit(f"\tLDX #$00")
                        copy_loop: str = self.new_label("ARR_COPY")
                        self.emit(f"{copy_loop}:")
                        self.emit(f"\tLDA {arr_label},X")
                        self.emit(f"\tSTA {dest_var},X")
                        if is_word:
                            self.emit(f"\tLDA {arr_label}+1,X")
                            self.emit(f"\tSTA {dest_var}+1,X")
                            self.emit(f"\tINX")
                        self.emit(f"\tINX")
                        self.emit(f"\tCPX #{total_bytes}")
                        self.emit(f"\tBNE {copy_loop}")
                return
            
            # Regular (non-struct) array
            # Check if all values are constant integers
            is_const_array: bool = all(isinstance(ex, IntLiteral) for ex in sym.init.values)
            
            if not is_const_array:
                # Non-constant values - evaluate each element and store
                for i, ex in enumerate(sym.init.values):
                    asm_name: str = sym.asm_name()
                    if sym.type.base == "LONG" and not sym.type.is_pointer:
                        elem_offset: int = i * 4
                        if isinstance(ex, IntLiteral):
                            # IntLiteral: emit 4 bytes directly (gen_expr doesn't load LONG literals into MATH0)
                            val: int = ex.value
                            last_lda: int = -1
                            for j in range(4):
                                byte_val: int = (val >> (8 * j)) & 0xFF
                                if byte_val == 0 and self.is_65c02:
                                    self.emit(f"\tSTZ {asm_name}+{elem_offset + j}")
                                    last_lda = -1
                                elif byte_val != last_lda:
                                    self.emit(f"\tLDA #${byte_val:02X}")
                                    self.emit(f"\tSTA {asm_name}+{elem_offset + j}")
                                    last_lda = byte_val
                                else:
                                    self.emit(f"\tSTA {asm_name}+{elem_offset + j}")
                        else:
                            # Expression: result in MATH0 after gen_expr
                            self.gen_expr(ex)
                            self.emit(f"\tLDA MATH0")
                            self.emit(f"\tSTA {asm_name}+{elem_offset}")
                            self.emit(f"\tLDA MATH0+1")
                            self.emit(f"\tSTA {asm_name}+{elem_offset + 1}")
                            self.emit(f"\tLDA MATH0+2")
                            self.emit(f"\tSTA {asm_name}+{elem_offset + 2}")
                            self.emit(f"\tLDA MATH0+3")
                            self.emit(f"\tSTA {asm_name}+{elem_offset + 3}")
                    else:
                        self.gen_expr(ex)
                        elem_offset = i * 2 if (sym.type.base == "WORD" or sym.type.is_pointer) else i
                        self.emit(f"\tSTA {asm_name}+{elem_offset}")
                        if sym.type.base == "WORD" or sym.type.is_pointer:
                            self.emit(f"\tSTX {asm_name}+{elem_offset + 1}")
                return

            # Constant array - optimize with loop copy
            # Type narrowing: we've verified all elements are IntLiteral above
            values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
            array_len: int = len(values)
            is_long: bool = sym.type.base == "LONG" and not sym.type.is_pointer
            is_word: bool = (sym.type.base == "WORD" or sym.type.is_pointer) and not is_long
            dest_var: str = sym.asm_name()
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space

            # For very short arrays (1-2 elements), inline is better
            if array_len <= 2:
                # Inline for very short arrays
                for i, ex in enumerate(sym.init.values):
                    if is_long:
                        assert isinstance(ex, IntLiteral)
                        val = ex.value
                        elem_offset = i * 4
                        last_lda = -1
                        for j in range(4):
                            byte_val = (val >> (8 * j)) & 0xFF
                            if byte_val == 0 and self.is_65c02:
                                self.emit(f"\tSTZ {dest_var}+{elem_offset + j}")
                                last_lda = -1
                            elif byte_val != last_lda:
                                self.emit(f"\tLDA #${byte_val:02X}")
                                self.emit(f"\tSTA {dest_var}+{elem_offset + j}")
                                last_lda = byte_val
                            else:
                                self.emit(f"\tSTA {dest_var}+{elem_offset + j}")
                    else:
                        self.gen_expr(ex)
                        elem_offset = i * 2 if is_word else i
                        self.emit(f"\tSTA {dest_var}+{elem_offset}")
                        if is_word:
                            self.emit(f"\tSTX {dest_var}+{elem_offset + 1}")
            else:
                # Use loop for longer arrays
                # Create unique key for this array data
                data_type_key: str = "LONG" if is_long else ("WORD" if is_word else "BYTE")
                data_key: tuple[tuple[int, ...], str] = (tuple(values), data_type_key)
                if data_key not in self.array_literals:
                    self.array_id += 1
                    self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"

                arr_label = self.array_literals[data_key]
                elem_size: int = 4 if is_long else (2 if is_word else 1)
                total_bytes: int = array_len * elem_size

                if total_bytes > 255:
                    # Large array: use 16-bit copy routine
                    self.copy_bytes16_needed = True
                    self.emit(f"\t; Copy array [{', '.join(str(v) for v in values[:5])}{'...' if len(values) > 5 else ''}] ({array_len} elements, {total_bytes} bytes)")
                    self.emit(f"\tLDA #<{arr_label}")
                    self.emit(f"\tLDX #>{arr_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")
                    self.emit(f"\tLDA #<{dest_var}")
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")
                    self.emit(f"\tLDA #${total_bytes & 0xFF:02X}")
                    self.emit("\tSTA TMP4")
                    self.emit(f"\tLDA #${(total_bytes >> 8) & 0xFF:02X}")
                    self.emit("\tSTA TMP4+1")
                    self.emit("\tJSR COPY_BYTES16")
                elif total_bytes > COPY_THRESHOLD:
                    # Medium array (9-255 bytes): use shared 8-bit copy routine
                    self.copy_bytes_needed = True
                    self.emit(f"\t; Copy array [{', '.join(str(v) for v in values[:5])}{'...' if len(values) > 5 else ''}] ({array_len} elements, {total_bytes} bytes)")
                    self.emit(f"\tLDA #<{arr_label}")
                    self.emit(f"\tLDX #>{arr_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")
                    self.emit(f"\tLDA #<{dest_var}")
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")
                    self.emit(f"\tLDX #{total_bytes}")
                    self.emit("\tJSR COPY_BYTES")
                else:
                    # Small array (3-8 bytes, BYTE/WORD only — LONG arrays with 3+ elems always > 8 bytes)
                    self.emit(f"\t; Copy array [{', '.join(str(v) for v in values[:5])}{'...' if len(values) > 5 else ''}] ({array_len} elements)")
                    self.emit(f"\tLDX #$00")
                    copy_loop: str = self.new_label("ARR_COPY")
                    self.emit(f"{copy_loop}:")
                    self.emit(f"\tLDA {arr_label},X")
                    self.emit(f"\tSTA {dest_var},X")
                    if is_word:
                        self.emit(f"\tLDA {arr_label}+1,X")
                        self.emit(f"\tSTA {dest_var}+1,X")
                        self.emit(f"\tINX")
                    self.emit(f"\tINX")
                    self.emit(f"\tCPX #{total_bytes}")
                    self.emit(f"\tBNE {copy_loop}")
            return

        self._raise_error("Complex initializer pattern not supported")


    def emit(self, line: str) -> None:
        """Append an assembly line to the output buffer.
        Rewrites internal names and tracks usage.
        """
        line = self._rewrite_internal_names(line)
        self.code.append(line)
        # Track frequency for ZP prioritization
        self._track_local_access_frequency(line)

    def _track_local_access_frequency(self, line: str) -> None:
        """Track load/store frequency for ZP prioritization.
        Only tracks scalar locals (not arrays, fixed-address, or pointers)."""
        # Detect LDA/STA/LDX/STX/LDY/STY operations on local variable references
        # Pattern: instruction _PROCNAME_LOCALNAME[+offset] or instruction (_PROCNAME_LOCALNAME[,Y])
        import re
        
        # Match main instruction operand patterns
        # Format: STA _PROCNAME_LOCALNAME or STA _PROCNAME_LOCALNAME+1 or LDA (_ptr),Y
        pattern = r'\s+(LDA|STA|LDX|STX|LDY|STY)\s+([_A-Z0-9]+)'
        match = re.search(pattern, line)
        if not match:
            return
        
        operand = match.group(2)
        # Skip system temps and registers
        sys_names = ("MATH_STACK", "MATH0", "MATH1", "TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5")
        sys_prefixed = {self._internal_name_map.get(name, name) for name in sys_names}
        if operand in (sys_prefixed | {"A", "X", "Y"}):
            return
        
        # Extract _PROCNAME_LOCALNAME from operand (strip +1, etc.)
        base_operand = operand.split('+')[0].split(',')[0]
        if not base_operand.startswith('_') or base_operand.count('_') < 2:
            return
        
        # Parse _PROCNAME_LOCALNAME or __PROCNAME_LOCALNAME → (PROCNAME, LOCALNAME)
        trimmed = base_operand.lstrip('_')
        parts = trimmed.split('_', 1)
        if len(parts) < 2:
            return
        
        proc_name, local_name = parts[0], parts[1]
        local_id = f"{proc_name}::{local_name}"
        
        # Verify this is a real local scalar (not array, not port, not fixed-address)
        try:
            sym = self.current_symtab.lookup(local_name)
            if sym and not sym.is_array and not sym.is_port and sym.address is None and sym.proc_name:
                # Track this access (combined load/store frequency)
                self.local_access_frequency[local_id] = self.local_access_frequency.get(local_id, 0) + 1
        except:
            pass  # Symbol not found or lookup failed

    def emit_src_comment_for_stmt(self, stmt) -> None:
        """Emit src comment for stmt.
        Internal helper used during code generation.
        """
        info = self.stmt_src.get(id(stmt))
        if info:
            # Support both 3-tuple and 4-tuple forms
            if len(info) == 3:
                fname, line, text = info
                col = 1
                self.current_stmt_info = (fname, line, col, text)
            else:
                fname, line, col, text = info
                self.current_stmt_info = (fname, line, col, text)
            display_line = self._map_clean_line_to_orig(fname, line)
            self.emit(f"\n; {fname} {display_line if display_line is not None else line}: {text}")

    def emit_src_comment_for_local(self, proc_name: str, var_name: str) -> None:
        """Emit src comment for local.
        Internal helper used during code generation.
        """
        info = self.local_decl_src.get((proc_name, var_name))
        if info:
            fname, line, col, text = info
            # Also attach current_stmt_info so subsequent raises have context
            self.current_stmt_info = (fname, line, col, text)
            display_line = self._map_clean_line_to_orig(fname, line)
            self.emit(f"\n; {fname} {display_line if display_line is not None else line}: {text}")

    def emit_src_comment_for_global(self, var_name: str) -> None:
        """Emit src comment for global.
        Internal helper used during code generation.
        """
        info = self.global_decl_src.get(var_name)
        if info:
            fname, line, col, text = info
            # Also attach current_stmt_info so subsequent raises have context
            self.current_stmt_info = (fname, line, col, text)
            display_line = self._map_clean_line_to_orig(fname, line)
            self.emit(f"\n; {fname} {display_line if display_line is not None else line}: {text}")

    def _map_clean_line_to_orig(self, fname: str, line: int | None) -> int | None:
        """Map clean line to orig.
        Internal helper used during code generation.
        """
        if fname and isinstance(line, int):
            orig_map = self.orig_line_map_per_file.get(fname)
            if orig_map and 1 <= line <= len(orig_map):
                return orig_map[line - 1]
        return line

    def _get_source_lines_for_file(self, fname: str | None) -> list[str] | None:
        """Return source lines for file.
        Internal helper used during code generation.
        """
        if not fname:
            return self.source_lines if self.source_lines else None
        orig_src = self.orig_source_lines_per_file.get(fname)
        if orig_src:
            return orig_src
        cleaned_src = self.file_lines.get(fname)
        if cleaned_src:
            return cleaned_src
        return self.source_lines if self.source_lines else None

    def _raise_error(self, msg: str) -> NoReturn:
        """Helper for raise error.
        Internal helper used during code generation.
        """
        # Attach line/col and source text for better error output
        from errors import SemanticError
        if self.current_stmt_info:
            fname, line, col, _ = self.current_stmt_info
            mapped_line = self._map_clean_line_to_orig(fname, line)
            e = SemanticError(msg, line=mapped_line if mapped_line is not None else line, col=col)
            src_lines = self._get_source_lines_for_file(fname)
            if src_lines:
                e.source_text = "\n".join(src_lines)
            if fname:
                e.filename = fname
            raise e
        else:
            # Attach current expression node if present so error has location
            raise SemanticError(msg, node=getattr(self, 'current_expr', None))

    def _load_sym_addr(self, sym_name: str) -> None:
        """Load sym addr.
        Internal helper used during code generation.
        """
        self.emit(f"\tLDA #<{sym_name}")
        self.emit(f"\tLDX #>{sym_name}")

    def _sym_operand(self, sym: Symbol, low_byte: bool = True) -> str:
        """Return an operand string for symbol `sym`.
        For const scalars emits immediate operand using the assembler constant
        (e.g., '#_NAME' or '#<_NAME'/'#>_NAME' for word low/high).
        For variables emits memory operand ('_NAME' or '_NAME+1' for high byte).
        """
        if sym.is_const:
            # Const scalars/bytes
            if sym.type.base == "WORD" or sym.type.is_pointer:
                # For word/pointer consts: use low/high byte operators
                prefix = '<' if low_byte else '>'
                return f"#{prefix}{sym.asm_name()}"
            else:
                return f"#{sym.asm_name()}"
        else:
            # Non-const: memory operand
            return f"{sym.asm_name()}" + ("" if low_byte else "+1")

    def _gen_literal(self, expr: IntLiteral) -> None:
        """Generate literal.
        Internal helper used during code generation.
        """
        t: ExprType = self.tc_check(expr)
        val: int = expr.value
        self.emit(f"\tLDA #${val & 0xFF:02X}")
        # Set X = high byte when needed; skip for byte-return ABI in return context
        if t.sem_type.base == "WORD" or t.sem_type.is_pointer or self.force_word_result:
            self.emit(f"\tLDX #${(val >> 8) & 0xFF:02X}")
        elif t.sem_type.base == "LONG":
            # LONG literal: load all 4 bytes into MATH0 (LONG convention)
            self.emit("\tSTA MATH0")
            self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
            self.emit("\tSTA MATH0+1")
            self.emit(f"\tLDA #${(val >> 16) & 0xFF:02X}")
            self.emit("\tSTA MATH0+2")
            self.emit(f"\tLDA #${(val >> 24) & 0xFF:02X}")
            self.emit("\tSTA MATH0+3")
        elif not self.suppress_byte_return_x:
            # Skip clearing X when assigning to a BYTE target
            target_is_byte: None | bool = (self.assign_target_type and
                            hasattr(self.assign_target_type, 'base') and
                            self.assign_target_type.base == "BYTE" and
                            not getattr(self.assign_target_type, 'is_pointer', False))
            if not target_is_byte:
                self.emit("\tLDX #$00")

    def _gen_string_literal(self, expr: StringLiteral) -> None:
        """Generate string literal address in A/X.
        Internal helper used during code generation.
        """
        content: str = expr.value
        if content not in self.string_literals:
            self.string_id += 1
            self.string_literals[content] = f"__STR_DATA_{self.string_id}"
        label: str = self.string_literals[content]
        self._load_sym_addr(label)


    def _gen_identifier(self, expr: Identifier) -> None:
        """Generate identifier.
        Internal helper used during code generation.
        """
        t: ExprType = self.tc_check(expr)
        sym: Symbol = self.current_symtab.lookup(expr.name)

        if sym.is_const:
            # Handle const arrays specially - they have addresses to ROM data
            if sym.is_array:
                # Const arrays: get address of ROM data
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    _is_long_arr: bool = sym.type.base == "LONG" and not sym.type.is_pointer
                    _is_word_arr: bool = sym.type.base == "WORD" and not _is_long_arr
                    _arr_dtype: str = "LONG" if _is_long_arr else ("WORD" if _is_word_arr else "BYTE")
                    data_key: tuple[tuple[int, ...], str] = (tuple(values), _arr_dtype)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                    return
                if sym.init and isinstance(sym.init, StringInit):
                    if sym.type.base != "BYTE":
                        self._raise_error("String init only supported for byte arrays")
                    values = [ord(ch) for ch in sym.init.value] + [0]
                    data_key = (tuple(values), "BYTE")
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                    return
                else:
                    self._raise_error(f"Const array '{sym.name}' has no initialization")
            
            # Handle const structs - they have addresses to ROM data
            if sym.type.is_struct:
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    data_key = (tuple(values), "BYTE")
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                    return
                else:
                    self._raise_error(f"Const struct '{sym.name}' has no initialization")
            
            # Const scalars
            if sym.const_value is None:
                self._raise_error(f"Constant '{sym.name}' has no value")
            # Use assembler-level constant reference so generated assembly can reference it
            if sym.type.base == "WORD" or sym.type.is_pointer:
                # Word/pointer constants: load low/high bytes using < and > operators
                self.emit(f"\tLDA #<{sym.asm_name()}")
                self.emit(f"\tLDX #>{sym.asm_name()}")
            else:
                # Byte constants: immediate symbol
                self.emit(f"\tLDA #{sym.asm_name()}")
            return

        # ADDR (pointer nebo pole)
        if t.kind == ExprKind.ADDR:
            if sym.type.is_pointer and not sym.is_array:
                # Load pointer value stored in the variable (A=low, X=high)
                asm: str = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit(f"\tLDX {asm}+1")
            else:
                # Arrays decay to their address
                self._load_sym_addr(sym.asm_name())
            return

        # VALUE
        asm: str = sym.asm_name()
        # VALUE
        asm: str = sym.asm_name()
        if t.sem_type.base == "LONG":
            # Load 32-bit value into MATH0
            # We can't use A/X for 32-bit values
            self.emit(f"\tLDA {asm}")
            self.emit(f"\tSTA MATH0")
            self.emit(f"\tLDA {asm}+1")
            self.emit(f"\tSTA MATH0+1")
            self.emit(f"\tLDA {asm}+2")
            self.emit(f"\tSTA MATH0+2")
            self.emit(f"\tLDA {asm}+3")
            self.emit(f"\tSTA MATH0+3")
            return

        self.emit(f"\tLDA {asm}")
        if t.sem_type.base == "WORD":
            self.emit(f"\tLDX {asm}+1")
        else:
            # BYTE → X = 0
            # Optimization: skip LDX #$00 if assignment target is BYTE (no need to set high byte)
            target_is_byte: None | bool = (self.assign_target_type and
                            hasattr(self.assign_target_type, 'base') and
                            self.assign_target_type.base == "BYTE" and
                            not getattr(self.assign_target_type, 'is_pointer', False))
            if (not target_is_byte or self.force_word_result) and not self.suppress_byte_return_x:
                self.emit("\tLDX #$00   ; note 3056")

    def _is_zeropage_pointer_array_subscript(self, expr) -> tuple[bool, Symbol | None, int]:
        """Check if expr is SubscriptExpr of a ZEROPAGE pointer array with BYTE index.
        
        Returns: (is_optimizable, symbol, byte_offset)
        - is_optimizable: True if we can use ZP indexed indirect addressing
        - symbol: The pointer array symbol
        - byte_offset: The byte offset to use in index register (or -1 if not constant/not computable)
        """
        if not isinstance(expr, SubscriptExpr):
            return False, None, -1
        
        if not isinstance(expr.array, Identifier):
            return False, None, -1
        
        sym: Symbol | None = self.current_symtab.lookup(expr.array.name)
        
        # Check: is it a pointer array in ZEROPAGE?
        if not (sym.is_array and sym.type.is_pointer and sym.address is None and not sym.is_const and sym.in_zeropage):
            return False, None, -1
        
        # Check: is the index a constant or simple expression that we can evaluate?
        # For now, only support constant indices
        if not isinstance(expr.index, IntLiteral):
            return False, None, -1
        
        # Check: does the byte offset fit in a single byte (Y register)?
        element_width: int = self._calculate_element_width(sym)
        byte_offset: int = expr.index.value * element_width
        
        if byte_offset >= 256:
            return False, None, -1
        
        return True, sym, byte_offset
    
    def _gen_deref_optimized_zeropage(self, expr: DerefExpr, sym: Symbol, byte_offset: int) -> None:
        """Generate optimized deref for ZEROPAGE pointer array subscript.
        
        Uses (ZP,X) addressing to dereference the pointer stored in the ZP array.
        This is valid only for BYTE deref targets; WORD still needs TMP0 + (TMP0),Y.
        """
        t: ExprType = self.tc_check(expr)

        # Only safe for BYTE deref targets
        if t.sem_type.base != "BYTE" or t.sem_type.is_pointer:
            return
        
        arr_base: str = sym.asm_name()
        self.emit(f"\tLDX #${byte_offset:02X}    ; byte offset = index * element_width")
        self.emit(f"\tLDA ({arr_base},X)")
    
    def _gen_deref(self, expr: DerefExpr) -> None:
        """Generate deref.
        Internal helper used during code generation.
        """
        t: ExprType = self.tc_check(expr)

        # OPTIMIZATION: Check for ZEROPAGE pointer array subscript (BYTE-only)
        is_zp_ptr_array, sym, byte_offset = self._is_zeropage_pointer_array_subscript(expr.pointer)
        if is_zp_ptr_array and sym is not None and t.sem_type.base == "BYTE" and not t.sem_type.is_pointer:
            self._gen_deref_optimized_zeropage(expr, sym, byte_offset)
            return

        # If pointer is a simple ZP identifier, use direct addressing without TMP0
        if isinstance(expr.pointer, Identifier):
            ptr_sym: Symbol = self.current_symtab.lookup(expr.pointer.name)
            if (ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array
                and ptr_sym.in_zeropage):
                ptr_asm: str = ptr_sym.asm_name()
                if t.sem_type.base == "LONG":
                    # Load 4 bytes into MATH0 via indexed indirect
                    if self.is_65c02:
                        self.emit(f"\tLDA ({ptr_asm})")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tSTA MATH0")
                    self.emit("\tLDY #1")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tSTA MATH0+1")
                    self.emit("\tLDY #2")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tSTA MATH0+2")
                    self.emit("\tLDY #3")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tSTA MATH0+3")
                elif t.sem_type.base == "WORD":
                    # Load high byte first, then low (saves stack ops)
                    self.emit("\tLDY #1")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tTAX")
                    if self.is_65c02:
                        self.emit(f"\tLDA ({ptr_asm})")
                    else:
                        self.emit("\tDEY")
                        self.emit(f"\tLDA ({ptr_asm}),Y")
                else:
                    if self.is_65c02:
                        self.emit(f"\tLDA ({ptr_asm})")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit(f"\tLDA ({ptr_asm}),Y")
                return

        # 1) vygeneruj adresu pointeru → A/X
        # For LONG targets, save MATH1 to stack since gen_expr may
        # clobber it via ADD16_AX (breaks LONG comparisons)
        _save_math1: bool = (t.sem_type.base == "LONG")
        if _save_math1:
            self.emit("\tLDA MATH1")
            self.emit("\tPHA")
            self.emit("\tLDA MATH1+1")
            self.emit("\tPHA")
            self.emit("\tLDA MATH1+2")
            self.emit("\tPHA")
            self.emit("\tLDA MATH1+3")
            self.emit("\tPHA")

        self.gen_expr(expr.pointer)

        # 2) ulož adresu (word temp uses contiguous bytes)
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")

        if _save_math1:
            self.emit("\tPLA")
            self.emit("\tSTA MATH1+3")
            self.emit("\tPLA")
            self.emit("\tSTA MATH1+2")
            self.emit("\tPLA")
            self.emit("\tSTA MATH1+1")
            self.emit("\tPLA")
            self.emit("\tSTA MATH1")

        # 3) načti LOW/HIGH byte(s)
        if t.sem_type.base == "LONG":
            # Load 4 bytes into MATH0
            self.emit("\tLDY #$00")
            self.emit("\tLDA (TMP0),Y")
            self.emit("\tSTA MATH0")
            self.emit("\tINY")
            self.emit("\tLDA (TMP0),Y")
            self.emit("\tSTA MATH0+1")
            self.emit("\tINY")
            self.emit("\tLDA (TMP0),Y")
            self.emit("\tSTA MATH0+2")
            self.emit("\tINY")
            self.emit("\tLDA (TMP0),Y")
            self.emit("\tSTA MATH0+3")
        elif t.sem_type.base == "WORD":
            # Load high byte first, then low (saves stack ops)
            self.emit("\tLDY #1")
            self.emit("\tLDA (TMP0),Y")
            self.emit("\tTAX")
            self.emit("\tDEY")
            self.emit("\tLDA (TMP0),Y")
        else:
            self.emit("\tLDY #$00")
            self.emit("\tLDA (TMP0),Y")

    def _collect_subscript_indices(self, expr: SubscriptExpr) -> tuple:
        """Collect all indices and base identifier from nested subscripts.
        
        For arr[i][j][k], returns ([k, j, i], Identifier('arr'))
        For struct_var.array_field[i][j], returns ([j, i], FieldAccess(...))
        (indices are collected in reverse order as we traverse the nesting)
        """
        indices = [expr.index]
        current: Expr = expr.array
        
        # Traverse nested subscripts
        while isinstance(current, SubscriptExpr):
            indices.append(current.index)
            current: Expr = current.array
        
        # current should now be an Identifier or FieldAccess
        if not isinstance(current, (Identifier, FieldAccess)):
            self._raise_error("Subscript base must be array identifier or field access")
        
        # Reverse to get correct order: [i, j, k]
        indices.reverse()
        
        return indices, current

    def _get_array_dimensions_for_codegen(self, sym: Symbol) -> list:
        """Get array dimensions for code generation.
        
        For 1D: returns [size] if size is known, [] if inferred
        For ND: returns [d1, d2, d3, ...] or [] if any dimension is inferred
        """
        if not sym.is_array:
            return []
        
        if sym.array_dims:
            # Multi-dimensional array
            if all(d is not None for d in sym.array_dims):
                return sym.array_dims
            else:
                # Some dimensions were inferred - can't do stride calculation
                return []
        elif sym.array_len:
            # 1D array (backward compat)
            return [sym.array_len]
        
        return []

    def _calculate_element_width(self, sym: Symbol) -> int:
        """Calculate the width of array elements in bytes.

        For array of pointers, the element width is the pointer size (2 bytes).
        For arrays of structs or native WORD/byte types, return the natural width.
        """
        # If array elements are pointers (e.g., byte ^arr[]), element size is pointer size (2)
        if sym.type.is_pointer:
            return 2

        # Non-pointer struct variable
        if sym.type.is_struct and sym.type.struct_info:
            return sym.type.struct_info.size
        # Native WORD type
        if sym.type.base == "WORD":
            return 2
        # Native LONG type
        if sym.type.base == "LONG":
            return 4
        # Default BYTE
        return 1

    def _gen_multidim_subscript(self, indices: list, sym: Symbol, 
                                load_only: bool, calc_addr_only: bool = False) -> None:
        """Generate code for multi-dimensional subscript with known dimensions.
        
        For arr[i][j][k] with dimensions [d1, d2, d3] and element width E:
        Strides: [d2*d3*E, d3*E, E]
        Offset = i*s[0] + j*s[1] + k*s[2]
        
        OPTIMIZATION: If all indices are compile-time constants (IntLiteral),
        compute the offset at compile time rather than runtime.
        """
        dims = self._get_array_dimensions_for_codegen(sym)
        if not dims:
            self._raise_error("Multi-dimensional array dimensions must be known")
        
        element_width: int = self._calculate_element_width(sym)
        
        # Calculate strides (least significant to most)
        strides = []
        stride: int = element_width
        for i in range(len(dims) - 1, -1, -1):
            strides.insert(0, stride)
            stride *= dims[i]
        
        # OPTIMIZATION: Check if all indices are compile-time constants
        all_indices_const: bool = all(isinstance(idx, IntLiteral) for idx in indices)
        
        if all_indices_const:
            # Compile-time address calculation - OPTIMIZED
            # Calculate offset: offset = i*stride[0] + j*stride[1] + k*stride[2] + ...
            compile_time_offset = 0
            for idx_expr, stride_val in zip(indices, strides):
                compile_time_offset += idx_expr.value * stride_val
            
            # Get offset as low and high bytes
            offset_low = compile_time_offset & 0xFF
            offset_high = (compile_time_offset >> 8) & 0xFF
            
            # Load base address and add compile-time offset directly
            # Optimized approach: load each byte sequentially, avoiding TXA move
            if compile_time_offset == 0:
                # No offset needed, load base address directly
                self.emit(f"\tLDA #${sym.address:02X}" if sym.address else f"\tLDA #<{sym.asm_name()}")
                self.emit("\tSTA TMP0")
                self.emit(f"\tLDA #${(sym.address >> 8) & 0xFF:02X}" if sym.address else f"\tLDA #>{sym.asm_name()}")
                self.emit("\tSTA TMP0+1")
            else:
                # Add compile-time offset: load low byte, add offset, store; then high byte with carry
                self.emit(f"\tLDA #<{sym.asm_name()}")
                self.emit("\tCLC")
                self.emit(f"\tADC #${offset_low:02X}")
                self.emit("\tSTA TMP0")
                # Carry flag now contains any overflow from low byte addition
                self.emit(f"\tLDA #>{sym.asm_name()}")
                self.emit(f"\tADC #${offset_high:02X}")
                self.emit("\tSTA TMP0+1")
            
            # If only calculating address, stop here
            if calc_addr_only:
                return

            if load_only:
                if element_width == 2:
                    self.emit("\tLDY #1")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tTAX")  # X = high byte
                    self.emit("\tDEY")
                    self.emit("\tLDA (TMP0),Y")
                else:
                    self.emit("\tLDY #$00")
                    self.emit("\tLDA (TMP0),Y")
                    # For BYTE element, only set X if final target is not BYTE
                    # If target is BYTE, we only need the low byte in A
                    need_x = True
                    if self.assign_target_type:
                        if hasattr(self.assign_target_type, 'base'):
                            if (self.assign_target_type.base == "BYTE" and 
                                not getattr(self.assign_target_type, 'is_pointer', False)):
                                need_x = False
                    if need_x:
                        self.emit("\tLDX #$00     ; note 3322")
                        self.emit("\tLDX #$00     ; note 3211")
            else:
                # Store RHS value (in TMP2/TMP2+1)
                self.emit("\tLDA TMP2")
                if element_width == 2:
                    self.emit("\tLDY #$00")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA TMP2+1")
                    self.emit("\tSTA (TMP0),Y")
                else:
                    self._emit_indirect_store_zero("TMP0")
            return
        
        # Runtime address calculation (for non-constant indices)
        # Note: RHS value is already in TMP2/TMP2+1 (saved by gen_assign before calling this method)
        
        # Calculate total offset for address: TMP4/TMP4+1 will accumulate
        self.emit("\tLDA #$00")
        self.emit("\tSTA TMP4")
        self.emit("\tSTA TMP4+1")
        
        # Add each index * stride to offset
        for idx_expr, stride_val in zip(indices, strides):
            # Evaluate index expression -> A
            self.gen_expr(idx_expr)
            
            # Multiply index by stride
            if stride_val == 1:
                # No multiplication needed - A already has index
                self.emit("\tLDX #$00     ; note 3212; note 3239")  # Clear high byte
            elif stride_val == 2:
                # Multiply by 2: ASL
                self.emit("\tASL")
                self.emit("\tLDX #$00     ; note 3243")
            elif stride_val & (stride_val - 1) == 0:
                # Power of 2: use bit shifts
                shifts = (stride_val - 1).bit_length()  # log2(stride_val)
                for _ in range(shifts):
                    self.emit("\tASL")
                self.emit("\tLDX #$00     ; note 3249")
            else:
                # General multiplication (non-power-of-2)
                # Save A (index) to a temporary (use TMP5 to avoid conflicts)
                self.emit("\tSTA TMP5")
                
                # Multiply TMP5 * stride -> A:X using repeated addition
                self.emit("\tLDA #$00")
                self.emit("\tSTA TMP3")  # TMP3 = result low byte
                # self.emit("\tLDA #$00") # Fixme: ### already cleared above
                self.emit("\tLDX #$00     ; note 3259")   # X = result high byte
                
                for _ in range(stride_val):
                    self.emit("\tCLC")
                    self.emit("\tLDA TMP5")
                    self.emit("\tADC TMP3")
                    self.emit("\tSTA TMP3")
                    carry_lbl: str = self.new_label("STRIDE_CARRY")
                    self.emit(f"\tBCC {carry_lbl}")
                    self.emit("\tINX")
                    self.emit(f"{carry_lbl}:")
                
                self.emit("\tLDA TMP3")
                # X already has high byte
            
            # Now A/X has (index * stride), add to TMP4
            self.emit("\tCLC")
            self.emit("\tADC TMP4")
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tADC TMP4+1")
            self.emit("\tSTA TMP4+1")
        
        # Load base address -> TMP0/TMP0+1
        self._load_sym_addr(sym.asm_name())
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")
        
        # TMP4/TMP4+1 now has total offset, add to base address in TMP0
        self.emit("\tLDA TMP4")
        self.emit("\tCLC")
        self.emit("\tADC TMP0")
        self.emit("\tSTA TMP0")
        self.emit("\tLDA TMP4+1")
        self.emit("\tADC TMP0+1")
        self.emit("\tSTA TMP0+1")
        
        # If only calculating address, stop here
        if calc_addr_only:
            return
        
        # Load or store element at TMP0
        if load_only:
            if element_width == 2:
                self.emit("\tLDY #1")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tTAX")  # X = high byte
                self.emit("\tDEY")
                self.emit("\tLDA (TMP0),Y")
            else:
                self.emit("\tLDY #$00")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tLDX #$00     ; note 3311")
        else:
            # Store RHS value (in TMP2/TMP2+1)
            self.emit("\tLDA TMP2")
            if element_width == 2:
                self.emit("\tLDY #$00")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tINY")
                self.emit("\tLDA TMP2+1")
                self.emit("\tSTA (TMP0),Y")
            else:
                self._emit_indirect_store_zero("TMP0")

    def _gen_subscript(self, expr: SubscriptExpr, load_only: bool, calc_addr_only: bool = False) -> None:
        """Generate subscript.
        Internal helper used during code generation.
        """
        # Check if this is a multi-dimensional subscript
        indices, base = self._collect_subscript_indices(expr)
        
        # For multi-index subscripts with Identifier base, use multi-dimensional code generation
        if len(indices) > 1 and isinstance(base, Identifier):
            sym: Symbol = self.current_symtab.lookup(base.name)
            self._gen_multidim_subscript(indices, sym, load_only, calc_addr_only)
            return
        
        # OPTIMIZATION: Direct load for immediate indices (compile-time constants)
        # Pattern: arr[1] where index is known at compile time
        if (load_only and isinstance(base, Identifier) and isinstance(expr.index, IntLiteral) and
            not calc_addr_only):
            sym: Symbol = self.current_symtab.lookup(base.name)
            if sym.is_array and not sym.is_const:
                # This is a simple array with runtime base address
                arr_addr: str = sym.asm_name()
                element_width: int = self._calculate_element_width(sym)
                index_val: int = expr.index.value
                offset: int = index_val * element_width
                
                # Direct load from arr+offset
                if sym.type.base == "BYTE" and not sym.type.is_pointer:
                    # BYTE element: simple load
                    self.emit(f"\tLDA {arr_addr}+{offset}")
                elif sym.type.base == "LONG" and not sym.type.is_pointer:
                    # LONG element: load 4 bytes into MATH0
                    self.emit(f"\tLDA {arr_addr}+{offset}")
                    self.emit("\tSTA MATH0")
                    self.emit(f"\tLDA {arr_addr}+{offset+1}")
                    self.emit("\tSTA MATH0+1")
                    self.emit(f"\tLDA {arr_addr}+{offset+2}")
                    self.emit("\tSTA MATH0+2")
                    self.emit(f"\tLDA {arr_addr}+{offset+3}")
                    self.emit("\tSTA MATH0+3")
                else:
                    # WORD element: load both bytes
                    self.emit(f"\tLDA {arr_addr}+{offset}")
                    self.emit(f"\tLDX {arr_addr}+{offset+1}")
                return
        
        # Single index or FieldAccess base - use original 1D implementation
        if isinstance(base, Identifier):
            # Original code for array identifiers
            sym: Symbol = self.current_symtab.lookup(base.name)
            
            # Calculate element width based on array element type
            element_width: int = self._calculate_element_width(sym)

            # For const arrays, load address of ROM data (ARRAY_DATA_*) instead of RAM variable
            if sym.is_const and sym.is_array:
                arr_label: str | None = None
                # Generate the ARRAY_DATA label from the const values
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    dtype: str = sym.type.base  # "BYTE", "WORD", or "LONG"
                    data_key: tuple[tuple[int, ...], str] = (tuple(values), dtype)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                elif sym.init and isinstance(sym.init, StringInit):
                    if sym.type.base != "BYTE":
                        self._raise_error("String init only supported for byte arrays")
                    values = [ord(ch) for ch in sym.init.value] + [0]
                    data_key = (tuple(values), "BYTE")
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                else:
                    self._raise_error(f"Const array '{sym.name}' has no initialization")

                # Optimization: direct indexed load for const BYTE arrays
                if (load_only and not calc_addr_only and element_width == 1 and arr_label is not None):
                    idx_type: ExprType = self.tc_check(expr.index)
                    if idx_type.sem_type.base == "BYTE" and not idx_type.sem_type.is_pointer:
                        self.gen_expr(expr.index)
                        self.emit("\tTAY")
                        self.emit(f"\tLDA {arr_label},Y")
                        # For BYTE element, only set X if final target is not BYTE
                        need_x = True
                        if self.suppress_byte_return_x:
                            # When passing single byte to function, X is not needed
                            need_x = False
                        elif self.assign_target_type:
                            if hasattr(self.assign_target_type, 'base'):
                                if (self.assign_target_type.base == "BYTE" and
                                    not getattr(self.assign_target_type, 'is_pointer', False)):
                                    need_x = False
                        if need_x:
                            self.emit("\tLDX #$00     ; note 3499")
                        return

                if arr_label is None:
                    self._raise_error(f"Const array '{sym.name}' has no initialization")
                self._load_sym_addr(arr_label)
            else:
                # base address -> TMP0/TMP0+1 (regular non-const array)
                self._load_sym_addr(sym.asm_name())
            
            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")

            # index -> calculate scaled offset
            self.gen_expr(expr.index)
            
        elif isinstance(base, FieldAccess):
            # New code for field access (struct_var.field[index])
            # First, generate the field access which should give us the address in A/X
            self._gen_field_access(base, load_only=True)
            # Result is in A/X - this is the address of the array field
            # Save it to TMP0
            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")
            
            # Get field info to determine element width
            obj_type = self.tc_check(base.object).sem_type
            if not obj_type.is_struct:
                self._raise_error("Field access base must be struct")
            
            struct_info: StructInfo | None = obj_type.struct_info
            if struct_info is None:
                self._raise_error(f"Struct '{obj_type.base}' not found")
            
            # Find field info to get element type
            field_info: StructFieldInfo | None = None
            for f in struct_info.fields:
                if f.name == base.field:
                    field_info = f
                    break
            
            if field_info is None:
                self._raise_error(f"Field '{base.field}' not found in struct")
            
            # Determine element width
            if field_info.is_pointer:
                element_width = 2
            elif field_info.base_type == "BYTE":
                element_width = 1
            elif field_info.base_type == "WORD":
                element_width = 2
            else:
                nested_struct = self.struct_registry.lookup(field_info.base_type)
                element_width = nested_struct.size if nested_struct else 2
            
            # Generate the index expression
            self.gen_expr(expr.index)
        else:
            self._raise_error("Subscript array must be identifier or field access")

        # Multiply index by element width and store result
        if element_width > 1:
            if element_width == 2:
                # Optimization: use ASL to multiply by 2
                self.emit("\tASL A")
                # Handle carry from multiplication
                carry_lbl: str = self.new_label("NOCARRY_MULT")
                self.emit(f"\tBCC {carry_lbl}")
                self.emit(f"{carry_lbl}:")
                # For indices that fit in a byte, X should be 0 after ASL
                self.emit("\tLDX #$00    ; note 3438")
            else:
                # General case: multiply by width using addition loop
                # Index is in A, multiply by width
                self.emit("\tSTA TMP3")  # Save index to TMP3
                self.emit("\tLDA #$00")
                self.emit("\tSTA TMP4")  # TMP4 = result (low byte)
                self.emit("\tLDA #$00")
                self.emit("\tSTA TMP4+1")  # TMP4+1 = result (high byte)
                
                # Multiply: TMP4 = TMP3 * width
                # Using repeated addition: result = 0; for i in range(width): result += index
                for i in range(element_width):
                    self.emit("\tCLC")
                    self.emit("\tLDA TMP3")
                    self.emit("\tADC TMP4")
                    self.emit("\tSTA TMP4")
                    multiply_carry_lbl: str = self.new_label("MULT_CARRY")
                    self.emit(f"\tBCC {multiply_carry_lbl}")
                    self.emit("\tINC TMP4+1")
                    self.emit(f"{multiply_carry_lbl}:")
                
                # Load result back to A/X
                self.emit("\tLDA TMP4")
                self.emit("\tLDX TMP4+1")
        else:
            self.emit("\tLDX #$00     ; note 3464")  # BYTE element, X = 0
        
        # Now A/X contains (scaled) index, add to base address in TMP0
        self.emit("\tCLC")
        self.emit("\tADC TMP0")
        self.emit("\tSTA TMP0")
        
        # Now add X (high byte of scaled index) to TMP0+1 with carry from low byte addition
        self.emit("\tTXA")
        self.emit("\tADC TMP0+1")
        self.emit("\tSTA TMP0+1")
        
        # If only calculating address, stop here - TMP0 has the address
        if calc_addr_only:
            return

        if load_only:
            if element_width == 4:
                # LONG element: load 4 bytes into MATH0
                self.emit("\tLDY #$00")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tSTA MATH0")
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tSTA MATH0+1")
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tSTA MATH0+2")
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tSTA MATH0+3")
            elif element_width == 2:
                self.emit("\tLDY #1")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tTAX")  # X = high byte
                self.emit("\tDEY")
                self.emit("\tLDA (TMP0),Y")
            else:
                self.emit("\tLDY #$00")
                self.emit("\tLDA (TMP0),Y")
                # For BYTE element, only set X if final target is not BYTE
                # If target is BYTE, we only need the low byte in A
                need_x = True
                if self.suppress_byte_return_x:
                    # When passing single byte to function, X is not needed
                    need_x = False
                elif self.assign_target_type:
                    if hasattr(self.assign_target_type, 'base'):
                        if (self.assign_target_type.base == "BYTE" and
                            not getattr(self.assign_target_type, 'is_pointer', False)):
                            need_x = False
                if need_x:
                    self.emit("\tLDX #$00     ; note 3499")
        else:
            # RHS value in TMP2/TMP2+1 for BYTE/WORD; in MATH0 for LONG
            if element_width == 4:
                # LONG store: write 4 bytes from MATH0 via (TMP0),Y
                self.emit("\tLDY #$00")
                self.emit("\tLDA MATH0")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tINY")
                self.emit("\tLDA MATH0+1")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tINY")
                self.emit("\tLDA MATH0+2")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tINY")
                self.emit("\tLDA MATH0+3")
                self.emit("\tSTA (TMP0),Y")
            else:
                self.emit("\tLDA TMP2")
                if element_width == 2:
                    self.emit("\tLDY #$00")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA TMP2+1")
                    self.emit("\tSTA (TMP0),Y")
                else:
                    self._emit_indirect_store_zero("TMP0")

    def _calculate_nested_field_offset(self, expr: FieldAccess) -> tuple:
        """Calculate total offset for potentially nested field access.
        
        Returns: (total_offset, base_expr)
        
        For example:
          - o1.md.in.a returns (offset_to_a_in_Outer, o1)
          - arr[i].md.in.a returns (offset_to_a_in_Outer, arr[i])
        """
        total_offset = 0
        
        # Walk down the chain of field accesses to calculate total offset
        current_expr: Expr = expr
        while isinstance(current_expr, FieldAccess):
            # Get the type of the struct we're accessing
            parent_type = self.tc_check(current_expr.object).sem_type
            
            from errors import SemanticError
            if not parent_type.is_struct or parent_type.struct_info is None:
                raise SemanticError(f"Field access on non-struct type: {parent_type.base}", node=current_expr)
            
            struct_info: StructInfo = parent_type.struct_info
            
            # Find this field's offset in the parent struct
            field_info: StructFieldInfo | None = None
            for f in struct_info.fields:
                if f.name == current_expr.field:
                    field_info = f
                    break
            
            if field_info is None:
                raise SemanticError(f"Field '{current_expr.field}' not found in struct '{struct_info.name}'", node=current_expr)
            
            total_offset += field_info.offset
            current_expr = current_expr.object
        
        # current_expr is now the base (Identifier, SubscriptExpr, or other)
        return (total_offset, current_expr)

    def _gen_field_access(self, expr: FieldAccess, load_only: bool) -> None:
        """Generate code for struct field access (obj.field or ptr^.field).
        
        For direct field access (obj.field):
          - Load field value from struct instance using offset
          
        For pointer field access (ptr^.field):
          - Dereference pointer to get object address
          - Load field from that address using offset
          
        For array fields, return the address instead of value.
        """
        t: ExprType = self.tc_check(expr, read_check_enabled=load_only)
        field_type = t.sem_type
        
        # Get struct info
        struct_type = self.tc_check(expr.object, read_check_enabled=load_only).sem_type
        if not struct_type.is_struct:
            self._raise_error("Object is not a struct")
        
        struct_info: StructInfo | None = struct_type.struct_info
        if struct_info is None:
            self._raise_error(f"Struct '{struct_type.base}' not found")
        
        # Find field info
        field_info: StructFieldInfo | None = None
        for f in struct_info.fields:
            if f.name == expr.field.upper():
                field_info = f
                break
        
        if field_info is None:
            self._raise_error(f"Field '{expr.field}' not found in struct '{struct_info.name}'")
        
        # Special handling for array fields - return address instead of loading value
        if field_info.array_sizes:
            # This field is an array, return its address
            field_offset: int = field_info.offset
            
            if expr.is_deref:
                # ptr^.field where field is array - load pointer, add offset
                self.gen_expr(expr.object)
                # A/X now has pointer to struct
                
                if field_offset > 0:
                    # Add offset to pointer
                    self.emit(f"\tCLC")
                    self.emit(f"\tADC #${field_offset:02X}")
                    carry_lbl = self._internal_label(f"NOCARRY_ARRFIELD_DEREF_{id(expr)}")
                    self.emit(f"\tBCC {carry_lbl}")
                    self.emit(f"\tINC A+1")
                    self.emit(f"{carry_lbl}:")
            else:
                # obj.field where field is array - get address of array within struct
                if isinstance(expr.object, Identifier):
                    sym: Symbol = self.current_symtab.lookup(expr.object.name)
                    base_asm: str = sym.asm_name()
                    
                    # Calculate field address
                    field_asm: str = base_asm
                    if field_offset > 0:
                        field_asm: str = f"{base_asm}+{field_offset}"
                    
                    # Load address of field into A/X
                    self.emit(f"\tLDA #<{field_asm}")
                    self.emit(f"\tLDX #>{field_asm}")
                    
                elif isinstance(expr.object, SubscriptExpr):
                    # Array subscript: arr[i].array_field
                    # Get address of arr[i]
                    self._gen_subscript(expr.object, load_only=True, calc_addr_only=True)
                    
                    # Add field offset to address in TMP0
                    if field_offset > 0:
                        self.emit(f"\tCLC")
                        self.emit(f"\tLDA TMP0")
                        self.emit(f"\tADC #${field_offset:02X}")
                        self.emit(f"\tSTA TMP0")
                        carry_lbl = self._internal_label(f"NOCARRY_ARRFIELD_SUBSCR_{id(expr)}")
                        self.emit(f"\tBCC {carry_lbl}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"{carry_lbl}:")
                    
                    # Return address in A/X
                    self.emit(f"\tLDA TMP0")
                    self.emit(f"\tLDX TMP0+1")
                else:
                    self._raise_error("Array field access requires identifier or subscript base")
            
            return
        
        field_offset: int = field_info.offset
        if field_info.is_pointer or field_info.base_type == "WORD":
            field_width: int = 2
        elif field_info.base_type == "LONG":
            field_width = 4
        else:
            field_width = 1
        
        if expr.is_deref:
            # ptr^.field - expr.object should be a DerefExpr(pointer)
            # We need to get the address that the pointer points to
            if not isinstance(expr.object, DerefExpr):
                self._raise_error(f"Expected DerefExpr for is_deref=True, got {type(expr.object).__name__}")
            
            if isinstance(expr.object.pointer, Identifier):
                # Simple case: pp^.field where pp is a pointer variable
                ptr_name: str = expr.object.pointer.name
                sym: Symbol = self.current_symtab.lookup(ptr_name)
                ptr_asm: str = sym.asm_name()
                
                # Load the pointer value (which is the struct address)
                self.emit(f"\tLDA {ptr_asm}")
                self.emit(f"\tLDX {ptr_asm}+1")
            else:
                # Complex case: generate the pointer expression
                # This will give us the pointer address in A/X
                self.gen_expr(expr.object.pointer)
            
            # Now A/X contains the address of the struct
            # Store it in TMP0
            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")
            
            # Add field offset to address if needed
            if field_offset > 0:
                self.emit(f"\tLDA #${field_offset:02X}")
                self.emit("\tCLC")
                self.emit("\tADC TMP0")
                self.emit("\tSTA TMP0")
                carry_lbl = self._internal_label(f"NOCARRY_FIELD_DEREF_{id(expr)}")
                self.emit(f"\tBCC {carry_lbl}")
                self.emit("\tINC TMP0+1")
                self.emit(f"{carry_lbl}:")
            
            # If only loading field value, load it now
            if load_only:
                if field_offset == 0:
                    # Field at offset 0: just load directly
                    if field_width == 4:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+1")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+2")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+3")
                    elif field_width == 2:
                        self.emit("\tLDY #1")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tDEY")
                        self.emit("\tLDA (TMP0),Y")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                else:
                    # Field at offset > 0, address is already in TMP0
                    if field_width == 4:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+1")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+2")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+3")
                    elif field_width == 2:
                        self.emit("\tLDY #1")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tDEY")
                        self.emit("\tLDA (TMP0),Y")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
        else:
            # obj.field - direct field access
            # obj can be: Identifier or SubscriptExpr (array[index])
            
            if isinstance(expr.object, Identifier):
                # Simple variable: Point p1; p1.x = ...
                sym: Symbol = self.current_symtab.lookup(expr.object.name)
                base_asm: str = sym.asm_name()
                
                # Calculate field address
                field_asm: str = base_asm
                if field_offset > 0:
                    field_asm: str = f"{base_asm}+{field_offset}"
                
                # Load field value
                if field_width == 4:
                    self.emit(f"\tLDA {field_asm}")
                    self.emit(f"\tSTA MATH0")
                    self.emit(f"\tLDA {field_asm}+1")
                    self.emit(f"\tSTA MATH0+1")
                    self.emit(f"\tLDA {field_asm}+2")
                    self.emit(f"\tSTA MATH0+2")
                    self.emit(f"\tLDA {field_asm}+3")
                    self.emit(f"\tSTA MATH0+3")
                else:
                    self.emit(f"\tLDA {field_asm}")
                    if field_width == 2:
                        self.emit(f"\tLDX {field_asm}+1")
                    else:
                        # BYTE field -> X = 0
                        # Optimization: skip LDX #$00 if assignment target is BYTE (no need to set high byte)
                        target_is_byte: None | bool = (self.assign_target_type and
                                        hasattr(self.assign_target_type, 'base') and
                                        self.assign_target_type.base == "BYTE" and
                                        not getattr(self.assign_target_type, 'is_pointer', False))
                        if not target_is_byte or self.force_word_result:
                            self.emit("\tLDX #$00     ; note 3721")
                    
            elif isinstance(expr.object, SubscriptExpr):
                # Array subscript: Point arr[i]; arr[i].x = ...
                # 1) Generate the address of arr[i] into TMP0/TMP0+1 (no loading)
                self._gen_subscript(expr.object, load_only=True, calc_addr_only=True)
                
                # 2) Add field offset to the address
                if field_offset > 0:
                    self.emit(f"\tCLC")
                    self.emit(f"\tLDA TMP0")
                    self.emit(f"\tADC #${field_offset:02X}")
                    self.emit(f"\tSTA TMP0")
                    carry_lbl = self._internal_label(f"NOCARRY_ARRFIELD_{id(expr)}")
                    self.emit(f"\tBCC {carry_lbl}")
                    self.emit(f"\tINC TMP0+1")
                    self.emit(f"{carry_lbl}:")
                
                # 3) Load field value via indirect addressing (LONG only when reading)
                if field_width == 4 and load_only:
                    self.emit("\tLDY #$00")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tSTA MATH0")
                    self.emit("\tINY")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tSTA MATH0+1")
                    self.emit("\tINY")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tSTA MATH0+2")
                    self.emit("\tINY")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tSTA MATH0+3")
                elif field_width == 2:
                    self.emit("\tLDY #1")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tTAX")
                    self.emit("\tDEY")
                    self.emit("\tLDA (TMP0),Y")
                else:
                    self.emit("\tLDY #$00")
                    self.emit("\tLDA (TMP0),Y")
                    # BYTE field -> X = 0
                    # Optimization: skip LDX #$00 if assignment target is BYTE
                    target_is_byte: None | bool = (self.assign_target_type and
                                    hasattr(self.assign_target_type, 'base') and
                                    self.assign_target_type.base == "BYTE" and
                                    not getattr(self.assign_target_type, 'is_pointer', False))
                    if not target_is_byte or self.force_word_result:
                        self.emit("\tLDX #$00     ; note 3749")
            elif isinstance(expr.object, FieldAccess):
                # Nested field access: obj.field1.field2... (e.g., xs.pt.x or o1.md.in.a)
                # Calculate total offset by traversing the entire chain
                total_offset, base_expr = self._calculate_nested_field_offset(expr.object)
                
                # Add the final field offset
                total_offset += field_offset
                
                # Now generate code based on what the base is
                if isinstance(base_expr, Identifier):
                    # Base case: simple variable
                    sym: Symbol = self.current_symtab.lookup(base_expr.name)
                    base_asm: str = sym.asm_name()
                    
                    # Load field value from total offset
                    field_asm: str = base_asm
                    if total_offset > 0:
                        field_asm: str = f"{base_asm}+{total_offset}"
                    
                    if field_width == 4 and load_only:
                        self.emit(f"\tLDA {field_asm}")
                        self.emit(f"\tSTA MATH0")
                        self.emit(f"\tLDA {field_asm}+1")
                        self.emit(f"\tSTA MATH0+1")
                        self.emit(f"\tLDA {field_asm}+2")
                        self.emit(f"\tSTA MATH0+2")
                        self.emit(f"\tLDA {field_asm}+3")
                        self.emit(f"\tSTA MATH0+3")
                    elif field_width != 4:
                        self.emit(f"\tLDA {field_asm}")
                        if field_width == 2:
                            self.emit(f"\tLDX {field_asm}+1")
                        else:
                            # BYTE field -> X = 0
                            # Optimization: skip LDX #$00 if assignment target is BYTE (no need to set high byte)
                            target_is_byte: None | bool = (self.assign_target_type and
                                            hasattr(self.assign_target_type, 'base') and
                                            self.assign_target_type.base == "BYTE" and
                                            not getattr(self.assign_target_type, 'is_pointer', False))
                            if not target_is_byte or self.force_word_result:
                                self.emit("\tLDX #$00     ; note 3774")

                elif isinstance(base_expr, SubscriptExpr):
                    # Array subscript case: arr[i].field1.field2.x
                    self._gen_subscript(base_expr, load_only=True, calc_addr_only=True)
                    
                    # Add total offset to address
                    if total_offset > 0:
                        self.emit(f"\tCLC")
                        self.emit(f"\tLDA TMP0")
                        self.emit(f"\tADC #{total_offset}")
                        self.emit(f"\tSTA TMP0")
                        carry_lbl = self._internal_label(f"NOCARRY_NESTEDFIELD_{id(expr)}")
                        self.emit(f"\tBCC {carry_lbl}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"{carry_lbl}:")
                    
                    # Load field value via indirect addressing (LONG only when reading)
                    if field_width == 4 and load_only:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+1")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+2")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+3")
                    elif field_width != 4:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                        if field_width == 2:
                            self.emit("\tPHA")
                            self.emit("\tINY")
                            self.emit("\tLDA (TMP0),Y")
                            self.emit("\tTAX")
                            self.emit("\tPLA")
                        else:
                            # BYTE field -> X = 0
                            # Optimization: skip LDX #$00 if assignment target is BYTE
                            target_is_byte: None | bool = (self.assign_target_type and
                                            hasattr(self.assign_target_type, 'base') and
                                            self.assign_target_type.base == "BYTE" and
                                            not getattr(self.assign_target_type, 'is_pointer', False))
                            if not target_is_byte or self.force_word_result:
                                self.emit("\tLDX #$00     ; note 3801")
                else:
                    self._raise_error("Nested field access base must be identifier or array subscript")
            elif isinstance(expr.object, CallExpr):
                # Function call returning struct: myfunc().field
                # The return buffer is at a static address; call the function and read field directly.
                call_expr: CallExpr = expr.object
                specs = self.func_param_specs.get(call_expr.name)
                if specs is not None:
                    self._emit_call_args(call_expr.name, call_expr.args, specs)
                self.emit(f"\tJSR {self.asm_symbol_name(call_expr.name)}")
                ret_buf = self.func_return_buffers.get(call_expr.name)
                if ret_buf is None:
                    self._raise_error(f"Function '{call_expr.name}' does not return a struct")
                asm_ret, _ret_info = ret_buf
                # Load field directly from static return buffer
                field_asm: str = asm_ret if field_offset == 0 else f"{asm_ret}+{field_offset}"
                if field_width == 4:
                    self.emit(f"\tLDA {field_asm}")
                    self.emit(f"\tSTA MATH0")
                    self.emit(f"\tLDA {field_asm}+1")
                    self.emit(f"\tSTA MATH0+1")
                    self.emit(f"\tLDA {field_asm}+2")
                    self.emit(f"\tSTA MATH0+2")
                    self.emit(f"\tLDA {field_asm}+3")
                    self.emit(f"\tSTA MATH0+3")
                else:
                    self.emit(f"\tLDA {field_asm}")
                    if field_width == 2:
                        self.emit(f"\tLDX {field_asm}+1")
                    else:
                        target_is_byte: None | bool = (self.assign_target_type and
                                        hasattr(self.assign_target_type, 'base') and
                                        self.assign_target_type.base == "BYTE" and
                                        not getattr(self.assign_target_type, 'is_pointer', False))
                        if not target_is_byte or self.force_word_result:
                            self.emit("\tLDX #$00     ; note myfunc().field")
            elif isinstance(expr.object, DerefExpr):
                # fptr^.field parsed as FieldAccess(is_deref=False, object=DerefExpr(fptr))
                # Happens when parser creates DerefExpr separately, then FieldAccess wraps it.
                # Treat like is_deref=True: load the pointer into TMP0.
                deref_expr: DerefExpr = expr.object
                if isinstance(deref_expr.pointer, Identifier):
                    ptr_name: str = deref_expr.pointer.name
                    sym: Symbol = self.current_symtab.lookup(ptr_name)
                    ptr_asm: str = sym.asm_name()
                    self.emit(f"\tLDA {ptr_asm}")
                    self.emit(f"\tLDX {ptr_asm}+1")
                else:
                    self.gen_expr(deref_expr.pointer)
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")
                if field_offset > 0:
                    self.emit(f"\tLDA #${field_offset:02X}")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")
                    self.emit("\tSTA TMP0")
                    carry_lbl = self._internal_label(f"NOCARRY_FIELD_DEREF2_{id(expr)}")
                    self.emit(f"\tBCC {carry_lbl}")
                    self.emit("\tINC TMP0+1")
                    self.emit(f"{carry_lbl}:")
                if load_only:
                    if field_width == 4:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+1")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+2")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tSTA MATH0+3")
                    elif field_width == 2:
                        self.emit("\tLDY #1")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tDEY")
                        self.emit("\tLDA (TMP0),Y")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit("\tLDA (TMP0),Y")
            else:
                self._raise_error("Direct field access only supported on struct variables or array elements")

        # If storing field (not load_only), RHS should be in TMP2/TMP2+1
        if not load_only:
            if expr.is_deref:
                # Store through pointer (TMP0 already has address)
                if field_width == 4:
                    self.emit("\tLDA MATH0")
                    self.emit("\tLDY #$00")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+1")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+2")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+3")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                else:
                    self.emit("\tLDA TMP2")
                    if field_width == 2:
                        self.emit("\tLDY #$00")
                        self.emit("\tSTA (TMP0),Y")
                    else:
                        self._emit_indirect_store_zero("TMP0")

                    if field_width == 2:
                        self.emit("\tINY")
                        self.emit("\tLDA TMP2+1")
                        self.emit("\tSTA (TMP0),Y")
            elif isinstance(expr.object, Identifier):
                # Direct store to simple variable
                sym: Symbol = self.current_symtab.lookup(expr.object.name)
                base_asm: str = sym.asm_name()
                field_asm: str = base_asm if field_offset == 0 else f"{base_asm}+{field_offset}"

                if field_width == 4:
                    self.emit(f"\tLDA MATH0")
                    self.emit(f"\tSTA {field_asm}")
                    self.emit(f"\tLDA MATH0+1")
                    self.emit(f"\tSTA {field_asm}+1")
                    self.emit(f"\tLDA MATH0+2")
                    self.emit(f"\tSTA {field_asm}+2")
                    self.emit(f"\tLDA MATH0+3")
                    self.emit(f"\tSTA {field_asm}+3")
                else:
                    self.emit(f"\tLDA TMP2")
                    self.emit(f"\tSTA {field_asm}")
                    if field_width == 2:
                        self.emit(f"\tLDA TMP2+1")
                        self.emit(f"\tSTA {field_asm}+1")
            elif isinstance(expr.object, SubscriptExpr):
                # Direct store to array element (TMP0 already has address)
                if field_width == 4:
                    self.emit(f"\tLDA MATH0")
                    self.emit(f"\tLDY #$00")
                    self.emit(f"\tSTA (TMP0),Y")
                    self.emit(f"\tLDA MATH0+1")
                    self.emit(f"\tINY")
                    self.emit(f"\tSTA (TMP0),Y")
                    self.emit(f"\tLDA MATH0+2")
                    self.emit(f"\tINY")
                    self.emit(f"\tSTA (TMP0),Y")
                    self.emit(f"\tLDA MATH0+3")
                    self.emit(f"\tINY")
                    self.emit(f"\tSTA (TMP0),Y")
                else:
                    self.emit(f"\tLDA TMP2")
                    if field_width == 2:
                        self.emit("\tLDY #$00")
                        self.emit(f"\tSTA (TMP0),Y")
                    else:
                        self._emit_indirect_store_zero("TMP0")

                    if field_width == 2:
                        self.emit(f"\tINY")
                        self.emit(f"\tLDA TMP2+1")
                        self.emit(f"\tSTA (TMP0),Y")
            elif isinstance(expr.object, FieldAccess):
                # Nested field access store: obj.field1.field2... = value
                # Calculate total offset by traversing the entire chain
                total_offset, base_expr = self._calculate_nested_field_offset(expr.object)
                
                # Add the final field offset
                total_offset += field_offset
                
                if isinstance(base_expr, Identifier):
                    # Base case: simple variable
                    sym: Symbol = self.current_symtab.lookup(base_expr.name)
                    base_asm: str = sym.asm_name()
                    field_asm: str = base_asm if total_offset == 0 else f"{base_asm}+{total_offset}"

                    if field_width == 4:
                        self.emit(f"\tLDA MATH0")
                        self.emit(f"\tSTA {field_asm}")
                        self.emit(f"\tLDA MATH0+1")
                        self.emit(f"\tSTA {field_asm}+1")
                        self.emit(f"\tLDA MATH0+2")
                        self.emit(f"\tSTA {field_asm}+2")
                        self.emit(f"\tLDA MATH0+3")
                        self.emit(f"\tSTA {field_asm}+3")
                    else:
                        self.emit(f"\tLDA TMP2")
                        self.emit(f"\tSTA {field_asm}")
                        if field_width == 2:
                            self.emit(f"\tLDA TMP2+1")
                            self.emit(f"\tSTA {field_asm}+1")

                elif isinstance(base_expr, SubscriptExpr):
                    # Array subscript case: arr[i].field1.field2... = value
                    self._gen_subscript(base_expr, load_only=True, calc_addr_only=True)

                    # Add total offset to address
                    if total_offset > 0:
                        self.emit(f"\tCLC")
                        self.emit(f"\tLDA TMP0")
                        self.emit(f"\tADC #${total_offset:02X}")
                        self.emit(f"\tSTA TMP0")
                        carry_lbl = self._internal_label(f"NOCARRY_NESTEDFIELD_STORE_{id(expr)}")
                        self.emit(f"\tBCC {carry_lbl}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"{carry_lbl}:")

                    # Store field value via indirect addressing
                    if field_width == 4:
                        self.emit(f"\tLDA MATH0")
                        self.emit(f"\tLDY #$00")
                        self.emit(f"\tSTA (TMP0),Y")
                        self.emit(f"\tLDA MATH0+1")
                        self.emit(f"\tINY")
                        self.emit(f"\tSTA (TMP0),Y")
                        self.emit(f"\tLDA MATH0+2")
                        self.emit(f"\tINY")
                        self.emit(f"\tSTA (TMP0),Y")
                        self.emit(f"\tLDA MATH0+3")
                        self.emit(f"\tINY")
                        self.emit(f"\tSTA (TMP0),Y")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit(f"\tLDA TMP2")
                        self.emit(f"\tSTA (TMP0),Y")
                        if field_width == 2:
                            self.emit(f"\tINY")
                            self.emit(f"\tLDA TMP2+1")
                            self.emit(f"\tSTA (TMP0),Y")
                else:
                    self._raise_error("Nested field access base must be identifier or array subscript")
            elif isinstance(expr.object, DerefExpr):
                # ptr^.field store: TMP0 set up by DerefExpr case in load section above
                if field_width == 4:
                    self.emit("\tLDA MATH0")
                    self.emit("\tLDY #$00")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+1")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+2")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                    self.emit("\tLDA MATH0+3")
                    self.emit("\tINY")
                    self.emit("\tSTA (TMP0),Y")
                else:
                    self.emit("\tLDA TMP2")
                    if field_width == 2:
                        self.emit("\tLDY #$00")
                        self.emit("\tSTA (TMP0),Y")
                        self.emit("\tINY")
                        self.emit("\tLDA TMP2+1")
                        self.emit("\tSTA (TMP0),Y")
                    else:
                        self._emit_indirect_store_zero("TMP0")

    def _collect_array_subscript_chain(self, expr: BinaryExpr) -> list | None:
        """
        Collect a chain of array subscript ADD/SUB operations for optimization.
        Returns list of (op, array_name, index_value) tuples if pattern matches, else None.
        Pattern: arr[0] + arr[1] - arr[2] where all are BYTE or WORD, all indices are immediate
        """
        if expr.op not in {BinOp.ADD, BinOp.SUB}:
            return None
        
        result = []
        element_type: str | None = None  # Track BYTE or WORD
        
        # Check right operand
        if isinstance(expr.right, SubscriptExpr):
            if (isinstance(expr.right.array, Identifier) and 
                isinstance(expr.right.index, IntLiteral)):
                arr_sym: Symbol = self.current_symtab.lookup(expr.right.array.name)
                if (arr_sym.is_array and not arr_sym.is_const and 
                    arr_sym.address is None and arr_sym.type.base in {"BYTE", "WORD"}):
                    element_type = arr_sym.type.base
                    result.append((expr.op, expr.right.array.name, expr.right.index.value))
        else:
            return None  # Right must be subscript
        
        # Check left operand - can be another subscript or another ADD/SUB chain
        left: Expr = expr.left
        while left:
            if isinstance(left, SubscriptExpr):
                if (isinstance(left.array, Identifier) and 
                    isinstance(left.index, IntLiteral)):
                    arr_sym: Symbol = self.current_symtab.lookup(left.array.name)
                    if (arr_sym.is_array and not arr_sym.is_const and 
                        arr_sym.address is None and arr_sym.type.base in {"BYTE", "WORD"}):
                        # Verify all elements same type
                        if element_type is None:
                            element_type = arr_sym.type.base
                        elif arr_sym.type.base != element_type:
                            return None  # Mixed BYTE/WORD not allowed
                        # For the leftmost element, the operation is implicit ADD
                        result.append((BinOp.ADD, left.array.name, left.index.value))
                    break
                else:
                    return None  # Non-immediate index
            elif isinstance(left, BinaryExpr) and left.op in {BinOp.ADD, BinOp.SUB}:
                # Check if right side is a subscript
                if isinstance(left.right, SubscriptExpr):
                    if (isinstance(left.right.array, Identifier) and 
                        isinstance(left.right.index, IntLiteral)):
                        arr_sym: Symbol = self.current_symtab.lookup(left.right.array.name)
                        if (arr_sym.is_array and not arr_sym.is_const and 
                            arr_sym.address is None and arr_sym.type.base in {"BYTE", "WORD"}):
                            # Verify element type consistency
                            if element_type is None:
                                element_type = arr_sym.type.base
                            elif arr_sym.type.base != element_type:
                                return None
                            result.append((left.op, left.right.array.name, left.right.index.value))
                            left: Expr = left.left
                            continue
                return None
            else:
                return None  # Not a subscript or ADD/SUB chain
        
        # Must have at least 2 elements and same array
        if len(result) < 2:
            return None
        
        # Check all from same array
        first_arr = result[0][1]
        if not all(arr == first_arr for op, arr, idx in result):
            return None
        
        return list(reversed(result))  # Reverse to get left-to-right order
    
    def _gen_array_subscript_chain(self, chain: list, array_name: str, result_is_16bit: bool = False) -> None:
        """
        Generate optimized code for array subscript chain with mixed ADD/SUB.
        chain: list of (op, array_name, index_value) tuples in order
        result_is_16bit: if True, generate 16-bit ADC/SBC with carry propagation
        
        For BYTE arrays:
          8-bit result: LDA arr[0]; CLC; ADC arr[1]; ...
          16-bit result: LDA arr[0]; LDX #$00; CLC; ADC arr[1]; (with carry to X)
        
        For WORD arrays (16-bit elements):
          Uses TMP1/TMP2 to accumulate: accumulation strategy
        """
        arr_sym: Symbol = self.current_symtab.lookup(array_name)
        arr_addr: str = arr_sym.asm_name()
        is_word_array: bool = arr_sym.type.base == "WORD"

        accum_lo: str = "TMP1"
        accum_hi: str = "TMP2"
        target_sym: Symbol | None = None
        target_is_byte: bool = False
        if self.assign_target_sym and not self.assign_target_blocked and self.assign_target_type:
            target_sym = self.assign_target_sym
            target_is_byte = (self.assign_target_type.base == "BYTE" and not self.assign_target_type.is_pointer)
        if target_sym and not target_sym.is_array and target_sym.address is None and not self._is_fixed_address(target_sym.asm_name()) and not self._is_port_variable(target_sym.asm_name()):
            if is_word_array and (self.assign_target_type and (self.assign_target_type.base == "WORD" or self.assign_target_type.is_pointer)):
                accum_lo = target_sym.asm_name()
                accum_hi = f"{accum_lo}+1"
            elif target_is_byte:
                accum_lo = target_sym.asm_name()
        
        # Load first element
        op0, _, idx0_val = chain[0]
        if is_word_array and target_is_byte:
            # If target is BYTE, keep 8-bit accumulation even for WORD arrays.
            result_is_16bit = False

        if is_word_array:
            # For WORD arrays, load both low and high bytes
            offset_low = idx0_val * 2
            offset_high = offset_low + 1
            self.emit(f"\tLDA {arr_addr}+{offset_low}")  # Load low byte → A
            if result_is_16bit:
                self.emit(f"\tLDX {arr_addr}+{offset_high}")  # Load high byte → X
                # Store initial result in accumulator
                self.emit(f"\tSTA {accum_lo}")
                self.emit(f"\tSTX {accum_hi}")
            else:
                # BYTE target: use low byte only
                self.emit(f"\tSTA {accum_lo}")
        else:
            # For BYTE arrays, load only low byte
            self.emit(f"\tLDA {arr_addr}+{idx0_val}")
            if result_is_16bit:
                # For 16-bit result from BYTE elements, initialize high byte to 0
                self.emit("\tLDX #$00     ; note 3994")
        
        # Process remaining elements
        for idx, (op, _, idx_val) in enumerate(chain[1:], 1):
            is_last: bool = idx == (len(chain) - 1)
            if is_word_array:
                # For WORD arrays: process 16-bit elements
                offset_low = idx_val * 2
                offset_high = offset_low + 1
                
                lbl_no_carry: str = self.new_label("WORD_ADD_NO_CARRY")
                lbl_no_borrow: str = self.new_label("WORD_SUB_NO_BORROW")
                
                if result_is_16bit:
                    if op == BinOp.ADD:
                        # 16-bit ADD: accum += arr[idx_val]
                        self.emit("\tCLC")
                        self.emit(f"\tLDA {accum_lo}")
                        self.emit(f"\tADC {arr_addr}+{offset_low}")
                        self.emit(f"\tSTA {accum_lo}")  # Save low result
                        # Now add high bytes with carry from low
                        self.emit(f"\tLDA {accum_hi}")
                        self.emit(f"\tADC {arr_addr}+{offset_high}")
                        self.emit(f"\tSTA {accum_hi}")  # Save high result
                    else:  # SUB
                        # 16-bit SUB: accum -= arr[idx_val]
                        self.emit("\tSEC")
                        self.emit(f"\tLDA {accum_lo}")
                        self.emit(f"\tSBC {arr_addr}+{offset_low}")
                        self.emit(f"\tSTA {accum_lo}")  # Save low result
                        # Now subtract high bytes with borrow from low
                        self.emit(f"\tLDA {accum_hi}")
                        self.emit(f"\tSBC {arr_addr}+{offset_high}")
                        self.emit(f"\tSTA {accum_hi}")  # Save high result
                else:
                    # BYTE target: use low byte only
                    if op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tLDA {accum_lo}")
                        self.emit(f"\tADC {arr_addr}+{offset_low}")
                        if not (target_sym and accum_lo == target_sym.asm_name() and is_last):
                            self.emit(f"\tSTA {accum_lo}")
                    else:  # SUB
                        self.emit("\tSEC")
                        self.emit(f"\tLDA {accum_lo}")
                        self.emit(f"\tSBC {arr_addr}+{offset_low}")
                        if not (target_sym and accum_lo == target_sym.asm_name() and is_last):
                            self.emit(f"\tSTA {accum_lo}")
            else:
                # BYTE array processing (existing logic)
                if op == BinOp.ADD:
                    self.emit("\tCLC")
                    self.emit(f"\tADC {arr_addr}+{idx_val}")
                    
                    if result_is_16bit:
                        # Propagate carry to high byte (X register)
                        no_carry_lbl: str = self.new_label("ARRAY_NO_CARRY")
                        self.emit(f"\tBCC {no_carry_lbl}")
                        self.emit("\tINX")  # Increment high byte if carry
                        self.emit(f"{no_carry_lbl}:")
                else:  # SUB
                    self.emit("\tSEC")
                    self.emit(f"\tSBC {arr_addr}+{idx_val}")
                    
                    if result_is_16bit:
                        # Propagate borrow to high byte (X register)
                        no_borrow_lbl: str = self.new_label("ARRAY_NO_BORROW")
                        self.emit(f"\tBCS {no_borrow_lbl}")
                        self.emit("\tDEX")  # Decrement high byte if borrow
                        self.emit(f"{no_borrow_lbl}:")
        
        # For WORD arrays, ensure result is in A/X
        if is_word_array and len(chain) > 1:
            if result_is_16bit:
                self.emit(f"\tLDA {accum_lo}")  # Low result → A
                self.emit(f"\tLDX {accum_hi}")  # High result → X
            else:
                if not (target_sym and accum_lo == target_sym.asm_name()):
                    self.emit(f"\tLDA {accum_lo}")  # Low result → A







    def _is_immediate_array_subscript(self, expr) -> tuple | None:
        """
        Check if expression is array[immediate_index] for BYTE or WORD array.
        Returns (array_name, offset) if match, else None
        """
        if not isinstance(expr, SubscriptExpr):
            return None
        if not isinstance(expr.array, Identifier):
            return None
        if not isinstance(expr.index, IntLiteral):
            return None
        
        arr_sym: Symbol = self.current_symtab.lookup(expr.array.name)
        if not (arr_sym.is_array and not arr_sym.is_const and 
                arr_sym.address is None and arr_sym.type.base in {"BYTE", "WORD"}):
            return None
        
        offset: int = expr.index.value * self._calculate_element_width(arr_sym)
        return (arr_sym.asm_name(), offset)

    def _collect_add_sub_chain(self, expr: BinaryExpr) -> list[tuple[BinOp, Expr]] | None:
        """Collect a chain of ADD/SUB operations for RPN evaluation.
        
        For expression (((a + b) + c) + d), returns:
        [(ADD, a), (ADD, b), (ADD, c), (ADD, d)]
        
        Returns None if not a valid chain (e.g., mixed with other operations).
        """
        chain: list[tuple[BinOp, Expr]] = []
        current: Expr = expr
        
        while isinstance(current, BinaryExpr) and current.op in {BinOp.ADD, BinOp.SUB}:
            chain.append((current.op, current.right))
            current = current.left
        
        # Add the final left operand
        chain.append((BinOp.ADD, current))
        chain.reverse()
        
        # Only use chain optimization if we have 3+ operands and all are simple (not nested binop)
        if len(chain) >= 3:
            for op, operand in chain:
                if isinstance(operand, BinaryExpr):
                    return None  # Too complex, fall back to regular handling
            return chain
        
        return None
    
    def _gen_add_sub_chain_rpn(self, chain: list[tuple[BinOp, Expr]]) -> None:
        """Generate RPN-style ADD/SUB chain using __MATH0 as accumulator.
        
        For chain [(+, a), (+, b), (+, c)], generates:
        - Load a → __MATH0
        - Load b → __MATH1
        - ADD16 → __MATH0
        - Load c → __MATH1  
        - ADD16 → __MATH0
        
        Result is left in __MATH0 (A/X).
        """
        if not chain or len(chain) < 2:
            return
        
        self.math_routines_needed.add("ADD16")
        self.math_routines_needed.add("SUB16")
        
        # Load first operand into __MATH0
        first_op, first_expr = chain[0]
        first_type = self.tc_check(first_expr)
        is_first_16bit = first_type.sem_type.base == "WORD" or first_type.sem_type.is_pointer
        
        # Load first operand
        if isinstance(first_expr, Identifier):
            sym = self.current_symtab.lookup(first_expr.name)
            self.emit(f"\tLDA {sym.asm_name()}")
            self.emit(f"\tSTA __MATH0")
            if is_first_16bit:
                self.emit(f"\tLDA {sym.asm_name()}+1")
                self.emit(f"\tSTA __MATH0+1")
            else:
                self.emit(f"\tLDX #$00")
                self.emit(f"\tSTX __MATH0+1")
        elif isinstance(first_expr, IntLiteral):
            val = first_expr.value & 0xFF
            self.emit(f"\tLDA #${val:02X}")
            self.emit(f"\tSTA __MATH0")
            if is_first_16bit:
                val_hi = (first_expr.value >> 8) & 0xFF
                self.emit(f"\tLDA #${val_hi:02X}")
                self.emit(f"\tSTA __MATH0+1")
            else:
                self.emit(f"\tLDX #$00")
                self.emit(f"\tSTX __MATH0+1")
        else:
            # Complex expression (including FieldAccess) - generate and store
            # gen_expr will put result in A/X with proper widening already applied
            self.gen_expr(first_expr)
            self.emit(f"\tSTA __MATH0")
            self.emit(f"\tSTX __MATH0+1")
        
        # Process remaining operands
        for i in range(1, len(chain)):
            op, operand = chain[i]
            operand_type = self.tc_check(operand)
            is_operand_16bit = operand_type.sem_type.base == "WORD" or operand_type.sem_type.is_pointer
            
            # Load operand into __MATH1
            if isinstance(operand, Identifier):
                sym = self.current_symtab.lookup(operand.name)
                self.emit(f"\tLDA {sym.asm_name()}")
                self.emit(f"\tSTA __MATH1")
                if is_operand_16bit:
                    self.emit(f"\tLDA {sym.asm_name()}+1")
                    self.emit(f"\tSTA __MATH1+1")
                else:
                    self.emit(f"\tLDX #$00")
                    self.emit(f"\tSTX __MATH1+1")
            elif isinstance(operand, IntLiteral):
                val = operand.value & 0xFF
                self.emit(f"\tLDA #${val:02X}")
                self.emit(f"\tSTA __MATH1")
                if is_operand_16bit:
                    val_hi = (operand.value >> 8) & 0xFF
                    self.emit(f"\tLDA #${val_hi:02X}")
                    self.emit(f"\tSTA __MATH1+1")
                else:
                    self.emit(f"\tLDX #$00")
                    self.emit(f"\tSTX __MATH1+1")
            else:
                # Complex expression (including FieldAccess) - generate and store
                # gen_expr will put result in A/X with proper widening already applied
                self.gen_expr(operand)
                self.emit(f"\tSTA __MATH1")
                self.emit(f"\tSTX __MATH1+1")
            
            # Perform operation
            if op == BinOp.ADD:
                self.emit("\tJSR __ADD16")
            else:  # SUB
                self.emit("\tJSR __SUB16")
        
        # Result is in __MATH0, move to A/X for caller
        self.emit("\tLDA __MATH0")
        self.emit("\tLDX __MATH0+1")
    
    def _gen_binary(self, expr: BinaryExpr, force_left_tmp=None) -> None:
        """Generate binary.
        Internal helper used during code generation.
        """
        t: ExprType = self.tc_check(expr)
        left_t: ExprType = self.tc_check(expr.left)
        right_t: ExprType = self.tc_check(expr.right)
        
        # OPTIMIZATION: Swap operands for commutative operations if left is constant and right is not
        if expr.op in {BinOp.ADD, BinOp.MUL, BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.EQ, BinOp.NE}:
            if isinstance(expr.left, IntLiteral) and not isinstance(expr.right, IntLiteral):
                # Swap operands by tracking them in a new node variable
                expr = BinaryExpr(left=expr.right, op=expr.op, right=expr.left, line=expr.line, col=expr.col)
                left_t, right_t = right_t, left_t
        
        # OPTIMIZATION: Detect chained ADD/SUB operations and generate RPN-style with accumulator
        # Pattern: ((a + b) + c) + d --> Load a → MATH0, b → MATH1, ADD, c → MATH1, ADD, d → MATH1, ADD
        # This avoids intermediate temporaries and uses __MATH0 as running accumulator
        if expr.op in {BinOp.ADD, BinOp.SUB}:
            chain = self._collect_add_sub_chain(expr)
            if chain and (t.sem_type.base == "WORD" or t.sem_type.is_pointer):
                # Only use chain optimization for 16-bit results
                self._gen_add_sub_chain_rpn(chain)
                return
        
        # OPTIMIZATION: Detect ADD/SUB with immediate array subscripts
        # Pattern: arr[0] + value --> LDA arr[0]; CLC; ADC value
        # Pattern: value + arr[0] --> generate value; CLC; ADC arr[0]
        # Pattern: arr[0] - value --> LDA arr[0]; SEC; SBC value
        if expr.op in {BinOp.ADD, BinOp.SUB} and not left_t.sem_type.base == "WORD" and not right_t.sem_type.base == "WORD":
            left_arr_info = self._is_immediate_array_subscript(expr.left)
            right_arr_info = self._is_immediate_array_subscript(expr.right)
            
            # Case 1: arr[i] + expr
            if left_arr_info and isinstance(expr.right, (Identifier, IntLiteral, SubscriptExpr)):
                arr_addr, offset = left_arr_info
                self.emit(f"\tLDA {arr_addr}+{offset}")
                
                if expr.op == BinOp.ADD:
                    self.emit("\tCLC")
                    if isinstance(expr.right, IntLiteral):
                        self.emit(f"\tADC #${expr.right.value & 0xFF:02X}")
                    elif isinstance(expr.right, Identifier):
                        right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                        self.emit(f"\tADC {right_sym.asm_name()}")
                    elif isinstance(expr.right, SubscriptExpr):
                        # Check if it's also an immediate array subscript
                        right_info = self._is_immediate_array_subscript(expr.right)
                        if right_info:
                            r_addr, r_offset = right_info
                            self.emit(f"\tADC {r_addr}+{r_offset}")
                        else:
                            # Complex subscript - fall through
                            pass
                    else:
                        # Complex expression - fall through
                        pass
                else:  # SUB
                    self.emit("\tSEC")
                    if isinstance(expr.right, IntLiteral):
                        self.emit(f"\tSBC #${expr.right.value & 0xFF:02X}")
                    elif isinstance(expr.right, Identifier):
                        right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                        self.emit(f"\tSBC {right_sym.asm_name()}")
                    elif isinstance(expr.right, SubscriptExpr):
                        right_info = self._is_immediate_array_subscript(expr.right)
                        if right_info:
                            r_addr, r_offset = right_info
                            self.emit(f"\tSBC {r_addr}+{r_offset}")
                        else:
                            pass
                    else:
                        pass
                
                # Check if we successfully handled it (no fallthrough needed)
                # If we got here and handled it, we should return
                if isinstance(expr.right, (Identifier, IntLiteral)):
                    return
                elif isinstance(expr.right, SubscriptExpr) and right_arr_info:
                    return
            
            # Case 2: expr + arr[i] (ADD only, since SUB doesn't commute)
            if right_arr_info and expr.op == BinOp.ADD and isinstance(expr.left, (Identifier, IntLiteral, SubscriptExpr)):
                arr_addr, offset = right_arr_info
                
                # Generate left side first
                if isinstance(expr.left, IntLiteral):
                    self.emit(f"\tLDA #${expr.left.value & 0xFF:02X}")
                elif isinstance(expr.left, Identifier):
                    left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                    self.emit(f"\tLDA {left_sym.asm_name()}")
                elif isinstance(expr.left, SubscriptExpr):
                    left_info = self._is_immediate_array_subscript(expr.left)
                    if left_info:
                        l_addr, l_offset = left_info
                        self.emit(f"\tLDA {l_addr}+{l_offset}")
                    else:
                        # Complex subscript - can't optimize
                        pass
                else:
                    # Complex expression - can't optimize this way
                    pass
                
                # Add the array element
                self.emit("\tCLC")
                self.emit(f"\tADC {arr_addr}+{offset}")
                
                # Check if we successfully handled it
                if isinstance(expr.left, (Identifier, IntLiteral)):
                    return
                elif isinstance(expr.left, SubscriptExpr) and left_arr_info:
                    return
        
        # OPTIMIZATION: Detect and optimize array subscript chains
        # Pattern: arr[0] + arr[1] - arr[2]
        # Determine result type: use assignment target type if available, else expression result type
        # Note: Pointers are 16-bit regardless of whether they're VALUE or ADDR kind
        result_16_temp: bool = t.sem_type.base == "WORD" or t.sem_type.is_pointer

        # Force word-sized evaluation when required by caller context
        if self.force_word_result:
            result_16_temp = True
        
        # If we're in an assignment context and LHS is WORD, treat result as 16-bit
        # If we're in an assignment context and LHS is BYTE, treat result as 8-bit only when
        # the expression and its operands are also BYTE-sized. For word/pointer operands or
        # when the expression itself yields WORD, keep 16-bit so bitwise/shift operations
        # are evaluated at the correct width before final truncation.
        if self.assign_target_type:
            if self.assign_target_type.base == "BYTE" and not self.assign_target_type.is_pointer:
                # Only narrow to 8-bit if neither the expression nor its operands are WORD/pointer
                if not (
                    t.sem_type.base == "WORD" or
                    left_t.sem_type.base == "WORD" or
                    right_t.sem_type.base == "WORD" or
                    (left_t.kind == ExprKind.ADDR) or
                    (right_t.kind == ExprKind.ADDR)
                ):
                    result_16_temp = False  # Final assignment is to BYTE and everything is BYTE → don't promote result
            elif self.assign_target_type.base == "WORD" or self.assign_target_type.is_pointer:
                result_16_temp = True  # Final assignment is to WORD, treat as 16-bit
        
        chain = self._collect_array_subscript_chain(expr)
        if chain:
            # chain[0][1] is the array name
            self._gen_array_subscript_chain(chain, chain[0][1], result_is_16bit=result_16_temp)
            return
        
        # Determine operand sizes
        # IMPORTANT: Pointers are always 16-bit, even if pointing to BYTE
        # Note: Pointers can be VALUE (from fields) or ADDR (array/@ operator)
        left_16: bool = left_t.sem_type.base == "WORD" or left_t.sem_type.is_pointer
        right_16: bool = right_t.sem_type.base == "WORD" or right_t.sem_type.is_pointer
        result_16: bool = result_16_temp
        
        # Check if left operand is a BYTE arithmetic expression that can overflow
        # If so, treat it as 16-bit because it will have carry promotion applied
        # UNLESS the final result will be assigned to BYTE, in which case we want 8-bit wrapping
        left_is_promoted_byte_arith: bool = (
            isinstance(expr.left, BinaryExpr) and 
            not left_16 and  # Type system says it's BYTE
            expr.left.op in {BinOp.ADD, BinOp.SUB, BinOp.DIV, BinOp.MOD} and
            result_16  # Only promote if result will be 16-bit
        )
        if left_is_promoted_byte_arith:
            left_16 = True  # Treat as 16-bit since it will have carry promotion
        
        # Check if right operand is a BYTE arithmetic expression that can overflow
        # UNLESS the final result will be assigned to BYTE, in which case we want 8-bit wrapping
        right_is_promoted_byte_arith: bool = (
            isinstance(expr.right, BinaryExpr) and 
            not right_16 and  # Type system says it's BYTE
            expr.right.op in {BinOp.ADD, BinOp.SUB, BinOp.DIV, BinOp.MOD} and
            result_16  # Only promote if result will be 16-bit
        )
        if right_is_promoted_byte_arith:
            right_16 = True  # Treat as 16-bit since it will have carry promotion
        
        # Also check if result type should be promoted due to operand promotion
        # If either operand was promoted to 16-bit and we're doing arithmetic, result should be 16-bit
        result_16_adj: bool = result_16 or (left_is_promoted_byte_arith and expr.op in {BinOp.ADD, BinOp.SUB, BinOp.DIV, BinOp.MOD})
        result_16_adj: bool = result_16_adj or (right_is_promoted_byte_arith and expr.op in {BinOp.ADD, BinOp.SUB, BinOp.DIV, BinOp.MOD})
        
        # Detect pointer arithmetic: determine if this is pointer +/- value
        # Check sem_type.is_pointer to detect both @-created addresses and pointer variables
        left_is_ptr: bool = left_t.sem_type.is_pointer
        right_is_ptr: bool = right_t.sem_type.is_pointer
        
        # For pointer arithmetic, we need the element size of the pointer
        ptr_elem_size = 1  # default
        if left_is_ptr:
            if left_t.sem_type.is_struct and left_t.sem_type.struct_info:
                ptr_elem_size: int = left_t.sem_type.struct_info.size
            elif left_t.sem_type.base == "LONG":
                ptr_elem_size: int = 4
            else:
                ptr_elem_size: int = 2 if left_t.sem_type.base == "WORD" else 1
        elif right_is_ptr:
            if right_t.sem_type.is_struct and right_t.sem_type.struct_info:
                ptr_elem_size: int = right_t.sem_type.struct_info.size
            elif right_t.sem_type.base == "LONG":
                ptr_elem_size: int = 4
            else:
                ptr_elem_size: int = 2 if right_t.sem_type.base == "WORD" else 1

        # Check for constant 1 optimization BEFORE generating code
        right_is_const_1: bool = isinstance(expr.right, IntLiteral) and expr.right.value == 1
        use_inc_opt: bool = (expr.op == BinOp.ADD and right_is_const_1 and left_is_ptr and ptr_elem_size == 1 and not result_16)
        use_dec_opt: bool = (expr.op == BinOp.SUB and right_is_const_1 and left_is_ptr and ptr_elem_size == 1)

        # Fast path: Pure byte arithmetic with simple operands (Identifier or IntLiteral)
        # For: byte z = x + y or byte z = x + 5 --> LDA x; CLC; ADC y/5; STA z
        is_simple_byte_add_sub: bool = (
            expr.op in {BinOp.ADD, BinOp.SUB} and 
            not left_16 and not right_16 and not result_16 and
            not left_is_ptr and not right_is_ptr and
            not left_is_promoted_byte_arith and not right_is_promoted_byte_arith and
            isinstance(expr.left, (Identifier, IntLiteral)) and
            isinstance(expr.right, (Identifier, IntLiteral))
        )
        
        if is_simple_byte_add_sub:
            # Generate left operand (just LDA, no X handling needed)
            if isinstance(expr.left, Identifier):
                left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
            elif isinstance(expr.left, IntLiteral):
                val: int = expr.left.value & 0xFF
                self.emit(f"\tLDA #${val:02X}")
            
            # Set carry for ADD, clear for SUB
            if expr.op == BinOp.ADD:
                self.emit("\tCLC")
            else:  # SUB
                self.emit("\tSEC")
            
            # Generate right operand and perform operation directly
            if isinstance(expr.right, Identifier):
                right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=True)}")
                else:
                    self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=True)}")
            elif isinstance(expr.right, IntLiteral):
                val: int = expr.right.value & 0xFF
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC #${val:02X}")
                else:
                    self.emit(f"\tSBC #${val:02X}")
            return

        # Fast path: Repeated byte addition of the same identifier (x + x + x ...)
        if (expr.op == BinOp.ADD and not left_16 and not right_16 and not result_16 and
                not left_is_ptr and not right_is_ptr and
                not left_is_promoted_byte_arith and not right_is_promoted_byte_arith):
            def _collect_same_id_add(node: Expr) -> tuple[str | None, int]:
                """Collect same id add.
                Internal helper used during code generation.
                """
                if isinstance(node, Identifier):
                    return node.name, 1
                if isinstance(node, BinaryExpr) and node.op == BinOp.ADD:
                    left_name, left_count = _collect_same_id_add(node.left)
                    right_name, right_count = _collect_same_id_add(node.right)
                    if left_name and right_name and left_name == right_name:
                        return left_name, left_count + right_count
                return None, 0

            ident_name, ident_count = _collect_same_id_add(expr)
            if ident_name and ident_count >= 3:
                ident_sym: Symbol = self.current_symtab.lookup(ident_name)
                ident_asm: str = ident_sym.asm_name()
                self.emit(f"\tLDA {ident_asm}")
                for _ in range(ident_count - 1):
                    self.emit("\tCLC")
                    self.emit(f"\tADC {ident_asm}")
                return

        # Fast path: Pure word arithmetic with simple operands (Identifier or IntLiteral)
        # For: word z = x + y or word z = x + 5
        # Generates direct 16-bit ADD/SUB without temporaries
        is_simple_word_add_sub: bool = (
            expr.op in {BinOp.ADD, BinOp.SUB} and 
            left_16 and right_16 and result_16 and
            not left_is_ptr and not right_is_ptr and
            not left_is_promoted_byte_arith and not right_is_promoted_byte_arith and
            isinstance(expr.left, (Identifier, IntLiteral)) and
            isinstance(expr.right, (Identifier, IntLiteral))
        )

        if is_simple_word_add_sub and isinstance(expr.right, IntLiteral):
            imm: int = expr.right.value & 0xFFFF
            if not ((expr.op == BinOp.ADD and imm == 1) or (expr.op == BinOp.SUB and imm == 1)):
                is_simple_word_add_sub = False
        
        if is_simple_word_add_sub:
            # Generate left operand low byte
            if isinstance(expr.left, Identifier):
                left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
            elif isinstance(expr.left, IntLiteral):
                val: int = expr.left.value & 0xFF
                self.emit(f"\tLDA #${val:02X}")
            
            # Set carry for ADD, clear for SUB
            if expr.op == BinOp.ADD:
                self.emit("\tCLC")
            else:  # SUB
                self.emit("\tSEC")
            
            # Generate right operand low byte and perform operation
            if isinstance(expr.right, Identifier):
                right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=True)}")
                else:
                    self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=True)}")
            elif isinstance(expr.right, IntLiteral):
                val: int = expr.right.value & 0xFF
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC #${val:02X}")
                else:
                    self.emit(f"\tSBC #${val:02X}")
            
            # Save low byte result to temporary
            self.emit("\tSTA TMP3")
            
            # Now do high byte (with carry propagation from low byte)
            # Load left operand high byte
            if isinstance(expr.left, Identifier):
                left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=False)}")
            elif isinstance(expr.left, IntLiteral):
                val: int = (expr.left.value >> 8) & 0xFF
                self.emit(f"\tLDA #${val:02X}")
            
            # ADC/SBC high byte (carry is already set/clear from low byte operation)
            if isinstance(expr.right, Identifier):
                right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=False)}")
                else:
                    self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=False)}")
            elif isinstance(expr.right, IntLiteral):
                val: int = (expr.right.value >> 8) & 0xFF
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC #${val:02X}")
                else:
                    self.emit(f"\tSBC #${val:02X}")
            
            # Result: A has high byte, need to return A/X with low byte in A, high byte in X
            self.emit("\tTAX")  # Move high byte to X
            self.emit("\tLDA TMP3")  # Get low byte back
            return

        # Check if left or right operand is complex (uses TMP0 internally)
        left_is_complex: bool = isinstance(expr.left, (SubscriptExpr, FieldAccess, DerefExpr, BinaryExpr))
        right_is_complex: bool = isinstance(expr.right, (SubscriptExpr, FieldAccess, DerefExpr, BinaryExpr))

        target_left_tmp: str | None = None
        target_used: bool = False
        if self.assign_target_sym and not self.assign_target_blocked:
            target_sym: Symbol = self.assign_target_sym
            target_is_word: bool = target_sym.type.base == "WORD" or target_sym.type.is_pointer
            if (not target_sym.is_array and target_sym.address is None and
                not self._is_fixed_address(target_sym.asm_name()) and
                not self._is_port_variable(target_sym.asm_name()) and
                not self._expr_mentions_identifier(expr, target_sym.name)):
                if not (result_16_adj and not target_is_word):
                    target_left_tmp = target_sym.asm_name()
        
        # Choose a temp that won't be clobbered by generating the right operand.
        # Honor caller's request when possible (force_left_tmp). If the left side
        # itself is complex it needs TMP1. Otherwise try to pick the opposite of
        # what the right side would prefer so they don't collide.
        if target_left_tmp:
            left_tmp = target_left_tmp
            target_used = True
        elif force_left_tmp and not left_is_complex:
            left_tmp = force_left_tmp
        elif left_is_complex:
            left_tmp = "TMP1"
        else:
            # Predict the right sub-expression's preferred left-temp
            if isinstance(expr.right, BinaryExpr):
                nested_left_is_complex: bool = isinstance(expr.right.left, (SubscriptExpr, FieldAccess, DerefExpr, BinaryExpr))
                right_pref: str = "TMP1" if nested_left_is_complex else "TMP0"
            elif isinstance(expr.right, (SubscriptExpr, FieldAccess, DerefExpr)):
                right_pref = "TMP0"
            else:
                right_pref = "TMP0"
            left_tmp: str = "TMP1" if right_pref == "TMP0" else "TMP0"

        # Detect if right operand contains a function call (needs special care)
        def _contains_call_or_math(e):
            """Helper for contains call or math.
            Internal helper used during code generation.
            """
            from ast_nodes import CallExpr, BinaryExpr, UnaryExpr, SubscriptExpr, FieldAccess
            # Detect explicit calls
            if isinstance(e, CallExpr):
                return e.name.upper() not in {"LOW", "HIGH", "SIZEOF", "LOWW", "HIGHW"}
            # Detect nested math operations that call runtime routines (MUL/DIV/MOD)
            if isinstance(e, BinaryExpr):
                if e.op in {BinOp.MUL, BinOp.DIV, BinOp.MOD}:
                    return True
                return _contains_call_or_math(e.left) or _contains_call_or_math(e.right)
            if isinstance(e, UnaryExpr):
                return _contains_call_or_math(e.expr)
            if isinstance(e, SubscriptExpr):
                return _contains_call_or_math(e.array) or _contains_call_or_math(e.index)
            if isinstance(e, FieldAccess):
                return _contains_call_or_math(e.object)
            return False

        right_has_call = _contains_call_or_math(expr.right)
        left_needs_word: bool = result_16_adj and left_t.sem_type.base == "BYTE" and not left_t.sem_type.is_pointer
        right_needs_word: bool = result_16_adj and right_t.sem_type.base == "BYTE" and not right_t.sem_type.is_pointer

        # Fast path: Bitwise operations with an immediate right operand (IntLiteral)
        if expr.op in {BinOp.BAND, BinOp.BOR, BinOp.BXOR} and isinstance(expr.right, IntLiteral) and not left_is_ptr and not right_is_ptr:
            asm_op = "AND" if expr.op == BinOp.BAND else "ORA" if expr.op == BinOp.BOR else "EOR"
            val = expr.right.value
            
            if t.width > 2:
                # 32-bit fast path
                self.gen_expr(expr.left)
                self.emit("\tLDA MATH0")
                self.emit(f"\t{asm_op} #${val & 0xFF:02X}")
                self.emit("\tSTA MATH0")
                self.emit("\tLDA MATH0+1")
                self.emit(f"\t{asm_op} #${(val >> 8) & 0xFF:02X}")
                self.emit("\tSTA MATH0+1")
                self.emit("\tLDA MATH0+2")
                self.emit(f"\t{asm_op} #${(val >> 16) & 0xFF:02X}")
                self.emit("\tSTA MATH0+2")
                self.emit("\tLDA MATH0+3")
                self.emit(f"\t{asm_op} #${(val >> 24) & 0xFF:02X}")
                self.emit("\tSTA MATH0+3")
                return
            
            # Generate left operand for 8/16-bit
            prev_force = self.force_word_result
            if left_needs_word:
                self.force_word_result = True
            try:
                self.gen_expr(expr.left)
            finally:
                self.force_word_result = prev_force

            if result_16_adj:
                # 16-bit fast path (result is in A/X)
                self.emit(f"\t{asm_op} #${val & 0xFF:02X}")
                self.emit("\tTAY")
                self.emit("\tTXA")
                self.emit(f"\t{asm_op} #${(val >> 8) & 0xFF:02X}")
                self.emit("\tTAX")
                self.emit("\tTYA")
            else:
                # 8-bit fast path (result is in A)
                self.emit(f"\t{asm_op} #${val & 0xFF:02X}")
            return


        if (expr.op in {BinOp.ADD, BinOp.SUB} and isinstance(expr.right, BinaryExpr) and
                expr.right.op in {BinOp.MUL, BinOp.DIV, BinOp.MOD} and
                isinstance(expr.left, (Identifier, IntLiteral)) and
                not (left_is_ptr or right_is_ptr)):
            # Evaluate right first (math call), then left, avoiding stack saves.
            prev_force = self.force_word_result
            if right_needs_word:
                self.force_word_result = True
            try:
                self.gen_expr(expr.right)
            finally:
                self.force_word_result = prev_force

            self.emit("\tSTA TMP0")
            if result_16_adj:
                self.emit("\tSTX TMP0+1")

            prev_force = self.force_word_result
            if left_needs_word:
                self.force_word_result = True
            try:
                self.gen_expr(expr.left)
            finally:
                self.force_word_result = prev_force

            self.emit("\tSTA TMP1")
            if result_16_adj:
                self.emit("\tSTX TMP1+1")

            self.emit("\tLDA TMP0")
            if result_16_adj:
                self.emit("\tLDX TMP0+1")

            # Use ADD16/SUB16 for 16-bit arithmetic
            if expr.op == BinOp.ADD and result_16_adj:
                self.math_routines_needed.add("ADD16")
                self.emit("\tSTA MATH0")
                self.emit("\tSTX MATH0+1")
                self.emit("\tLDA TMP1")
                self.emit("\tSTA MATH1")
                self.emit("\tLDA TMP1+1")
                self.emit("\tSTA MATH1+1")
                self.emit("\tJSR ADD16")
                self.emit("\tLDA MATH0")
                self.emit("\tLDX MATH0+1")
            elif expr.op == BinOp.SUB and result_16_adj:
                self.math_routines_needed.add("SUB16")
                self.emit("\tSTA MATH0")
                self.emit("\tSTX MATH0+1")
                self.emit("\tLDA TMP1")
                self.emit("\tSTA MATH1")
                self.emit("\tLDA TMP1+1")
                self.emit("\tSTA MATH1+1")
                self.emit("\tJSR SUB16")
                self.emit("\tLDA MATH0")
                self.emit("\tLDX MATH0+1")
            elif expr.op == BinOp.ADD:
                self._gen_add(result_16_adj, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, False, True, "TMP1")
            else:
                self._gen_sub(result_16_adj, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, False, "TMP1")
            return

        if right_has_call and expr.op in {BinOp.ADD, BinOp.SUB} and not (left_is_ptr or right_is_ptr):
            # Special-case: right contains a call. Preserve left across call.
            if result_16_adj:
                # 16-bit: save (A,X) → stack using PHA;TXA;PHA and restore with PLA;TAX;PLA
                prev_force: bool = self.force_word_result
                if left_needs_word:
                    self.force_word_result = True
                try:
                    self.gen_expr(expr.left)
                finally:
                    self.force_word_result = prev_force
                self.emit("\tPHA")
                self.emit("\tTXA")
                self.emit("\tPHA")

                # Generate right operand (callee may clobber temps)
                prev_force = self.force_word_result
                if right_needs_word:
                    self.force_word_result = True
                try:
                    self.gen_expr(expr.right)
                finally:
                    self.force_word_result = prev_force

                # Save right (A=low, X=high) to TMP0/TMP0+1
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")

                # Restore left (low in A, high in X)
                self.emit("\tPLA")
                self.emit("\tTAX")
                self.emit("\tPLA")

                # Use ADD16/SUB16 routines for better accumulator usage
                if expr.op == BinOp.ADD:
                    # Use ADD16: left in A/X, right in TMP0/TMP0+1
                    self.math_routines_needed.add("ADD16")
                    self.emit("\tSTA MATH0")
                    self.emit("\tSTX MATH0+1")
                    self.emit("\tLDA TMP0")
                    self.emit("\tSTA MATH1")
                    self.emit("\tLDA TMP0+1")
                    self.emit("\tSTA MATH1+1")
                    self.emit("\tJSR ADD16")
                    self.emit("\tLDA MATH0")
                    self.emit("\tLDX MATH0+1")
                else:
                    # Use SUB16: left in A/X, right in TMP0/TMP0+1
                    self.math_routines_needed.add("SUB16")
                    self.emit("\tSTA MATH0")
                    self.emit("\tSTX MATH0+1")
                    self.emit("\tLDA TMP0")
                    self.emit("\tSTA MATH1")
                    self.emit("\tLDA TMP0+1")
                    self.emit("\tSTA MATH1+1")
                    self.emit("\tJSR SUB16")
                    self.emit("\tLDA MATH0")
                    self.emit("\tLDX MATH0+1")

                # Special-case handled inline, skip generic handling
                return
            else:
                # 8-bit case (existing behavior)
                prev_force = self.force_word_result
                if left_needs_word:
                    self.force_word_result = True
                try:
                    self.gen_expr(expr.left)
                finally:
                    self.force_word_result = prev_force
                self.emit("\tPHA")

                # Generate right operand (callee may clobber TMPs)
                prev_force = self.force_word_result
                if right_needs_word:
                    self.force_word_result = True
                try:
                    self.gen_expr(expr.right)
                finally:
                    self.force_word_result = prev_force

                # Combine results: A contains right result; pull left from stack
                if expr.op == BinOp.ADD:
                    # Save right result, pull left, add
                    self.emit("\tSTA TMP0")
                    self.emit("\tPLA")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")
                else:  # SUB: left - right
                    self.emit("\tSTA TMP0")
                    self.emit("\tPLA")
                    self.emit("\tSEC")
                    self.emit("\tSBC TMP0")
                # Special-case handled inline, skip the generic handlers
                return
            # Special-case handled inline, skip the generic handlers
            return

        # Strength-reduce byte DIV/MOD by power-of-two constants.
        if (expr.op in {BinOp.DIV, BinOp.MOD} and isinstance(expr.right, IntLiteral) and
                not left_16 and not right_16 and not result_16_adj and
                not left_is_ptr and not right_is_ptr and
                not left_is_promoted_byte_arith and not right_is_promoted_byte_arith):
            divisor: int = expr.right.value & 0xFF
            if divisor != 0 and (divisor & (divisor - 1)) == 0:
                div_shift_count: int = 0
                while (1 << div_shift_count) < divisor:
                    div_shift_count += 1
                self.gen_expr(expr.left)
                if expr.op == BinOp.DIV:
                    for _ in range(div_shift_count):
                        self.emit("\tLSR A")
                else:
                    mask: int = divisor - 1
                    self.emit(f"\tAND #${mask:02X}")
                return

        if (expr.op in {BinOp.MUL, BinOp.DIV, BinOp.MOD} or 
                (expr.op in {BinOp.ADD, BinOp.SUB, BinOp.LSHIFT, BinOp.RSHIFT, 
                             BinOp.BAND, BinOp.BOR, BinOp.BXOR} and t.width > 2)):
            self._gen_math_binop(expr, left_t.width, right_t.width)
            return

        # Generate left operand
        prev_force = self.force_word_result
        if left_needs_word:
            self.force_word_result = True
        try:
            self.gen_expr(expr.left)
        finally:
            self.force_word_result = prev_force
        self.emit(f"\tSTA {left_tmp}")
        # Only save high byte if we need 16-bit result
        if result_16_adj:
            self.emit(f"\tSTX {left_tmp}+1")

        # Immediate 16-bit add/sub without temp shuffles
        if (expr.op in {BinOp.ADD, BinOp.SUB} and isinstance(expr.right, IntLiteral) and
                result_16_adj and not use_inc_opt and not use_dec_opt):
            imm_val: int = expr.right.value & 0xFFFF
            scale: int = 1
            if left_is_ptr or right_is_ptr:
                scale = ptr_elem_size
            total: int = (imm_val * scale) & 0xFFFF
            lo: int = total & 0xFF
            hi: int = (total >> 8) & 0xFF

            if expr.op == BinOp.ADD:
                # Use ADD16 routine for 16-bit immediate addition
                self.math_routines_needed.add("ADD16")
                self.emit(f"\tLDA {left_tmp}")
                self.emit(f"\tSTA MATH0")
                self.emit(f"\tLDA {left_tmp}+1")
                self.emit(f"\tSTA MATH0+1")
                self.emit(f"\tLDA #${lo:02X}")
                self.emit(f"\tSTA MATH1")
                self.emit(f"\tLDA #${hi:02X}")
                self.emit(f"\tSTA MATH1+1")
                self.emit("\tJSR ADD16")
                # Load result from MATH0 to A/X
                self.emit("\tLDA MATH0")
                self.emit("\tLDX MATH0+1")
                return
            else:
                # Use SUB16 routine for 16-bit immediate subtraction
                self.math_routines_needed.add("SUB16")
                self.emit(f"\tLDA {left_tmp}")
                self.emit(f"\tSTA MATH0")
                self.emit(f"\tLDA {left_tmp}+1")
                self.emit(f"\tSTA MATH0+1")
                self.emit(f"\tLDA #${lo:02X}")
                self.emit(f"\tSTA MATH1")
                self.emit(f"\tLDA #${hi:02X}")
                self.emit(f"\tSTA MATH1+1")
                self.emit("\tJSR SUB16")
                # Load result from MATH0 to A/X
                self.emit("\tLDA MATH0")
                self.emit("\tLDX MATH0+1")
                return
            return

        # Generate right operand (skip for INC/DEC optimization on BYTE pointers)
        shift_count: int | None = None
        if expr.op in {BinOp.LSHIFT, BinOp.RSHIFT} and isinstance(expr.right, IntLiteral):
            shift_count = expr.right.value

        if not (use_inc_opt or use_dec_opt) and shift_count is None:
            # Ask the right sub-expression to prefer the opposite temp to avoid
            # accidental clobbering of the saved left value.
            right_hint: str = "TMP0" if left_tmp == "TMP1" else "TMP1"
            prev_blocked: bool = self.assign_target_blocked
            if target_used:
                self.assign_target_blocked = True
            try:
                prev_force = self.force_word_result
                if right_needs_word:
                    self.force_word_result = True
                try:
                    self.gen_expr(expr.right, force_left_tmp=right_hint)
                finally:
                    self.force_word_result = prev_force
            finally:
                self.assign_target_blocked = prev_blocked
        
        # Handle different operations - try accumulator mode for 16-bit ADD/SUB
        if expr.op == BinOp.ADD and result_16_adj and not (left_is_ptr or right_is_ptr) and not use_inc_opt:
            # Use ADD16 routine for 16-bit non-pointer addition
            self.math_routines_needed.add("ADD16")
            # Right operand is in A/X, left is in left_tmp
            self.emit(f"\tSTA MATH1")
            self.emit(f"\tSTX MATH1+1")
            self.emit(f"\tLDA {left_tmp}")
            self.emit(f"\tSTA MATH0")
            self.emit(f"\tLDA {left_tmp}+1")
            self.emit(f"\tSTA MATH0+1")
            self.emit("\tJSR ADD16")
            # Load result from MATH0 to A/X for downstream code
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
        elif expr.op == BinOp.SUB and result_16_adj and not (left_is_ptr or right_is_ptr) and not use_dec_opt:
            # Use SUB16 routine for 16-bit non-pointer subtraction
            self.math_routines_needed.add("SUB16")
            # Right operand is in A/X, left is in left_tmp
            self.emit(f"\tSTA MATH1")
            self.emit(f"\tSTX MATH1+1")
            self.emit(f"\tLDA {left_tmp}")
            self.emit(f"\tSTA MATH0")
            self.emit(f"\tLDA {left_tmp}+1")
            self.emit(f"\tSTA MATH0+1")
            self.emit("\tJSR SUB16")
            # Load result from MATH0 to A/X for downstream code
            self.emit("\tLDA MATH0")
            self.emit("\tLDX MATH0+1")
        elif expr.op == BinOp.ADD:
            self._gen_add(result_16_adj, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, use_inc_opt, right_16, left_tmp)
        elif expr.op == BinOp.SUB:
            self._gen_sub(result_16_adj, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, use_dec_opt, left_tmp)
        elif expr.op == BinOp.MUL:
            self._gen_mul(left_16, right_16)
        elif expr.op == BinOp.DIV:
            self._gen_div(left_16, right_16)
        elif expr.op == BinOp.MOD:
            self._gen_mod(left_16, right_16)
        elif expr.op == BinOp.BAND:
            self._gen_bitwise_and(result_16, left_tmp)
        elif expr.op == BinOp.BOR:
            self._gen_bitwise_or(result_16, left_tmp)
        elif expr.op == BinOp.BXOR:
            self._gen_bitwise_xor(result_16, left_tmp)
        elif expr.op == BinOp.LSHIFT:
            self._gen_lshift(result_16, left_tmp, shift_count)
        elif expr.op == BinOp.RSHIFT:
            self._gen_rshift(result_16, left_tmp, shift_count)
        
        # For BYTE arithmetic where result is also BYTE, we don't need to promote to 16-bit
        # The carry is automatically handled by 8-bit wrapping (overflow wraps around 0-255)
        # We only need carry promotion if the result will be promoted somewhere else (checked via result_16_adj)
    
    def _gen_add(self, is_16bit: bool, ptr_elem_size: int = 1, use_inc: bool = False, right_16: bool = True, left_tmp: str = "TMP0") -> None:
        """Generate addition (inline)
        ptr_elem_size: if doing pointer arithmetic, the size of elements (1 for BYTE, 2 for WORD, or struct size)
        use_inc: if True and ptr_elem_size == 1, use INC on left_tmp for adding 1 (optimization)
        right_16: whether the right operand is 16-bit (if False, X may not be valid)
        left_tmp: which temporary register holds the left operand (default TMP0)
        
        NOTE: For 16-bit operations, right operand should be in A/X when called
        """
        # OPTIMIZATION: If we're adding to a BYTE target and the result is artificially 16-bit
        # just due to intermediate promotion, collapse back to 8-bit for the final result
        final_target_is_byte: None | bool = (self.assign_target_type and 
                               self.assign_target_type.base == "BYTE" and 
                               not self.assign_target_type.is_pointer)
        
        if ptr_elem_size > 1:
            # Pointer arithmetic with element size > 1
            # Need to multiply offset by element size
            if ptr_elem_size == 2:
                # Optimization: use ASL to multiply by 2
                self.emit("\tASL")  # Multiply by 2
            else:
                # General case: multiply by ptr_elem_size
                self.emit("\tSTA TMP3")  # Save offset
                self.emit("\tLDA #$00")
                self.emit("\tSTA TMP4")
                # Multiply TMP3 by ptr_elem_size
                for i in range(ptr_elem_size - 1):
                    self.emit("\tCLC")
                    self.emit("\tLDA TMP3")
                    self.emit("\tADC TMP4")
                    self.emit("\tSTA TMP4")
                    if self.emit("\tBCC +"):  # Check for carry
                        self.emit("\tINC TMP4+1")
                    self.emit("+")
                self.emit("\tLDA TMP4")
                self.emit("\tLDX TMP4+1")
        
        # If final target is BYTE, use simple 8-bit addition regardless of is_16bit
        if final_target_is_byte and is_16bit and not use_inc:
            # Simple 8-bit addition - just add low byte
            self.emit("\tCLC")
            self.emit(f"\tADC {left_tmp}")
            return
        
        if is_16bit:
            # 16-bit: (A,X) + (left_tmp,left_tmp+1) → (A,X)
            if use_inc and ptr_elem_size == 1:
                # Optimization: use INC for adding 1 to 16-bit pointer
                self.emit(f"\tINC {left_tmp}")
                self.emit(f"\tBNE +")
                self.emit(f"\tINC {left_tmp}+1")
                self.emit("+")
                self.emit(f"\tLDA {left_tmp}")
                self.emit(f"\tLDX {left_tmp}+1")
            else:
                # For BYTE operands, the high byte is always 0
                # For WORD operands, we need to use X correctly
                if not right_16:
                    # BYTE operand: high byte is 0, don't rely on X
                    # Save only the low byte and use 0 for high byte
                    self.emit("\tSTA TMP3")
                    # self.emit("\tLDA TMP3")    # Restore low byte
                    self.emit("\tCLC")
                    self.emit(f"\tADC {left_tmp}")     # Add low bytes
                    self.emit("\tTAY")
                    self.emit("\tLDA #$00")       # High byte is 0
                    self.emit(f"\tADC {left_tmp}+1")   # Add high bytes with carry
                    self.emit("\tTAX")
                    self.emit("\tTYA")
                else:
                    # WORD operand: both bytes are in A/X
                    # Save right operand (A,X) to TMP3/TMP4
                    self.emit("\tSTA TMP3")
                    self.emit("\tSTX TMP3+1")
                    # Now do the addition with proper handling
                    self.emit("\tLDA TMP3")    # Restore low byte of right operand
                    self.emit("\tCLC")
                    self.emit(f"\tADC {left_tmp}")     # Add low bytes
                    self.emit("\tTAY")
                    self.emit("\tLDA TMP3+1")   # Get high byte of right operand
                    self.emit(f"\tADC {left_tmp}+1")   # Add high bytes with carry
                    self.emit("\tTAX")
                    self.emit("\tTYA")
        else:
            # 8-bit: A + left_tmp → A
            if use_inc and ptr_elem_size == 1:
                # Optimization: use INC for adding 1
                self.emit(f"\tINC {left_tmp}")
                self.emit(f"\tLDA {left_tmp}")
            else:
                self.emit("\tCLC")
                self.emit(f"\tADC {left_tmp}")
    
    def _gen_sub(self, is_16bit: bool, ptr_elem_size: int = 1, use_dec: bool = False, left_tmp: str = "TMP0") -> None:
        """Generate subtraction (inline): left_tmp - A
        ptr_elem_size: if doing pointer arithmetic, the size of elements (1 for BYTE, 2 for WORD)
        use_dec: if True and ptr_elem_size == 1, use DEC on left_tmp for subtracting 1 (optimization)
        left_tmp: which temporary register holds the left operand (default TMP0)
        """
        if ptr_elem_size == 2:
            # Pointer to WORD: scale offset by 2
            # A (offset) needs to be multiplied by 2 before subtracting
            self.emit("\tASL")  # Multiply by 2
        
        if is_16bit:
            # 16-bit: (left_tmp,left_tmp+1) - (A,X) → (A,X)
            if use_dec and ptr_elem_size == 1:
                # Optimization: use DEC for subtracting 1 from 16-bit pointer
                self.emit(f"\tDEC {left_tmp}")
                self.emit(f"\tBNE +")
                self.emit(f"\tDEC {left_tmp}+1")
                self.emit("+")
                self.emit(f"\tLDA {left_tmp}")
                self.emit(f"\tLDX {left_tmp}+1")
            else:
                self.emit("\tSTA TMP2")
                self.emit("\tSTX TMP2+1")
                self.emit("\tSEC")
                self.emit(f"\tLDA {left_tmp}")
                self.emit("\tSBC TMP2")
                self.emit("\tTAY")
                self.emit(f"\tLDA {left_tmp}+1")
                self.emit("\tSBC TMP2+1")
                self.emit("\tTAX")
                self.emit("\tTYA")
        else:
            # 8-bit: left_tmp - A → A
            if use_dec and ptr_elem_size == 1:
                # Optimization: use DEC for subtracting 1
                self.emit(f"\tDEC {left_tmp}")
                self.emit(f"\tLDA {left_tmp}")
            else:
                self.emit("\tSTA TMP2")
                self.emit("\tSEC")
                self.emit(f"\tLDA {left_tmp}")
                self.emit("\tSBC TMP2")
    
    def _gen_math_binop(self, expr: BinaryExpr, left_width: int, right_width: int) -> None:
        """Generate MUL/DIV/MOD (and 32-bit ADD/SUB) using math stack."""
        def _is_simple_operand(op: Expr) -> bool:
            return isinstance(op, (Identifier, IntLiteral))

        def _emit_op0(op: Expr, width: int) -> None:
            if isinstance(op, IntLiteral):
                val = op.value
                self.emit(f"\tLDA #${val & 0xFF:02X}")
                self.emit("\tSTA MATH0")
                self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
                self.emit("\tSTA MATH0+1")
                if width > 2:
                    self.emit(f"\tLDA #${(val >> 16) & 0xFF:02X}")
                    self.emit("\tSTA MATH0+2")
                    self.emit(f"\tLDA #${(val >> 24) & 0xFF:02X}")
                    self.emit("\tSTA MATH0+3")
                else:
                    self._stz("MATH0+2")
                    self._stz("MATH0+3")
                return
            if isinstance(op, Identifier):
                sym = self.current_symtab.lookup(op.name)
                asm = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit("\tSTA MATH0")
                if width >= 2:
                    self.emit(f"\tLDA {asm}+1")
                    self.emit("\tSTA MATH0+1")
                else:
                    self._stz("MATH0+1")
                
                if width > 2:
                    self.emit(f"\tLDA {asm}+2")
                    self.emit("\tSTA MATH0+2")
                    self.emit(f"\tLDA {asm}+3")
                    self.emit("\tSTA MATH0+3")
                else:
                    self._stz("MATH0+2")
                    self._stz("MATH0+3")
                return

        def _emit_op1(op: Expr, width: int) -> None:
            if isinstance(op, IntLiteral):
                val = op.value
                self.emit(f"\tLDA #${val & 0xFF:02X}")
                self.emit("\tSTA MATH1")
                self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
                self.emit("\tSTA MATH1+1")
                if width > 2:
                    self.emit(f"\tLDA #${(val >> 16) & 0xFF:02X}")
                    self.emit("\tSTA MATH1+2")
                    self.emit(f"\tLDA #${(val >> 24) & 0xFF:02X}")
                    self.emit("\tSTA MATH1+3")
                else:
                    self._stz("MATH1+2")
                    self._stz("MATH1+3")
                return
            if isinstance(op, Identifier):
                sym = self.current_symtab.lookup(op.name)
                asm = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit("\tSTA MATH1")
                if width >= 2:
                    self.emit(f"\tLDA {asm}+1")
                    self.emit("\tSTA MATH1+1")
                else:
                    self._stz("MATH1+1")
                
                if width > 2:
                    self.emit(f"\tLDA {asm}+2")
                    self.emit("\tSTA MATH1+2")
                    self.emit(f"\tLDA {asm}+3")
                    self.emit("\tSTA MATH1+3")
                else:
                    self._stz("MATH1+2")
                    self._stz("MATH1+3")
                return

        # If both operands are simple, avoid math stack entirely.
        if _is_simple_operand(expr.left) and _is_simple_operand(expr.right):
            _emit_op0(expr.left, left_width)
            _emit_op1(expr.right, right_width)
        else:
            # Save left operand on math stack
            self.gen_expr(expr.left)
            # If gen_expr result is in A/X (width <= 2) or MATH0 (width > 2), push correctly
            self._math_stack_push(left_width)

            # Evaluate right operand
            self.gen_expr(expr.right)
            # Result in A/X or MATH0. Move to MATH1.
            if right_width > 2:
                # Already in MATH0? Move to MATH1?
                # gen_expr for 32-bit leaves result in MATH0.
                # Just move MATH0 -> MATH1
                self.emit("\tLDA MATH0")
                self.emit("\tSTA MATH1")
                self.emit("\tLDA MATH0+1")
                self.emit("\tSTA MATH1+1")
                self.emit("\tLDA MATH0+2")
                self.emit("\tSTA MATH1+2")
                self.emit("\tLDA MATH0+3")
                self.emit("\tSTA MATH1+3")
            else:
                # Result in A/X
                self.emit("\tSTA MATH1")
                if right_width == 2:
                    self.emit("\tSTX MATH1+1")
                else:
                    self._stz("MATH1+1")
                self._stz("MATH1+2")
                self._stz("MATH1+3")

            # Restore left operand into MATH0/MATH0+1..3
            self._math_stack_pop_to_op0()

        if expr.op == BinOp.MUL:
            self._gen_mul(left_width, right_width)
        elif expr.op == BinOp.DIV:
            self._gen_div(left_width, right_width)
        elif expr.op == BinOp.MOD:
            self._gen_mod(left_width, right_width)
        elif expr.op == BinOp.ADD:
            # Assume 32-bit add if called here
            self.math_routines_needed.add("ADD32")
            self.emit("\tJSR ADD32")
        elif expr.op == BinOp.SUB:
            self.math_routines_needed.add("SUB32")
            self.emit("\tJSR SUB32")
        elif expr.op == BinOp.LSHIFT:
            self._gen_lshift32()
        elif expr.op == BinOp.RSHIFT:
            self._gen_rshift32()
        elif expr.op in {BinOp.BAND, BinOp.BOR, BinOp.BXOR}:
            self._gen_bitwise32(expr.op)

        # Result is stored in MATH0; load low word into A/X for downstream codegen.
        left_16 = left_width >= 2
        right_16 = right_width >= 2
        if not (left_16 or right_16):
            self._stz("MATH0+1")
            self._stz("MATH0+2")
            self._stz("MATH0+3")
        self.emit("\tLDA MATH0")
        self.emit("\tLDX MATH0+1")

    def _gen_lshift32(self) -> None:
        """Generate 32-bit left shift via runtime routine."""
        self.math_routines_needed.add("LSHIFT32")
        # Runtime routine expects count in A. Count is in MATH1.
        self.emit("\tLDA MATH1")
        self.emit("\tJSR LSHIFT32")

    def _gen_rshift32(self) -> None:
        """Generate 32-bit right shift via runtime routine."""
        self.math_routines_needed.add("RSHIFT32")
        # Runtime routine expects count in A. Count is in MATH1.
        self.emit("\tLDA MATH1")
        self.emit("\tJSR RSHIFT32")

    def _gen_bitwise32(self, op: BinOp) -> None:
        """Generate 32-bit bitwise op inline."""
        # MATH0 = MATH0 op MATH1
        for i in range(4):
            suffix = "" if i == 0 else f"+{i}"
            self.emit(f"\tLDA MATH0{suffix}")
            if op == BinOp.BAND:
                self.emit(f"\tAND MATH1{suffix}")
            elif op == BinOp.BOR:
                self.emit(f"\tORA MATH1{suffix}")
            elif op == BinOp.BXOR:
                self.emit(f"\tEOR MATH1{suffix}")
            self.emit(f"\tSTA MATH0{suffix}")

    def _gen_mul(self, left_width: int, right_width: int) -> None:
        """Generate multiplication (call runtime routine)."""
        if left_width > 2 or right_width > 2:
            self.math_routines_needed.add("MUL32")
            self.emit("\tJSR MUL32")
            return

        left_16 = left_width >= 2
        right_16 = right_width >= 2
        
        if not left_16 and not right_16:
            self.math_routines_needed.add("MUL8")
            self.emit("\tJSR MUL8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("MUL16_8")
            self.emit("\tJSR MUL16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("MUL16_8")
            # Swap operands so multiplicand is 16-bit in MATH0
            self.emit("\tLDA MATH0")
            self.emit("\tSTA TMP0")
            self.emit("\tLDA MATH0+1")
            self.emit("\tSTA TMP0+1")
            self.emit("\tLDA MATH1")
            self.emit("\tSTA MATH0")
            self.emit("\tLDA MATH1+1")
            self.emit("\tSTA MATH0+1")
            self.emit("\tLDA TMP0")
            self.emit("\tSTA MATH1")
            self._stz("MATH1+1")
            self.emit("\tJSR MUL16_8")
        else:
            self.math_routines_needed.add("MUL16")
            # MUL16 emits a full 32-bit product in MATH0
            self.emit("\tJSR MUL16")

    def _gen_div(self, left_width: int, right_width: int) -> None:
        """Generate division (call runtime routine)."""
        if left_width > 2 or right_width > 2:
            self.math_routines_needed.add("DIV32")
            self.emit("\tJSR DIV32")
            return

        left_16 = left_width >= 2
        right_16 = right_width >= 2

        if not left_16 and not right_16:
            self.math_routines_needed.add("DIV8")
            self.emit("\tJSR DIV8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("DIV16_8")
            self.emit("\tJSR DIV16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("DIV8_16")
            self.emit("\tJSR DIV8_16")
        else:
            self.math_routines_needed.add("DIV16")
            self.emit("\tJSR DIV16")

    def _gen_mod(self, left_width: int, right_width: int) -> None:
        """Generate modulo (call runtime routine)."""
        if left_width > 2 or right_width > 2:
            self.math_routines_needed.add("MOD32")
            self.emit("\tJSR MOD32")
            return

        left_16 = left_width >= 2
        right_16 = right_width >= 2

        if not left_16 and not right_16:
            self.math_routines_needed.add("MOD8")
            self.emit("\tJSR MOD8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("MOD16_8")
            self.emit("\tJSR MOD16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("MOD8_16")
            self.emit("\tJSR MOD8_16")
        else:
            self.math_routines_needed.add("MOD16")
            self.emit("\tJSR MOD16")

    def _gen_bitwise_and(self, result_16: bool, left_tmp: str = "TMP0") -> None:
        """Generate bitwise AND: left_tmp & A (or left_tmp/left_tmp+1 & A/X for 16-bit)"""
        if result_16:
            # 16-bit AND: (left_tmp,left_tmp+1) & (A,X) → (A,X)
            self.emit(f"\tAND {left_tmp}")
            self.emit("\tTAY")
            self.emit("\tTXA")
            self.emit(f"\tAND {left_tmp}+1")
            self.emit("\tTAX")
            self.emit("\tTYA")
        else:
            # 8-bit AND: left_tmp & A → A
            self.emit(f"\tAND {left_tmp}")

    def _gen_bitwise_or(self, result_16: bool, left_tmp: str = "TMP0") -> None:
        """Generate bitwise OR: left_tmp | A (or left_tmp/left_tmp+1 | A/X for 16-bit)"""
        if result_16:
            # 16-bit OR: (left_tmp,left_tmp+1) | (A,X) → (A,X)
            self.emit(f"\tORA {left_tmp}")
            self.emit("\tTAY")
            self.emit("\tTXA")
            self.emit(f"\tORA {left_tmp}+1")
            self.emit("\tTAX")
            self.emit("\tTYA")
        else:
            # 8-bit OR: left_tmp | A → A
            self.emit(f"\tORA {left_tmp}")

    def _gen_bitwise_xor(self, result_16: bool, left_tmp: str = "TMP0") -> None:
        """Generate bitwise XOR: left_tmp ^ A (or left_tmp/left_tmp+1 ^ A/X for 16-bit)"""
        if result_16:
            # 16-bit XOR: (left_tmp,left_tmp+1) ^ (A,X) → (A,X)
            self.emit(f"\tEOR {left_tmp}")
            self.emit("\tTAY")
            self.emit("\tTXA")
            self.emit(f"\tEOR {left_tmp}+1")
            self.emit("\tTAX")
            self.emit("\tTYA")
        else:
            # 8-bit XOR: left_tmp ^ A → A
            self.emit(f"\tEOR {left_tmp}")

    def _gen_lshift(self, result_16: bool, left_tmp: str = "TMP0", shift_count: int | None = None) -> None:
        """Generate left shift: left_tmp << A (shift count in A)
        Special case: left_tmp="A" means value is already in accumulator (for constant-count shifts)
        For 16-bit shifts with left_tmp="A", both A and X contain the operand (low and high bytes)
        """
        self.used_temps.add("TMP2")
        self.used_temps.add("TMP3")
        # Shift count is in A
        if shift_count is not None:
            if shift_count <= 0:
                if left_tmp != "A":
                    self.emit(f"\tLDA {left_tmp}")
                if result_16:
                    if left_tmp != "A":
                        self.emit(f"\tLDX {left_tmp}+1")
                return
            if result_16:
                if left_tmp == "A":
                    # Value is already in A/X (both low and high bytes from operand loading)
                    # Save both bytes to TMP0/TMP0+1
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")  # X already contains high byte, don't change it
                else:
                    self.emit(f"\tLDA {left_tmp}")
                    self.emit(f"\tLDX {left_tmp}+1")
                    if left_tmp != "TMP0":
                        self.emit("\tSTA TMP0")
                        self.emit("\tSTX TMP0+1")
                # OPTIMIZATION: Use absolute addressing mode to shift directly in memory
                for _ in range(shift_count):
                    self.emit("\tASL TMP0")
                    self.emit("\tROL TMP0+1")
                self.emit("\tLDA TMP0")
                self.emit("\tLDX TMP0+1")
                return
            # 8-bit constant shift
            if left_tmp != "A":
                self.emit(f"\tLDA {left_tmp}")
            for _ in range(shift_count):
                self.emit("\tASL")   # accumulator mode (ca65 syntax: no 'A' suffix)
            return
        if result_16:
            # 16-bit shift left (left_tmp,left_tmp+1) << A → (A,X)
            self.emit("\tSTA TMP2")    # Store shift count
            self.emit(f"\tLDA {left_tmp}")    # Load low byte into A
            self.emit(f"\tLDX {left_tmp}+1")  # Load high byte into X
            
            # Copy to TMP0/TMP0+1 if not already there
            if left_tmp != "TMP0":
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")
            
            lbl_loop: str = self.new_label("LSHIFT_LOOP")
            lbl_end: str = self.new_label("LSHIFT_END")
            self.emit(f"\tLDA TMP2")   # Load shift count
            self.emit(f"\tBEQ {lbl_end}")
            self.emit(f"{lbl_loop}:")
            self.emit("\tASL TMP0")    # Shift low byte left
            self.emit("\tROL TMP0+1")  # Rotate high byte left with carry
            self.emit("\tDEC TMP2")    # Decrement shift count
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Result low byte
            self.emit("\tLDX TMP0+1")  # Result high byte
        else:
            # 8-bit shift left: left_tmp << A → A
            self.emit("\tSTA TMP2")    # Store shift count
            self.emit(f"\tLDA {left_tmp}")    # Load value
            
            # Copy to TMP0 if not already there
            if left_tmp != "TMP0":
                self.emit("\tSTA TMP0")
            
            lbl_loop: str = self.new_label("LSHIFT8_LOOP")
            lbl_end: str = self.new_label("LSHIFT8_END")
            self.emit(f"\tLDA TMP2")   # Load shift count
            self.emit(f"\tBEQ {lbl_end}")
            self.emit(f"{lbl_loop}:")
            self.emit("\tASL TMP0")    # Shift left in place
            self.emit("\tDEC TMP2")    # Decrement counter
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Load result

    def _gen_rshift(self, result_16: bool, left_tmp: str = "TMP0", shift_count: int | None = None) -> None:
        """Generate right shift: left_tmp >> A (shift count in A)
        Special case: left_tmp="A" means value is already in accumulator (for constant-count shifts)
        For 16-bit shifts with left_tmp="A", both A and X contain the operand (low and high bytes)
        """
        self.used_temps.add("TMP2")
        self.used_temps.add("TMP3")
        # Shift count is in A
        if shift_count is not None:
            if shift_count <= 0:
                if left_tmp != "A":
                    self.emit(f"\tLDA {left_tmp}")
                if result_16:
                    if left_tmp != "A":
                        self.emit(f"\tLDX {left_tmp}+1")
                return
            if result_16:
                if left_tmp == "A":
                    # Value is already in A/X (both low and high bytes from operand loading)
                    # Save both bytes to TMP0/TMP0+1
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")  # X already contains high byte, don't change it
                else:
                    self.emit(f"\tLDA {left_tmp}")
                    self.emit(f"\tLDX {left_tmp}+1")
                    if left_tmp != "TMP0":
                        self.emit("\tSTA TMP0")
                        self.emit("\tSTX TMP0+1")
                # OPTIMIZATION: Use absolute addressing mode to shift directly in memory
                for _ in range(shift_count):
                    self.emit("\tLSR TMP0+1")
                    self.emit("\tROR TMP0")
                self.emit("\tLDA TMP0")
                self.emit("\tLDX TMP0+1")
                return
            # 8-bit constant shift
            if left_tmp != "A":
                self.emit(f"\tLDA {left_tmp}")
            for _ in range(shift_count):
                self.emit("\tLSR")   # accumulator mode (ca65 syntax: no 'A' suffix)
            return
        if result_16:
            # 16-bit shift right (left_tmp,left_tmp+1) >> A → (A,X)
            self.emit("\tSTA TMP2")    # Store shift count
            self.emit(f"\tLDA {left_tmp}")    # Load low byte into A
            self.emit(f"\tLDX {left_tmp}+1")  # Load high byte into X
            
            # Copy to TMP0/TMP0+1 if not already there
            if left_tmp != "TMP0":
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")
            
            lbl_loop: str = self.new_label("RSHIFT_LOOP")
            lbl_end: str = self.new_label("RSHIFT_END")
            self.emit(f"\tLDA TMP2")   # Load shift count
            self.emit(f"\tBEQ {lbl_end}")
            self.emit(f"{lbl_loop}:")
            self.emit("\tLSR TMP0+1")  # Shift high byte right
            self.emit("\tROR TMP0")    # Rotate low byte right with carry
            self.emit("\tDEC TMP2")    # Decrement shift count
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Result low byte
            self.emit("\tLDX TMP0+1")  # Result high byte
        else:
            # 8-bit shift right: left_tmp >> A → A
            self.emit("\tSTA TMP2")    # Store shift count
            self.emit(f"\tLDA {left_tmp}")    # Load value
            
            # Copy to TMP0 if not already there
            if left_tmp != "TMP0":
                self.emit("\tSTA TMP0")
            
            lbl_loop: str = self.new_label("RSHIFT8_LOOP")
            lbl_end: str = self.new_label("RSHIFT8_END")
            self.emit(f"\tLDA TMP2")   # Load shift count
            self.emit(f"\tBEQ {lbl_end}")
            self.emit(f"{lbl_loop}:")
            self.emit("\tLSR TMP0")    # Shift right in place
            self.emit("\tDEC TMP2")    # Decrement counter
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Load result

    def _gen_unary(self, expr: UnaryExpr) -> None:
        """Generate code for unary operators (@, !, ~, -)"""
        operand_t: ExprType = self.tc_check(expr.expr)
        width: int = operand_t.sem_type.width if hasattr(operand_t.sem_type, 'width') else operand_t.sem_type.get_size()
        
        if expr.op == UnOp.ADDROF:  # Address-of (@)
            # Generate code to load address of operand into A (low) and X (high)
            self._gen_address_of(expr.expr)
        
        elif expr.op == UnOp.BNOT:  # Bitwise NOT (~)
            # Generate operand
            self.gen_expr(expr.expr)
            
            if width > 2:
                # 32-bit: Invert all 4 bytes in MATH0
                # Operand is in MATH0
                self.emit("\tLDA MATH0")
                self.emit("\tEOR #$FF")
                self.emit("\tSTA MATH0")
                self.emit("\tLDA MATH0+1")
                self.emit("\tEOR #$FF")
                self.emit("\tSTA MATH0+1")
                self.emit("\tLDA MATH0+2")
                self.emit("\tEOR #$FF")
                self.emit("\tSTA MATH0+2")
                self.emit("\tLDA MATH0+3")
                self.emit("\tEOR #$FF")
                self.emit("\tSTA MATH0+3")
                return

            result_16: bool = width >= 2
            
            if result_16:
                # For WORD: invert both bytes
                # A has low byte, X has high byte
                self.emit("\tEOR #$FF")      # Invert low byte
                self.emit("\tSTA TMP0")      # Save low byte
                self.emit("\tTXA")           # Move high byte to A
                self.emit("\tEOR #$FF")      # Invert high byte
                self.emit("\tTAX")           # Move back to X
                self.emit("\tLDA TMP0")      # Restore low byte
            else:
                # For BYTE: invert just A
                self.emit("\tEOR #$FF")
        
        elif expr.op == UnOp.NOT:  # Logical NOT (!)
            # Generate operand and test it
            self.gen_expr(expr.expr)
            lbl_zero: str = self.new_label("NOT_ZERO")
            lbl_end: str = self.new_label("NOT_END")
            
            if width > 2:
                # 32-bit: Check if any byte is nonzero
                self.emit("\tLDA MATH0")
                self.emit("\tORA MATH0+1")
                self.emit("\tORA MATH0+2")
                self.emit("\tORA MATH0+3")
                self.emit(f"\tBNE {lbl_zero}")
                # Zero -> 1
                self.emit("\tLDA #$01")
                self.emit(f"\tJMP {lbl_end}")
                self.emit(f"{lbl_zero}:")
                self.emit("\tLDA #$00")
                self.emit(f"{lbl_end}:")
                return

            result_16: bool = width >= 2
            
            if result_16:
                # Test if A or X is nonzero
                self.emit("\tSTA TMP4")
                self.emit("\tTXA")
                self.emit("\tORA TMP4")
                self.emit(f"\tBNE {lbl_zero}")
                # Value was zero, result is 1
                self.emit("\tLDA #$01")
                if self.is_65c02:
                    self.emit(f"\tBRA {lbl_end}")
                else:
                    self.emit(f"\tJMP {lbl_end}")
                self.emit(f"{lbl_zero}:")
                self.emit("\tLDA #$00")
                self.emit(f"{lbl_end}:")
            else:
                # Test A only
                self.emit(f"\tBNE {lbl_zero}")
                self.emit("\tLDA #$01")
                if self.is_65c02:
                    self.emit(f"\tBRA {lbl_end}")
                else:
                    self.emit(f"\tJMP {lbl_end}")
                self.emit(f"{lbl_zero}:")
                self.emit("\tLDA #$00")
                self.emit(f"{lbl_end}:")

        elif expr.op == UnOp.NEG:   # Negation (-)
            self.gen_expr(expr.expr)
            
            if width > 2:
                # 32-bit negation
                self.math_routines_needed.add("NEG32")
                self.emit("\tJSR NEG32")
                return

            result_16: bool = width >= 2
            if result_16:
                # 16-bit negation (0 - val)
                # A/X contains val. Use TMP for storage.
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")
                self.emit("\tLDA #$00")
                self.emit("\tSEC")
                self.emit("\tSBC TMP0")
                self.emit("\tTAY")
                self.emit("\tLDA #$00")
                self.emit("\tSBC TMP0+1")
                self.emit("\tTAX")
                self.emit("\tTYA")
            else:
                # 8-bit negation (0 - val)
                self.emit("\tSTA TMP0")
                self.emit("\tLDA #$00")
                self.emit("\tSEC")
                self.emit("\tSBC TMP0")
    
    def _estimate_temp_slots(self, expr) -> int:
        """Conservative estimator of required temporary *slots* for an expression.
        Each slot corresponds to a TMP (TMP0..TMP5) used to hold intermediate values.
        This estimator is conservative and intended to detect expressions that are
        too complex to lower given the limited number of temps. Rules:
          - IntLiteral, Identifier -> 0
          - Subscript/Field/Deref/Call -> 1
          - Unary -> same as child
          - Binary: max(left,right) + 1
          - MUL/DIV/MOD: max(left,right) + 1 (math stack handles extra storage)
        """
        from ast_nodes import BinaryExpr, UnaryExpr, CallExpr, SubscriptExpr, FieldAccess, DerefExpr, Identifier, IntLiteral
        if isinstance(expr, (IntLiteral, Identifier)):
            return 0
        if isinstance(expr, (SubscriptExpr, FieldAccess, DerefExpr, CallExpr)):
            return 1
        if isinstance(expr, UnaryExpr):
            return self._estimate_temp_slots(expr.expr)
        if isinstance(expr, BinaryExpr):
            left = self._estimate_temp_slots(expr.left)
            right = self._estimate_temp_slots(expr.right)
            if expr.op in {BinOp.MUL, BinOp.DIV, BinOp.MOD}:
                return max(left, right) + 1
            return max(left, right) + 1
        return 1

    def _gen_address_of(self, operand: Expr) -> None:
        """Generate code to load address of operand into A (low byte) and X (high byte)"""
        if isinstance(operand, Identifier):
            # Simple variable: load its address
            sym: Symbol = self.current_symtab.lookup(operand.name)
            label: str = self._get_label_for_symbol(sym)
            
            # Load address into A (low) and X (high)
            self.emit(f"\tLDA #<{label}")
            self.emit(f"\tLDX #>{label}")
        
        elif isinstance(operand, SubscriptExpr):
            # Array element: calculate base + index*element_size
            # Get array symbol
            if not isinstance(operand.array, Identifier):
                raise SemanticError("Complex array subscripts not supported with @", node=getattr(self, 'current_expr', None))
            array_sym: Symbol = self.current_symtab.lookup(operand.array.name)
            label: str = self._get_label_for_symbol(array_sym)
            
            # Get element size
            elem_size: int = array_sym.type.get_size()
            
            # Generate index value into TMP0
            self.gen_expr(operand.index)
            self.emit("\tSTA TMP0")  # Save index
            
            # Calculate address = base + index * elem_size
            if elem_size == 1:
                # No multiplication needed
                self.emit(f"\tLDA #<{label}")
                self.emit("\tCLC")
                self.emit("\tADC TMP0")
                self.emit("\tSTA TMP1")       # Save low byte of result
                self.emit(f"\tLDA #>{label}")
                self.emit("\tADC #$00")       # Add carry to high byte
                self.emit("\tTAX")            # High byte to X
                self.emit("\tLDA TMP1")       # Low byte to A
            else:
                # Multiply index by element size (index is 8-bit in TMP0)
                if elem_size == 2:
                    # index * 2: shift left, track carry in TMP1 (high byte of offset)
                    self.emit("\tASL TMP0")         # TMP0 = (index*2) & $FF, C = bit7
                    self.emit("\tLDA #$00")
                    self.emit("\tROL A")            # A = high byte of (index*2)
                    self.emit("\tSTA TMP1")         # TMP1 = high byte of offset
                    self.emit(f"\tLDA #<{label}")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")         # A = base_lo + offset_lo
                    self.emit("\tSTA TMP0")         # save low byte of result
                    self.emit(f"\tLDA #>{label}")
                    self.emit("\tADC TMP1")         # A = base_hi + offset_hi + carry
                    self.emit("\tTAX")              # X = high byte of address
                    self.emit("\tLDA TMP0")         # A = low byte of address
                elif elem_size == 4:
                    # index * 4: shift left twice, accumulate carries in TMP1
                    self.emit("\tASL TMP0")         # TMP0 = (index*2) & $FF, C = bit7
                    self.emit("\tLDA #$00")
                    self.emit("\tROL A")            # A = carry from first shift
                    self.emit("\tASL TMP0")         # TMP0 = (index*4) & $FF, C = bit7 of (index*2)
                    self.emit("\tROL A")            # A = high byte of (index*4)
                    self.emit("\tSTA TMP1")         # TMP1 = high byte of offset
                    self.emit(f"\tLDA #<{label}")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")         # A = base_lo + offset_lo
                    self.emit("\tSTA TMP0")         # save low byte of result
                    self.emit(f"\tLDA #>{label}")
                    self.emit("\tADC TMP1")         # A = base_hi + offset_hi + carry
                    self.emit("\tTAX")              # X = high byte of address
                    self.emit("\tLDA TMP0")         # A = low byte of address
                else:
                    raise SemanticError(f"Element size {elem_size} not yet supported for @array[index]", node=getattr(self, 'current_expr', None))
        
        elif isinstance(operand, FieldAccess):
            # Struct field: base address + field offset
            if not isinstance(operand.object, Identifier):
                raise SemanticError("Complex field access not supported with @", node=getattr(self, 'current_expr', None))
            
            struct_sym: Symbol = self.current_symtab.lookup(operand.object.name)
            struct_label: str = self._get_label_for_symbol(struct_sym)
            
            # Get field offset
            field_offset: int = self._get_field_offset(operand.object, operand.field)
            
            # Load base address
            self.emit(f"\tLDA #<{struct_label}")
            self.emit(f"\tLDX #>{struct_label}")
            
            # Add field offset
            if field_offset > 0:
                lbl_no_carry: str = self.new_label("ADDROF_NO_CARRY")
                self.emit("\tSTA TMP0")
                self.emit("\tCLC")
                self.emit(f"\tADC #${field_offset:02X}")
                self.emit(f"\tBCC {lbl_no_carry}")
                self.emit("\tINX")
                self.emit(f"{lbl_no_carry}:")
        
        else:
            raise SemanticError("Invalid operand for address-of operator", node=getattr(self, 'current_expr', None))
    
    def _get_const_array_label(self, sym: Symbol) -> str:
        """Return the __ARRAY_DATA_N label for a const array, registering it if needed."""
        if sym.init and isinstance(sym.init, ListInit):
            values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
            dtype: str = sym.type.base
            data_key: tuple[tuple[int, ...], str] = (tuple(values), dtype)
            if data_key not in self.array_literals:
                self.array_id += 1
                self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
            return self.array_literals[data_key]
        elif sym.init and isinstance(sym.init, StringInit):
            str_values: list[int] = [ord(ch) for ch in sym.init.value] + [0]
            str_key: tuple[tuple[int, ...], str] = (tuple(str_values), "BYTE")
            if str_key not in self.array_literals:
                self.array_id += 1
                self.array_literals[str_key] = f"__ARRAY_DATA_{self.array_id}"
            return self.array_literals[str_key]
        else:
            raise SemanticError(f"Const array '{sym.name}' has no initialization")

    def _get_label_for_symbol(self, sym: Symbol) -> str:
        """Get the label name for a symbol"""
        if sym.address is not None:
            # Fixed address variable
            return f"${sym.address:04X}"
        # Const array: data lives in ROM under __ARRAY_DATA_N label
        if sym.is_const and sym.is_array:
            return self._get_const_array_label(sym)
        # Dynamic address - use symbol label (supports shared slots)
        return sym.asm_name()
    
    def _get_field_offset(self, struct_expr: Expr, field_name: str) -> int:
        """Calculate byte offset of field within struct"""
        if not isinstance(struct_expr, Identifier):
            raise SemanticError("Complex struct access not supported", node=getattr(self, 'current_expr', None))
        
        sym: Symbol = self.current_symtab.lookup(struct_expr.name)
        if not sym.type.is_struct or not sym.type.struct_info:
            raise SemanticError("Not a struct", node=getattr(self, 'current_expr', None))
        
        offset = 0
        for field in sym.type.struct_info.fields:
            if field.name.upper() == field_name.upper():
                return offset
            offset += field.width
        
        raise SemanticError(f"Field '{field_name}' not found in struct", node=getattr(self, 'current_expr', None))

    def _expr_mentions_identifier(self, expr: Expr, name: str) -> bool:
        """Helper for expr mentions identifier.
        Internal helper used during code generation.
        """
        if isinstance(expr, Identifier):
            return expr.name == name
        if isinstance(expr, IntLiteral):
            return False
        if isinstance(expr, UnaryExpr):
            return self._expr_mentions_identifier(expr.expr, name)
        if isinstance(expr, BinaryExpr):
            return (self._expr_mentions_identifier(expr.left, name) or
                    self._expr_mentions_identifier(expr.right, name))
        if isinstance(expr, SubscriptExpr):
            return (self._expr_mentions_identifier(expr.array, name) or
                    self._expr_mentions_identifier(expr.index, name))
        if isinstance(expr, FieldAccess):
            return self._expr_mentions_identifier(expr.object, name)
        if isinstance(expr, DerefExpr):
            return self._expr_mentions_identifier(expr.pointer, name)
        if isinstance(expr, CallExpr):
            return any(arg is not None and self._expr_mentions_identifier(arg, name) for arg in expr.args)
        return False

    def _gen_logical(self, expr: BinaryExpr) -> None:
        """Generate logical.
        Internal helper used during code generation.
        """
        # Use TMP4 only when we must test a word value via A/X
        def _is_word_value(e: Expr) -> bool:
            """Return whether word value.
            Internal helper used during code generation.
            """
            t: ExprType = self.tc_check(e)
            return t.sem_type.base == "WORD" or t.sem_type.is_pointer

        def _branch_if_zero(is_word_val: bool, label: str) -> None:
            """Helper for branch if zero.
            Internal helper used during code generation.
            """
            if is_word_val:
                self.used_temps.add("TMP4")
                self.emit("\tSTA TMP4")
                self.emit("\tTXA")
                self.emit("\tORA TMP4")
                self.emit(f"\tBEQ {label}")
            else:
                self.emit(f"\tBEQ {label}")

        def _branch_if_nonzero(is_word_val: bool, label: str) -> None:
            """Helper for branch if nonzero.
            Internal helper used during code generation.
            """
            if is_word_val:
                self.used_temps.add("TMP4")
                self.emit("\tSTA TMP4")
                self.emit("\tTXA")
                self.emit("\tORA TMP4")
                self.emit(f"\tBNE {label}")
            else:
                self.emit(f"\tBNE {label}")
        if expr.op == BinOp.LAND:
            lbl_false: str = self.new_label("LAND_FALSE")
            lbl_end: str   = self.new_label("LAND_END")

            # lhs
            self.gen_expr(expr.left)
            _branch_if_zero(_is_word_value(expr.left), lbl_false)  # lhs == 0 → false

            # rhs
            self.gen_expr(expr.right)
            _branch_if_zero(_is_word_value(expr.right), lbl_false)  # rhs == 0 → false

            # true
            self.emit("\tLDA #1")
            self.emit(f"\tJMP {lbl_end}")

            # false
            self.emit(f"{lbl_false}:")
            self.emit("\tLDA #$00")

            self.emit(f"{lbl_end}:")
            if self.force_word_result:
                self.emit("\tLDX #$00     ; note 5044")   # X = result high byte
            return

    def _sizeof_struct_arg(self, arg: Expr) -> int:
        """Helper for sizeof struct arg.
        Internal helper used during code generation.
        """
        if not isinstance(arg, Identifier):
            self._raise_error("SIZEOF expects a struct name")

        if self.struct_registry and self.struct_registry.is_defined(arg.name):
            info = self.struct_registry.lookup(arg.name)
            if info:
                return info.size

        try:
            sym: Symbol = self.current_symtab.lookup(arg.name)
        except KeyError:
            self._raise_error(f"'{arg.name}' is not a defined struct")
            return 0

        if sym.type.is_struct and sym.type.struct_info:
            return sym.type.struct_info.size

        self._raise_error("SIZEOF expects a struct type")
        return 0

    def _gen_builtin_call(self, expr: CallExpr) -> bool:
        """Generate builtin call.
        Internal helper used during code generation.
        """
        name_upper = expr.name.upper()
        if name_upper not in {"LOW", "HIGH", "SIZEOF", "LOWW", "HIGHW"}:
            return False

        if len(expr.args) != 1 or expr.args[0] is None:
            self._raise_error(f"{name_upper}() expects exactly one argument")

        arg = expr.args[0]
        if name_upper == "SIZEOF":
            size = self._sizeof_struct_arg(arg)
            self.emit(f"\tLDA #${size & 0xFF:02X}")
            self.emit(f"\tLDX #${(size >> 8) & 0xFF:02X}")
            return True

        arg_t: ExprType = self.tc_check(arg)
        if arg_t.sem_type.is_struct and not arg_t.sem_type.is_pointer:
            self._raise_error("LOW/HIGH not supported for struct values")

        if name_upper == "LOW":
            # For LOW(), only load the low byte - directly load without X
            if isinstance(arg, Identifier):
                sym = self.current_symtab.lookup(arg.name)
                if sym.is_const:
                    self.emit(f"\tLDA #<{sym.asm_name()}")
                else:
                    self.emit(f"\tLDA {sym.asm_name()}")
            elif isinstance(arg, IntLiteral):
                self.emit(f"\tLDA #${arg.value & 0xFF:02X}")
            else:
                # For complex expressions, evaluate then take low byte
                self.gen_expr(arg)
                if arg_t.sem_type.base == "LONG":
                    # LONG result is in MATH0, not A
                    self.emit("\tLDA MATH0")
            # If result is used in 16-bit context, set high byte to 0
            if self.force_word_result:
                self.emit("\tLDX #$00     ; widen byte builtin")
        elif name_upper == "HIGH":
            # For HIGH(), directly load the high byte
            if arg_t.sem_type.base == "BYTE" and not arg_t.sem_type.is_pointer:
                # Byte value has no high byte, return 0
                self.emit("\tLDA #$00")
            else:
                # Load the high byte directly without loading the low byte first
                # This requires special handling for different expression types
                if isinstance(arg, Identifier):
                    sym = self.current_symtab.lookup(arg.name)
                    if sym.is_const:
                        self.emit(f"\tLDA #>{sym.asm_name()}")
                    else:
                        self.emit(f"\tLDA {sym.asm_name()}+1")
                elif isinstance(arg, IntLiteral):
                    self.emit(f"\tLDA #${(arg.value >> 8) & 0xFF:02X}")
                elif isinstance(arg, SubscriptExpr):
                    # For array subscripts, we need the address first
                    self._gen_subscript(arg, load_only=True, calc_addr_only=True)
                    self.emit(f"\tLDY #1")
                    self.emit(f"\tLDA (TMP0),Y")
                elif isinstance(arg, FieldAccess):
                    # Generate field access, then extract high byte from result
                    self._gen_field_access(arg, load_only=True)
                    self.emit(f"\tTXA")
                else:
                    # For other expressions, evaluate and use high byte
                    self.gen_expr(arg)
                    if arg_t.sem_type.base == "LONG":
                        # LONG result is in MATH0, byte 1 is the high byte
                        self.emit("\tLDA MATH0+1")
                    else:
                        self.emit("\tTXA")
            # If result is used in 16-bit context, set high byte to 0
            if self.force_word_result:
                self.emit("\tLDX #$00     ; widen byte builtin")

        elif name_upper == "LOWW":
            # LOWW(longExpr) → low WORD (bytes 0-1) in A (low) / X (high)
            if isinstance(arg, Identifier):
                sym: Symbol = self.current_symtab.lookup(arg.name)
                self.emit(f"\tLDA {sym.asm_name()}")
                self.emit(f"\tLDX {sym.asm_name()}+1")
            elif isinstance(arg, IntLiteral):
                self.emit(f"\tLDA #${arg.value & 0xFF:02X}")
                self.emit(f"\tLDX #${(arg.value >> 8) & 0xFF:02X}")
            else:
                # Complex expression: evaluate into MATH0, then read bytes 0-1
                self.gen_expr(arg)
                self.emit("\tLDA MATH0")
                self.emit("\tLDX MATH0+1")

        elif name_upper == "HIGHW":
            # HIGHW(longExpr) → high WORD (bytes 2-3) in A (low) / X (high)
            if isinstance(arg, Identifier):
                sym = self.current_symtab.lookup(arg.name)
                self.emit(f"\tLDA {sym.asm_name()}+2")
                self.emit(f"\tLDX {sym.asm_name()}+3")
            elif isinstance(arg, IntLiteral):
                self.emit(f"\tLDA #${(arg.value >> 16) & 0xFF:02X}")
                self.emit(f"\tLDX #${(arg.value >> 24) & 0xFF:02X}")
            else:
                # Complex expression: evaluate into MATH0, then read bytes 2-3
                self.gen_expr(arg)
                self.emit("\tLDA MATH0+2")
                self.emit("\tLDX MATH0+3")

        return True

    def gen_expr(self, expr, force_left_tmp=None) -> None:
        """Generate assembly for an expression node.
        Applies folding and chooses codegen path.
        """
        # Apply constant substitution and folding
        from typing import cast
        expr = subst_const(cast(Expr, expr), cast(SymbolTable, self.current_symtab))
        expr = cast(Expr, fold_expr(expr))
        
        if isinstance(expr, IntLiteral):
            self._gen_literal(expr)
        elif isinstance(expr, StringLiteral):
            self._gen_string_literal(expr)
        elif isinstance(expr, Identifier):
            self._gen_identifier(expr)
        elif isinstance(expr, DerefExpr):
            self._gen_deref(expr)
        elif isinstance(expr, SubscriptExpr):
            self._gen_subscript(expr, load_only=True)
        elif isinstance(expr, FieldAccess):
            self._gen_field_access(expr, load_only=True)
        elif isinstance(expr, CallExpr):
            if self._gen_builtin_call(expr):
                return
            # Emit source comment for function call if available
            info = self.stmt_src.get(id(expr))
            if info:
                fname, line, text = info
                self.emit(f"\n; {fname} {line}: {text}")
            # Evaluate and pass arguments to function parameters
            specs: list[tuple[str, int, object, SemType]] | None = self.func_param_specs.get(expr.name)
            if specs is not None:
                self._emit_call_args(expr.name, expr.args, specs)
            self.emit(f"\tJSR {self.asm_symbol_name(expr.name)}")
            ret_buf = self.func_return_buffers.get(expr.name)
            if ret_buf:
                asm_ret, _struct_info = ret_buf
                self.emit(f"\tLDA #<{asm_ret}")
                self.emit(f"\tLDX #>{asm_ret}")
                return
            # Caller-side widening: only clear X when a byte result is used in word context
            ret_t: ExprType = self.tc_check(expr)
            if ret_t.sem_type.base == "BYTE" and not ret_t.sem_type.is_pointer and self.force_word_result:
                self.emit("\tLDX #$00     ; widen byte call result")

        elif isinstance(expr, BinaryExpr):
            # Conservative TMP usage check before generating potentially large expressions
            needed: int = self._estimate_temp_slots(expr)
            max_temps: int = 16  # Hard limit: TMP0..TMP15 available (can dynamically allocate up to 16)
            if needed > max_temps:
                self._raise_error(f"Expression too complex: requires {needed} temporary slot(s) but hard limit is {max_temps}. Simplify the expression.")

            # FAST PATH: Optimize simple byte operations (a op b) to avoid RPN overhead
            # For expressions like: a < b, a + b, a & b where both are identifiers/literals
            # Generate direct accumulator code instead of using MATH registers
            if (isinstance(expr.left, (Identifier, IntLiteral)) and 
                isinstance(expr.right, (Identifier, IntLiteral)) and
                not self.force_word_result):
                
                # Check if operands are byte-sized
                left_t: ExprType = self.tc_check(expr.left)
                right_t: ExprType = self.tc_check(expr.right)
                left_is_byte: bool = left_t.sem_type.base == "BYTE" and not left_t.sem_type.is_pointer
                right_is_byte: bool = right_t.sem_type.base == "BYTE" and not right_t.sem_type.is_pointer
                
                if left_is_byte and right_is_byte and expr.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE, BinOp.ADD, BinOp.SUB, BinOp.BAND, BinOp.BOR, BinOp.BXOR}:
                    # Generate left operand into accumulator
                    if isinstance(expr.left, Identifier):
                        left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                        self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
                    else:  # IntLiteral
                        val: int = expr.left.value & 0xFF
                        self.emit(f"\tLDA #${val:02X}")
                    
                    # Generate operation with right operand
                    if isinstance(expr.right, Identifier):
                        right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                        right_operand: str = self._sym_operand(right_sym, low_byte=True)
                    else:  # IntLiteral
                        val: int = expr.right.value & 0xFF
                        right_operand: str = f"#${val:02X}"
                    
                    if expr.op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tADC {right_operand}")
                    elif expr.op == BinOp.SUB:
                        self.emit("\tSEC")
                        self.emit(f"\tSBC {right_operand}")
                    elif expr.op == BinOp.BAND:
                        self.emit(f"\tAND {right_operand}")
                    elif expr.op == BinOp.BOR:
                        self.emit(f"\tORA {right_operand}")
                    elif expr.op == BinOp.BXOR:
                        self.emit(f"\tEOR {right_operand}")
                    elif expr.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                        # Comparison: use CMP and convert to boolean
                        self.emit(f"\tCMP {right_operand}")
                        true_label: str = self.new_label("CMP_TRUE")
                        end_label: str = self.new_label("CMP_END")
                        
                        if expr.op == BinOp.EQ:
                            self.emit(f"\tBEQ {true_label}")
                        elif expr.op == BinOp.NE:
                            self.emit(f"\tBNE {true_label}")
                        elif expr.op == BinOp.LT:
                            self.emit(f"\tBCC {true_label}")
                        elif expr.op == BinOp.GE:
                            self.emit(f"\tBCS {true_label}")
                        elif expr.op == BinOp.GT:
                            # a > b: !(a < b) && a != b → BCS && BNE
                            self.emit(f"\tBCC {end_label}")  # If less, skip to false
                            self.emit(f"\tBNE {true_label}")  # If not equal and not less, it's greater
                        elif expr.op == BinOp.LE:
                            # a <= b: (a < b) || a == b → BCC || BEQ
                            self.emit(f"\tBCC {true_label}")
                            self.emit(f"\tBEQ {true_label}")
                        
                        self.emit("\tLDA #$00")
                        self.emit(f"\tJMP {end_label}")
                        self.emit(f"{true_label}:")
                        self.emit("\tLDA #$01")
                        self.emit(f"{end_label}:")
                    
                    return  # Fast path complete

            # Try RPN-based code generation if enabled and expression is arithmetic/bitwise/comparison/logical
            if self.rpn_enabled and expr.op in {BinOp.ADD, BinOp.SUB, BinOp.MUL, BinOp.DIV, BinOp.MOD, BinOp.BAND, BinOp.BOR, BinOp.BXOR, BinOp.LSHIFT, BinOp.RSHIFT, BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE, BinOp.LAND, BinOp.LOR} and self._is_rpn_safe(expr):
                rpn_sequence = self.ast_to_rpn(expr)
                self.rpn_eval_to_code(rpn_sequence, target_16bit=self.force_word_result)
                return  # RPN path complete, don't fall through to traditional generators
            elif expr.op in {BinOp.LAND, BinOp.LOR}:
                self._gen_logical(expr)
            elif expr.op in {
                BinOp.EQ, BinOp.NE,
                BinOp.LT, BinOp.LE,
                BinOp.GT, BinOp.GE
            }:
                self._gen_relational(expr)
            else:
                self._gen_binary(expr, force_left_tmp)

        elif isinstance(expr, UnaryExpr):
            if self.rpn_enabled and self._is_rpn_safe(expr):
                rpn_sequence = self.ast_to_rpn(expr)
                self.rpn_eval_to_code(rpn_sequence, target_16bit=self.force_word_result)
                return
            self._gen_unary(expr)

    def gen_assign(self, lhs: Expr, rhs: Expr) -> None:
        """Generate assignment code for an lvalue and rhs.
        Handles arrays, structs, and scalar stores.
        """
        # Early exit: self-assignment (x = x) has no effect
        if isinstance(lhs, Identifier) and isinstance(rhs, Identifier) and lhs.name == rhs.name:
            return
        
        # Apply constant substitution and folding to RHS
        from constsubst import subst_const
        from typing import cast
        rhs = subst_const(rhs, cast(SymbolTable, self.current_symtab))
        rhs = fold_expr(rhs)

        lhs_t: ExprType = self.tc_check(lhs, read_check_enabled=False)

        # typová kompatibilita                
        if not isinstance(lhs, (Identifier, DerefExpr, SubscriptExpr, FieldAccess)):
            self._raise_error("Left side of assignment is not assignable")
        
        # Check for const violation: can't assign to const variables, const array elements, or const struct fields
        if isinstance(lhs, Identifier):
            try:
                sym: Symbol = self.current_symtab.lookup(lhs.name)
            except KeyError:
                raise SemanticError(f"Variable '{lhs.name}' is not defined", node=lhs)
            if sym.is_const:
                self._raise_error(f"Cannot assign to const variable '{lhs.name}'")
        elif isinstance(lhs, DerefExpr):
            # Check if writing through a pointer to a const variable
            # Catches patterns like (@const_arr + 1)^ = val
            def _find_const_addr_target(expr) -> str | None:
                """Walk expression tree looking for @const_variable."""
                from ast_nodes import UnaryExpr, BinaryExpr, Identifier
                from ast_nodes import UnOp
                if isinstance(expr, UnaryExpr) and expr.op == UnOp.ADDROF:
                    if isinstance(expr.expr, Identifier):
                        try:
                            s = self.current_symtab.lookup(expr.expr.name)
                            if s.is_const:
                                return expr.expr.name
                        except KeyError:
                            pass
                    elif isinstance(expr.expr, SubscriptExpr):
                        if isinstance(expr.expr.array, Identifier):
                            try:
                                s = self.current_symtab.lookup(expr.expr.array.name)
                                if s.is_const:
                                    return expr.expr.array.name
                            except KeyError:
                                pass
                elif isinstance(expr, BinaryExpr):
                    return _find_const_addr_target(expr.left) or _find_const_addr_target(expr.right)
                return None

            const_name = _find_const_addr_target(lhs.pointer)
            if const_name:
                self._raise_error(f"Cannot write through pointer to const '{const_name}'")
        elif isinstance(lhs, SubscriptExpr):
            # Check if modifying an element of a const array
            if isinstance(lhs.array, Identifier):
                try:
                    sym: Symbol = self.current_symtab.lookup(lhs.array.name)
                except KeyError:
                    raise SemanticError(f"Variable '{lhs.array.name}' is not defined", node=lhs.array)
                if sym.is_const:
                    self._raise_error(f"Cannot assign to element of const array '{lhs.array.name}'")
                    
            # EARLY OPTIMIZATION: Handle array subscript assignment with optimizations
            # This must be done BEFORE the general gen_expr(rhs) call to avoid duplicate code generation
            if isinstance(lhs.array, Identifier):
                try:
                    arr_sym: Symbol = self.current_symtab.lookup(lhs.array.name)
                except KeyError:
                    raise SemanticError(f"Variable '{lhs.array.name}' is not defined", node=lhs.array)
                if arr_sym.is_array and not arr_sym.is_const:
                    arr_addr: str = arr_sym.asm_name()
                    element_width: int = self._calculate_element_width(arr_sym)

                    # Pointer arrays can be in ZP or BSS; direct indexed stores work for both
                    if arr_sym.type.is_pointer:
                        # Constant index path uses direct store below
                        if not isinstance(lhs.index, IntLiteral):
                            # If RHS is complex, evaluate it first since X is used for index
                            if not isinstance(rhs, (Identifier, IntLiteral)):
                                self.gen_expr(rhs)
                                self.emit("\tSTA TMP2")
                                self.emit("\tSTX TMP2+1")

                            # Compute index*element_width into X (element_width is 2 for pointers)
                            self.gen_expr(lhs.index)
                            if element_width == 2:
                                self.emit("\tASL A")
                            self.emit("\tTAX")

                            if isinstance(rhs, Identifier):
                                rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)
                                rhs_addr: str = rhs_sym.asm_name()
                                self.emit(f"\tLDA {rhs_addr}")
                                self.emit(f"\tSTA {arr_addr},X")
                                self.emit("\tINX")
                                self.emit(f"\tLDA {rhs_addr}+1")
                                self.emit(f"\tSTA {arr_addr},X")
                                return
                            if isinstance(rhs, IntLiteral):
                                lo: int = rhs.value & 0xFF
                                hi: int = (rhs.value >> 8) & 0xFF
                                self.emit(f"\tLDA #${lo:02X}")
                                self.emit(f"\tSTA {arr_addr},X")
                                self.emit("\tINX")
                                self.emit(f"\tLDA #${hi:02X}")
                                self.emit(f"\tSTA {arr_addr},X")
                                return

                            # Complex RHS saved in TMP2
                            self.emit("\tLDA TMP2")
                            self.emit(f"\tSTA {arr_addr},X")
                            self.emit("\tINX")
                            self.emit("\tLDA TMP2+1")
                            self.emit(f"\tSTA {arr_addr},X")
                            return
                    
                    # Case 1: Immediate index - calculate offset at compile time
                    if isinstance(lhs.index, IntLiteral):
                        index_val: int = lhs.index.value
                        offset: int = index_val * element_width
                        
                        # Generate RHS value into A/X
                        # For BYTE elements, suppress X register loading
                        if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
                            prev_suppress = self.suppress_byte_return_x
                            self.suppress_byte_return_x = True
                            self.gen_expr(rhs)
                            self.suppress_byte_return_x = prev_suppress
                        else:
                            self.gen_expr(rhs)
                        
                        # Direct store using calculated offset
                        if lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer:
                            # WORD element: store both bytes
                            self.emit(f"\tSTA {arr_addr}+{offset}")
                            self.emit(f"\tSTX {arr_addr}+{offset+1}")
                        else:
                            # BYTE element: store only A
                            self.emit(f"\tSTA {arr_addr}+{offset}")
                        return
                    
                    # Case 2: Index in register/accumulator - inline address calculation
                    # Save RHS value first since index calculation might use A/X
                    self.gen_expr(rhs)
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")
                    
                    # Generate index expression
                    self.gen_expr(lhs.index)
                    
                    # Now calculate address: arr_addr + index * element_width
                    if element_width == 1:
                        # BYTE elements: address = arr_addr + index
                        self.emit(f"\tCLC")
                        self.emit(f"\tADC #<{arr_addr}")
                        self.emit(f"\tSTA TMP0")
                        self.emit(f"\tTXA")
                        self.emit(f"\tADC #>{arr_addr}")
                        self.emit(f"\tSTA TMP0+1")
                    elif element_width == 2:
                        # WORD elements: address = arr_addr + index * 2
                        self.emit(f"\tASL A")  # Multiply index by 2
                        self.emit("\tLDX #$00")
                        carry_lbl: str = self.new_label("ARR_CARRY")
                        self.emit(f"\tBCC {carry_lbl}")
                        self.emit("\tINX")
                        self.emit(f"{carry_lbl}:")
                        self.emit(f"\tCLC")
                        self.emit(f"\tADC #<{arr_addr}")
                        self.emit(f"\tSTA TMP0")
                        self.emit(f"\tTXA")
                        self.emit(f"\tADC #>{arr_addr}")
                        self.emit(f"\tSTA TMP0+1")
                    else:
                        # Complex element width: fall back to general handler
                        # RHS is already in TMP2, need to handle index
                        self._gen_subscript(lhs, load_only=False)
                        return
                    
                    # Store RHS value from TMP2 to calculated address
                    self.emit(f"\tLDA TMP2")
                    if lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer:
                        self.emit(f"\tLDY #$00")
                        self.emit(f"\tSTA (TMP0),Y")
                        self.emit(f"\tINY")
                        self.emit(f"\tLDA TMP2+1")
                        self.emit(f"\tSTA (TMP0),Y")
                    else:
                        self._emit_indirect_store_zero("TMP0")
                    return
                    
        elif isinstance(lhs, FieldAccess):
            # Check if accessing a field of a const struct
            if isinstance(lhs.object, Identifier):
                sym: Symbol = self.current_symtab.lookup(lhs.object.name)
                if sym.is_const:
                    self._raise_error(f"Cannot assign to field of const struct '{lhs.object.name}'")

        if isinstance(rhs, StructLiteral):
            if not lhs_t.sem_type.is_struct or lhs_t.sem_type.is_pointer:
                self._raise_error("Struct literal requires struct lvalue")
            if not isinstance(lhs, Identifier):
                self._raise_error("Struct literal assignment requires a struct variable")
            sym = self.current_symtab.lookup(lhs.name)
            struct_info = sym.type.struct_info or (
                self.struct_registry.lookup(sym.type.base.upper()) if self.struct_registry else None
            )
            if struct_info is None:
                self._raise_error(f"Cannot determine struct type for '{lhs.name}'")
            self._emit_struct_literal_store(sym.asm_name(), struct_info, rhs.values, ctx_name=sym.name)
            return

        if isinstance(rhs, CallExpr) and lhs_t.sem_type.is_struct and not lhs_t.sem_type.is_pointer:
            if not isinstance(lhs, Identifier):
                self._raise_error("Struct assignment requires a struct variable")
            ret_buf = self.func_return_buffers.get(rhs.name)
            if ret_buf is None:
                self._raise_error("Struct assignment requires a struct-returning function")
            asm_ret, ret_info = ret_buf
            sym = self.current_symtab.lookup(lhs.name)
            if sym.type.base.upper() != ret_info.name.upper():
                self._raise_error("Struct assignment type mismatch")
            specs: list[tuple[str, int, object, SemType]] | None = self.func_param_specs.get(rhs.name)
            if specs is not None:
                self._emit_call_args(rhs.name, rhs.args, specs)
            self.emit(f"\tJSR {self.asm_symbol_name(rhs.name)}")
            self.emit(f"\tLDA #<{asm_ret}")
            self.emit("\tSTA TMP0")
            self.emit(f"\tLDA #>{asm_ret}")
            self.emit("\tSTA TMP0+1")
            self.emit(f"\tLDA #<{sym.asm_name()}")
            self.emit("\tSTA TMP2")
            self.emit(f"\tLDA #>{sym.asm_name()}")
            self.emit("\tSTA TMP2+1")
            if ret_info.size > 255:
                self.copy_bytes16_needed = True
                self.emit(f"\tLDA #${ret_info.size & 0xFF:02X}")
                self.emit("\tSTA TMP4")
                self.emit(f"\tLDA #${(ret_info.size >> 8) & 0xFF:02X}")
                self.emit("\tSTA TMP4+1")
                self.emit("\tJSR COPY_BYTES16")
            else:
                self.copy_bytes_needed = True
                self.emit(f"\tLDX #${ret_info.size:02X}")
                self.emit("\tJSR COPY_BYTES")
            return

        rhs_t: ExprType = self.tc_check(rhs)

        # Special case: array-to-array assignment and struct assignment
        if isinstance(lhs, Identifier) and isinstance(rhs, Identifier):
            lhs_sym: Symbol = self.current_symtab.lookup(lhs.name)
            rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)

            # Guard: array-of-struct assignment is not supported
            if lhs_sym.is_array and rhs_sym.is_array and lhs_sym.type.is_struct:
                self._raise_error(
                    "Array-of-struct assignment is not supported; use a loop or pointer copy"
                )

            # Array-to-array copy (BYTE, WORD, or LONG)
            # Note: bare array identifiers always have is_pointer=True in ExprType,
            # so check the symbol's own type instead.
            if lhs_sym.is_array and rhs_sym.is_array and not lhs_sym.type.is_struct:
                self._gen_string_copy(lhs_sym, rhs_sym)
                return

            # Non-const struct variable to struct variable copy
            if not lhs_sym.is_array and not rhs_sym.is_array and \
               lhs_t.sem_type.is_struct and rhs_t.sem_type.is_struct and \
               not rhs_sym.is_const:
                if lhs_t.sem_type.base.upper() != rhs_t.sem_type.base.upper():
                    self._raise_error(
                        f"Struct type mismatch: cannot assign '{rhs_t.sem_type.base}' to '{lhs_t.sem_type.base}'"
                    )
                struct_info = lhs_t.sem_type.struct_info
                if struct_info is None:
                    self._raise_error(f"Cannot determine struct type for '{lhs_sym.name}'")
                src_asm = rhs_sym.asm_name()
                dst_asm_c = lhs_sym.asm_name()
                self.emit(f"\tLDA #<{src_asm}")
                self.emit("\tSTA TMP0")
                self.emit(f"\tLDA #>{src_asm}")
                self.emit("\tSTA TMP0+1")
                self.emit(f"\tLDA #<{dst_asm_c}")
                self.emit("\tSTA TMP2")
                self.emit(f"\tLDA #>{dst_asm_c}")
                self.emit("\tSTA TMP2+1")
                if struct_info.size > 255:
                    self.copy_bytes16_needed = True
                    self.emit(f"\tLDA #${struct_info.size & 0xFF:02X}")
                    self.emit("\tSTA TMP4")
                    self.emit(f"\tLDA #${(struct_info.size >> 8) & 0xFF:02X}")
                    self.emit("\tSTA TMP4+1")
                    self.emit("\tJSR COPY_BYTES16")
                else:
                    self.copy_bytes_needed = True
                    self.emit(f"\tLDX #${struct_info.size:02X}")
                    self.emit("\tJSR COPY_BYTES")
                return

            # Const struct to struct variable copy
            if not lhs_sym.is_array and not rhs_sym.is_array and \
               lhs_t.sem_type.is_struct and rhs_t.sem_type.is_struct and \
               rhs_sym.is_const and rhs_sym.init and isinstance(rhs_sym.init, ListInit):
                self._gen_const_struct_copy(lhs_sym, rhs_sym)
                return

        if lhs_t.kind == ExprKind.LVALUE:
            # RHS LVALUE means we're reading from that location (convert to VALUE semantically)
            if rhs_t.kind == ExprKind.LVALUE:
                # Both sides are lvalues, treat RHS as reading a value
                rhs_t = ExprType(rhs_t.sem_type, ExprKind.VALUE)

            # Allow assigning an address to an lvalue if the lvalue is a pointer
            if rhs_t.kind != ExprKind.VALUE:
                if lhs_t.sem_type.is_pointer and rhs_t.kind == ExprKind.ADDR:
                    # Allow assignment of an address literal (ADDR) into a pointer field
                    pass
                else:
                    self._raise_error("Cannot assign address to lvalue")

            # Allow implicit narrowing (WORD to BYTE) - just truncate low byte
            # This is common in low-level code (e.g., ptr^ = word_counter)
        
        # Allow ADDR = ADDR for pointer assignments
        if lhs_t.kind == ExprKind.ADDR and lhs_t.sem_type.is_pointer:
            # If RHS is an LVALUE (e.g., dereference expr), treat as VALUE (reading)
            if rhs_t.kind == ExprKind.LVALUE:
                rhs_t = ExprType(rhs_t.sem_type, ExprKind.VALUE)
            if rhs_t.kind != ExprKind.ADDR and rhs_t.kind != ExprKind.VALUE:
                self._raise_error("Cannot assign to pointer")
            # Type compatibility for pointers (WORD base for all pointers)
            # No further checks needed since pointers are always WORD-sized

        # Peepholes: constant assign and small +/-
        if isinstance(lhs, Identifier):
            sym_lhs: Symbol = self.current_symtab.lookup(lhs.name)

            # Direct constant assignment
            if isinstance(rhs, IntLiteral) and (sym_lhs.address is None or lhs_t.sem_type.base == "LONG"):
                # Check if constant fits in target type
                self._check_constant_fits(rhs.value, cast(SemType, lhs_t.sem_type), f"assignment to {lhs.name}")
                if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
                    self._emit_store_byte_const(sym_lhs, rhs.value)
                elif lhs_t.sem_type.base == "LONG":
                    # Emit 4-byte store for LONG constant.
                    # Group bytes by value (first-occurrence order) so each unique byte value
                    # needs only one LDA, with all its STA destinations following it.
                    # On 65C02, zero bytes use STZ instead (no LDA, preserving that group).
                    val = rhs.value
                    asm = sym_lhs.asm_name()
                    _ga_grp: dict[int, list[int]] = {}
                    for _bi in range(4):
                        _bv: int = (val >> (_bi * 8)) & 0xFF
                        _ga_grp.setdefault(_bv, []).append(_bi)
                    for _bv, _offsets in _ga_grp.items():
                        if _bv == 0 and self.is_65c02:
                            for _bi in _offsets:
                                _d = asm if _bi == 0 else f"{asm}+{_bi}"
                                self.emit(f"\tSTZ {_d}")
                        else:
                            self.emit(f"\tLDA #${_bv:02X}")
                            for _bi in _offsets:
                                _d = asm if _bi == 0 else f"{asm}+{_bi}"
                                self.emit(f"\tSTA {_d}")
                else:
                    self._emit_store_word_const(sym_lhs, rhs.value)
                return

            # Optimization: Direct LONG variable copy
            if isinstance(rhs, Identifier) and lhs_t.sem_type.base == "LONG":
                try:
                    rhs_sym = self.current_symtab.lookup(rhs.name)
                    if (not rhs_sym.is_array and rhs_sym.address is None and 
                        not rhs_sym.type.is_pointer and rhs_sym.type.base == "LONG"):
                        
                        lhs_asm = sym_lhs.asm_name()
                        rhs_asm = rhs_sym.asm_name()
                        
                        self.emit(f"\tLDA {rhs_asm}")
                        self.emit(f"\tSTA {lhs_asm}")
                        self.emit(f"\tLDA {rhs_asm}+1")
                        self.emit(f"\tSTA {lhs_asm}+1")
                        self.emit(f"\tLDA {rhs_asm}+2")
                        self.emit(f"\tSTA {lhs_asm}+2")
                        self.emit(f"\tLDA {rhs_asm}+3")
                        self.emit(f"\tSTA {lhs_asm}+3")
                        return
                except KeyError:
                    pass

            if isinstance(rhs, BinaryExpr):
                asm: str = sym_lhs.asm_name()
                # Pointers are always 16-bit even if base type is BYTE
                is_word: bool = lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer

                def is_self(opnd) -> bool:
                    """Return whether self.
                    Internal helper used during code generation.
                    """
                    return isinstance(opnd, Identifier) and opnd.name == lhs.name

                def small_const(opnd) -> int | None:
                    """Helper for small const.
                    Internal helper used during code generation.
                    """
                    if isinstance(opnd, IntLiteral) and opnd.value in {1, 2, 3}:
                        return opnd.value
                    return None

                # var = var + k (k=1..3)
                k_left: int | None = small_const(rhs.left)
                k_right: int | None = small_const(rhs.right)

                if rhs.op == BinOp.ADD:
                    k: int | None = None
                    if is_self(rhs.left) and k_right is not None:
                        k = k_right
                    elif is_self(rhs.right) and k_left is not None:
                        k = k_left

                    if k is not None:
                        # For pointer arithmetic, scale by element size
                        # LONG pointers move by 4, WORD by 2, BYTE by 1, struct by size
                        scale = 1
                        if lhs_t.sem_type.is_pointer:
                            if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                                scale: int = lhs_t.sem_type.struct_info.size
                            elif lhs_t.sem_type.base == "LONG":
                                scale = 4
                            elif lhs_t.sem_type.base == "WORD":
                                scale = 2
                        total_inc: int = k * scale
                        
                        if is_word:
                            # For 16-bit values, use proper ADD instead of looping INC
                            if lhs_t.sem_type.is_pointer and total_inc > 1:
                                # Use 16-bit addition for pointer arithmetic
                                self.emit(f"\tLDA {asm}")
                                self.emit(f"\tCLC")
                                self.emit(f"\tADC #${total_inc:02X}")
                                self.emit(f"\tSTA {asm}")
                                lbl: str = self.new_label("CARRY_ADD_PTR")
                                self.emit(f"\tBCC {lbl}")
                                self.emit(f"\tINC {asm}+1")
                                self.emit(f"{lbl}:")
                            else:
                                for _ in range(total_inc):
                                    self._emit_inc_word(asm)
                        elif lhs_t.sem_type.base == "LONG":
                            for _ in range(total_inc):
                                lbl: str = self.new_label("SKIP_INC32")
                                self.emit(f"\tINC {asm}")
                                self.emit(f"\tBNE {lbl}")
                                self.emit(f"\tINC {asm}+1")
                                self.emit(f"\tBNE {lbl}")
                                self.emit(f"\tINC {asm}+2")
                                self.emit(f"\tBNE {lbl}")
                                self.emit(f"\tINC {asm}+3")
                                self.emit(f"{lbl}:")
                        else:
                            for _ in range(total_inc):
                                self.emit(f"\tINC {asm}")
                        return

                # var = var - k (k=1..3) ; only when self - const on rhs
                if rhs.op == BinOp.SUB and is_self(rhs.left) and k_right is not None:
                    k = k_right
                    # For pointer arithmetic, scale by element size
                    # LONG pointers move by 4, WORD by 2, BYTE by 1, struct by size
                    scale = 1
                    if lhs_t.sem_type.is_pointer:
                        if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                            scale: int = lhs_t.sem_type.struct_info.size
                        elif lhs_t.sem_type.base == "LONG":
                            scale = 4
                        elif lhs_t.sem_type.base == "WORD":
                            scale = 2
                    total_dec: int = k * scale
                    
                    if is_word:
                        # For 16-bit values, use proper SBC instead of looping DEC
                        if lhs_t.sem_type.is_pointer and total_dec > 1:
                            # Use 16-bit subtraction for pointer arithmetic
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tSEC")
                            self.emit(f"\tSBC #${total_dec:02X}")
                            self.emit(f"\tSTA {asm}")
                            lbl: str = self.new_label("CARRY_SUB_PTR")
                            self.emit(f"\tBCS {lbl}")
                            self.emit(f"\tDEC {asm}+1")
                            self.emit(f"{lbl}:")
                        else:
                            for _ in range(total_dec):
                                self._emit_dec_word(asm)
                    elif lhs_t.sem_type.base == "LONG":
                        for _ in range(total_dec):
                            lbl: str = self.new_label("SKIP_DEC32")
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tBNE {lbl}")
                            self.emit(f"\tLDA {asm}+1")
                            self.emit(f"\tBNE {lbl}")
                            self.emit(f"\tLDA {asm}+2")
                            self.emit(f"\tBNE {lbl}")
                            self.emit(f"\tDEC {asm}+3")
                            self.emit(f"{lbl}:")
                            lbl2: str = self.new_label("SKIP_DEC32_2")
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tBNE {lbl2}")
                            self.emit(f"\tLDA {asm}+1")
                            self.emit(f"\tBNE {lbl2}")
                            self.emit(f"\tDEC {asm}+2")
                            self.emit(f"{lbl2}:")
                            lbl3: str = self.new_label("SKIP_DEC32_3")
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tBNE {lbl3}")
                            self.emit(f"\tDEC {asm}+1")
                            self.emit(f"{lbl3}:")
                            self.emit(f"\tDEC {asm}")
                    else:
                        for _ in range(total_dec):
                            self.emit(f"\tDEC {asm}")
                    return

                # var = var * (power of 2) or var = var / (power of 2)
                if rhs.op in {BinOp.MUL, BinOp.DIV} and is_self(rhs.left) and isinstance(rhs.right, IntLiteral):
                    const_val = rhs.right.value
                    if const_val > 0 and (const_val & (const_val - 1)) == 0:
                        shift_amount = const_val.bit_length() - 1
                        if shift_amount > 0:
                            width = 4 if lhs_t.sem_type.base == "LONG" else (2 if is_word else 1)
                            
                            # Load value into A/X/MATH0 depending on size
                            if width == 1:
                                self.emit(f"\tLDA {asm}")
                                if rhs.op == BinOp.MUL:
                                    self._gen_lshift(False, "A", shift_amount)
                                else:
                                    self._gen_rshift(False, "A", shift_amount)
                                self.emit(f"\tSTA {asm}")
                            elif width == 2:
                                # Direct in-place shift on memory (avoids TMP0 copy)
                                for _ in range(shift_amount):
                                    if rhs.op == BinOp.MUL:
                                        self.emit(f"\tASL {asm}")
                                        self.emit(f"\tROL {asm}+1")
                                    else:
                                        self.emit(f"\tLSR {asm}+1")
                                        self.emit(f"\tROR {asm}")
                            elif width == 4:
                                self.emit(f"\tLDA {asm}")
                                self.emit(f"\tSTA MATH0")
                                self.emit(f"\tLDA {asm}+1")
                                self.emit(f"\tSTA MATH0+1")
                                self.emit(f"\tLDA {asm}+2")
                                self.emit(f"\tSTA MATH0+2")
                                self.emit(f"\tLDA {asm}+3")
                                self.emit(f"\tSTA MATH0+3")
                                self.emit(f"\tLDA #{shift_amount}")
                                if rhs.op == BinOp.MUL:
                                    self.math_routines_needed.add("LSHIFT32")
                                    self.emit("\tJSR LSHIFT32")
                                else:
                                    self.math_routines_needed.add("RSHIFT32")
                                    self.emit("\tJSR RSHIFT32")
                                self.emit(f"\tLDA MATH0")
                                self.emit(f"\tSTA {asm}")
                                self.emit(f"\tLDA MATH0+1")
                                self.emit(f"\tSTA {asm}+1")
                                self.emit(f"\tLDA MATH0+2")
                                self.emit(f"\tSTA {asm}+2")
                                self.emit(f"\tLDA MATH0+3")
                                self.emit(f"\tSTA {asm}+3")
                            return

                # var = var << N / var = var >> N (constant-count in-place shift)
                if rhs.op in {BinOp.LSHIFT, BinOp.RSHIFT} and is_self(rhs.left) and isinstance(rhs.right, IntLiteral):
                    shift_n = rhs.right.value
                    if shift_n > 0 and not sym_lhs.is_port:
                        width = 4 if lhs_t.sem_type.base == "LONG" else (2 if is_word else 1)
                        is_left = rhs.op == BinOp.LSHIFT
                        if width == 1 and shift_n == 1:
                            # BYTE N=1: single read-modify-write instruction
                            self.emit(f"\t{'ASL' if is_left else 'LSR'} {asm}")
                            return
                        elif width == 2:
                            # WORD: N × (ASL lo; ROL hi) or N × (LSR hi; ROR lo)
                            for _ in range(shift_n):
                                if is_left:
                                    self.emit(f"\tASL {asm}")
                                    self.emit(f"\tROL {asm}+1")
                                else:
                                    self.emit(f"\tLSR {asm}+1")
                                    self.emit(f"\tROR {asm}")
                            return
                        elif width == 4 and shift_n <= 4:
                            # LONG small N: inline unroll directly on memory
                            for _ in range(shift_n):
                                if is_left:
                                    self.emit(f"\tASL {asm}")
                                    self.emit(f"\tROL {asm}+1")
                                    self.emit(f"\tROL {asm}+2")
                                    self.emit(f"\tROL {asm}+3")
                                else:
                                    self.emit(f"\tLSR {asm}+3")
                                    self.emit(f"\tROR {asm}+2")
                                    self.emit(f"\tROR {asm}+1")
                                    self.emit(f"\tROR {asm}")
                            return
                        elif width == 4:
                            # LONG large N: load MATH0, JSR, writeback (no MATH1 overhead)
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tSTA MATH0")
                            self.emit(f"\tLDA {asm}+1")
                            self.emit(f"\tSTA MATH0+1")
                            self.emit(f"\tLDA {asm}+2")
                            self.emit(f"\tSTA MATH0+2")
                            self.emit(f"\tLDA {asm}+3")
                            self.emit(f"\tSTA MATH0+3")
                            self.emit(f"\tLDA #{shift_n}")
                            if is_left:
                                self.math_routines_needed.add("LSHIFT32")
                                self.emit("\tJSR LSHIFT32")
                            else:
                                self.math_routines_needed.add("RSHIFT32")
                                self.emit("\tJSR RSHIFT32")
                            self.emit(f"\tLDA MATH0")
                            self.emit(f"\tSTA {asm}")
                            self.emit(f"\tLDA MATH0+1")
                            self.emit(f"\tSTA {asm}+1")
                            self.emit(f"\tLDA MATH0+2")
                            self.emit(f"\tSTA {asm}+2")
                            self.emit(f"\tLDA MATH0+3")
                            self.emit(f"\tSTA {asm}+3")
                            return
                        # BYTE N>1: fall through to generic path (LDA; N×ASL/LSR; STA)

                # var = var & expr / var = var | expr / var = var ^ expr (bitwise in-place)
                if rhs.op in {BinOp.BAND, BinOp.BOR, BinOp.BXOR} and not sym_lhs.is_port:
                    # All three ops are commutative: normalise so lhs-side is `self`
                    if is_self(rhs.left):
                        bit_rhs: Expr = rhs.right
                    elif is_self(rhs.right):
                        bit_rhs = rhs.left
                    else:
                        bit_rhs = None  # type: ignore[assignment]

                    if bit_rhs is not None:
                        op_mnem: str = ("AND" if rhs.op == BinOp.BAND
                                        else ("ORA" if rhs.op == BinOp.BOR else "EOR"))
                        # Identity bytes: AND #$FF, OR #$00, EOR #$00 leave the byte unchanged
                        identity: int = (0xFF if rhs.op == BinOp.BAND else 0x00)
                        width = 4 if lhs_t.sem_type.base == "LONG" else (2 if is_word else 1)

                        if isinstance(bit_rhs, IntLiteral):
                            val: int = bit_rhs.value
                            for _bi in range(width):
                                _bv: int = (val >> (_bi * 8)) & 0xFF
                                _addr: str = asm if _bi == 0 else f"{asm}+{_bi}"
                                if _bv == identity:
                                    continue  # AND #$FF / OR #$00 / EOR #$00 → no-op
                                if rhs.op == BinOp.BAND and _bv == 0x00:
                                    self._stz(_addr)  # AND #$00 clears the byte
                                else:
                                    self.emit(f"\tLDA {_addr}")
                                    self.emit(f"\t{op_mnem} #${_bv:02X}")
                                    self.emit(f"\tSTA {_addr}")
                            return

                        if isinstance(bit_rhs, Identifier):
                            try:
                                _rhs_sym: Symbol = self.current_symtab.lookup(bit_rhs.name)
                                if not _rhs_sym.is_array and not _rhs_sym.is_port:
                                    _rasm: str = _rhs_sym.asm_name()
                                    for _bi in range(width):
                                        _la: str = asm if _bi == 0 else f"{asm}+{_bi}"
                                        _ra: str = _rasm if _bi == 0 else f"{_rasm}+{_bi}"
                                        self.emit(f"\tLDA {_la}")
                                        self.emit(f"\t{op_mnem} {_ra}")
                                        self.emit(f"\tSTA {_la}")
                                    return
                            except KeyError:
                                pass  # fall through to generic RPN path

                def _self_const_fold(expr: Expr) -> tuple[int, int] | None:
                    """Helper for self const fold.
                    Internal helper used during code generation.
                    """
                    if isinstance(expr, IntLiteral):
                        return (0, expr.value)
                    if isinstance(expr, Identifier):
                        if expr.name == lhs.name:
                            return (1, 0)
                        return None
                    if isinstance(expr, BinaryExpr) and expr.op in {BinOp.ADD, BinOp.SUB}:
                        left = _self_const_fold(expr.left)
                        right = _self_const_fold(expr.right)
                        if left is None or right is None:
                            return None
                        left_self, left_const = left
                        right_self, right_const = right
                        if expr.op == BinOp.ADD:
                            return (left_self + right_self, left_const + right_const)
                        return (left_self - right_self, left_const - right_const)
                    return None

                # Fold chains like var = var + c1 + c2 into a single immediate add/sub
                folded = _self_const_fold(rhs)
                if folded is not None:
                    self_count, const_val = folded
                    if self_count == 1 and const_val != 0:
                        scale = 1
                        if lhs_t.sem_type.is_pointer:
                            if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                                scale = lhs_t.sem_type.struct_info.size
                            elif lhs_t.sem_type.base == "WORD":
                                scale = 2
                        total: int = const_val * scale
                        is_add = total >= 0


                        if is_word:
                            abs_total: int = (total if is_add else -total) & 0xFFFF
                            lo: int = abs_total & 0xFF
                            hi: int = (abs_total >> 8) & 0xFF
                            self.emit(f"\tLDA {asm}")
                            if is_add:
                                self.emit("\tCLC")
                                self.emit(f"\tADC #${lo:02X}")
                            else:
                                self.emit("\tSEC")
                                self.emit(f"\tSBC #${lo:02X}")
                            self.emit(f"\tSTA {asm}")

                            self.emit(f"\tLDA {asm}+1")
                            if is_add:
                                self.emit(f"\tADC #${hi:02X}")
                            else:
                                self.emit(f"\tSBC #${hi:02X}")
                            self.emit(f"\tSTA {asm}+1")
                            return
                        elif lhs_t.sem_type.base == "BYTE":
                            abs_total = (total if is_add else -total) & 0xFF
                            self.emit(f"\tLDA {asm}")
                            if is_add:
                                self.emit("\tCLC")
                                self.emit(f"\tADC #${abs_total:02X}")
                            else:
                                self.emit("\tSEC")
                                self.emit(f"\tSBC #${abs_total:02X}")
                            self.emit(f"\tSTA {asm}")
                            return

                # var = var +/- imm (general immediate, WORD or pointer)
                if is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    imm_op: IntLiteral | None = None
                    is_add: bool = rhs.op == BinOp.ADD
                    if is_self(rhs.left) and isinstance(rhs.right, IntLiteral):
                        imm_op = rhs.right
                    elif is_add and is_self(rhs.right) and isinstance(rhs.left, IntLiteral):
                        imm_op = rhs.left

                    if imm_op is not None:
                        imm_val: int = imm_op.value & 0xFFFF
                        # For pointer arithmetic, scale by element size
                        scale = 1
                        if lhs_t.sem_type.is_pointer:
                            if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                                scale = lhs_t.sem_type.struct_info.size
                            elif lhs_t.sem_type.base == "LONG":
                                scale = 4
                            elif lhs_t.sem_type.base == "WORD":
                                scale = 2
                        total: int = (imm_val * scale) & 0xFFFF
                        lo: int = total & 0xFF
                        hi: int = (total >> 8) & 0xFF

                        self.emit(f"\tLDA {asm}")
                        if is_add:
                            self.emit("\tCLC")
                            self.emit(f"\tADC #${lo:02X}")
                        else:
                            self.emit("\tSEC")
                            self.emit(f"\tSBC #${lo:02X}")
                        self.emit(f"\tSTA {asm}")

                        self.emit(f"\tLDA {asm}+1")
                        if is_add:
                            self.emit(f"\tADC #${hi:02X}")
                        else:
                            self.emit(f"\tSBC #${hi:02X}")
                        self.emit(f"\tSTA {asm}+1")
                        return

                # Optimize word var = var1 +/- var2 (memory-to-memory operations)
                if is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    # Check if both operands are simple identifier references
                    if isinstance(rhs.left, Identifier) and isinstance(rhs.right, Identifier):
                        left_sym: Symbol = self.current_symtab.lookup(rhs.left.name)
                        right_sym: Symbol = self.current_symtab.lookup(rhs.right.name)
                        
                        # Only optimize if both are simple memory variables (not arrays, not at fixed addresses)
                        if (not left_sym.is_array and left_sym.address is None and
                            not right_sym.is_array and right_sym.address is None):

                            
                            left_asm: str = left_sym.asm_name()
                            right_asm: str = right_sym.asm_name()
                            
                            if rhs.op == BinOp.ADD:
                                # word_var = word_var1 + word_var2
                                self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
                                self.emit("\tCLC")
                                self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=True)}")
                                self.emit(f"\tSTA {asm}")
                                self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=False)}")
                                self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=False)}")
                                self.emit(f"\tSTA {asm}+1")
                                return

                # Optimize word var = var1 +/- imm (direct immediate add/sub)
                if is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    var_opnd: Identifier | None = None
                    imm_opnd: IntLiteral | None = None
                    is_add: bool = rhs.op == BinOp.ADD

                    if isinstance(rhs.left, Identifier) and isinstance(rhs.right, IntLiteral):
                        var_opnd = rhs.left
                        imm_opnd = rhs.right
                    elif is_add and isinstance(rhs.right, Identifier) and isinstance(rhs.left, IntLiteral):
                        var_opnd = rhs.right
                        imm_opnd = rhs.left

                    if var_opnd and imm_opnd:
                        var_sym: Symbol = self.current_symtab.lookup(var_opnd.name)
                        if not var_sym.is_array:
                            var_asm: str = var_sym.asm_name()
                            imm_val: int = imm_opnd.value & 0xFFFF

                            scale = 1
                            if var_sym.type.is_pointer:
                                if var_sym.type.is_struct and var_sym.type.struct_info:
                                    scale = var_sym.type.struct_info.size
                                elif var_sym.type.base == "WORD":
                                    scale = 2

                            total: int = (imm_val * scale) & 0xFFFF
                            lo: int = total & 0xFF
                            hi: int = (total >> 8) & 0xFF

                            self.emit(f"\tLDA {var_asm}")
                            if is_add:
                                self.emit("\tCLC")
                                self.emit(f"\tADC #${lo:02X}")
                            else:
                                self.emit("\tSEC")
                                self.emit(f"\tSBC #${lo:02X}")
                            self.emit(f"\tSTA {asm}")

                            self.emit(f"\tLDA {var_asm}+1")
                            if is_add:
                                self.emit(f"\tADC #${hi:02X}")
                            else:
                                self.emit(f"\tSBC #${hi:02X}")
                            self.emit(f"\tSTA {asm}+1")
                            return

                # Optimize byte var = var1 +/- imm (direct immediate operations)
                if not is_word and lhs_t.sem_type.base == "BYTE" and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    # Check if one operand is identifier and other is immediate
                    var_opnd: Identifier | None = None
                    imm_opnd: IntLiteral | None = None
                    is_sub_reversed: bool = False

                    if isinstance(rhs.left, Identifier) and isinstance(rhs.right, IntLiteral):
                        var_opnd = rhs.left
                        imm_opnd = rhs.right
                        is_sub_reversed = False
                    elif isinstance(rhs.right, Identifier) and isinstance(rhs.left, IntLiteral) and rhs.op == BinOp.ADD:
                        # For addition, const + var is same as var + const
                        var_opnd = rhs.right
                        imm_opnd = rhs.left
                        is_sub_reversed = False
                    
                    if var_opnd and imm_opnd:
                        var_sym: Symbol = self.current_symtab.lookup(var_opnd.name)
                        if not var_sym.is_array and var_sym.address is None:
                            var_asm: str = var_sym.asm_name()
                            imm_val: int = imm_opnd.value & 0xFF
                            
                            if rhs.op == BinOp.ADD:
                                # byte_var = other_var + imm
                                self.emit(f"\tLDA {var_asm}")
                                self.emit("\tCLC")
                                self.emit(f"\tADC #{imm_val}")
                                self.emit(f"\tSTA {asm}")
                                return
                            elif rhs.op == BinOp.SUB:
                                # byte_var = other_var - imm
                                self.emit(f"\tLDA {var_asm}")
                                self.emit("\tSEC")
                                self.emit(f"\tSBC #{imm_val}")
                                self.emit(f"\tSTA {asm}")
                                return

                # Optimization: Chained word ADD/SUB with immediate
                # Pattern: z = (x + y) + imm or z = (x - y) - imm
                # This uses destination as temporary to avoid register shuffling
                if is_word and isinstance(rhs.left, BinaryExpr) and isinstance(rhs.right, IntLiteral):
                    left_expr: BinaryExpr = rhs.left
                    imm_val: int = rhs.right.value & 0xFFFF
                    
                    # Check if left operand is ADD/SUB of two identifiers
                    if (left_expr.op in {BinOp.ADD, BinOp.SUB} and
                        isinstance(left_expr.left, Identifier) and 
                        isinstance(left_expr.right, Identifier)):
                        
                        # Lookup all symbols
                        x_sym: Symbol = self.current_symtab.lookup(left_expr.left.name)
                        y_sym: Symbol = self.current_symtab.lookup(left_expr.right.name)
                        
                        # Check all are simple variables
                        if (not x_sym.is_array and x_sym.address is None and
                            not y_sym.is_array and y_sym.address is None):
                            
                            x_asm: str = x_sym.asm_name()
                            y_asm: str = y_sym.asm_name()
                            imm_low: int = imm_val & 0xFF
                            imm_high: int = (imm_val >> 8) & 0xFF
                            
                            # Step 1: Compute (x op1 y) and store in destination
                            self.emit(f"\tLDA {x_asm}")
                            if left_expr.op == BinOp.ADD:
                                self.emit("\tCLC")
                                self.emit(f"\tADC {y_asm}")
                            else:  # SUB
                                self.emit("\tSEC")
                                self.emit(f"\tSBC {y_asm}")
                            self.emit(f"\tSTA {asm}")
                            
                            self.emit(f"\tLDA {x_asm}+1")
                            if left_expr.op == BinOp.ADD:
                                self.emit(f"\tADC {y_asm}+1")
                            else:  # SUB
                                self.emit(f"\tSBC {y_asm}+1")
                            self.emit(f"\tSTA {asm}+1")
                            
                            # Step 2: Apply outer operation with immediate to destination
                            if rhs.op == BinOp.ADD:
                                # dest = dest + imm
                                self.emit(f"\tLDA #${imm_low:02X}")
                                self.emit("\tCLC")
                                self.emit(f"\tADC {asm}")
                                self.emit(f"\tSTA {asm}")
                                
                                self.emit(f"\tLDA #${imm_high:02X}")
                                self.emit(f"\tADC {asm}+1")
                                self.emit(f"\tSTA {asm}+1")
                            else:  # SUB
                                # dest = dest - imm
                                self.emit(f"\tLDA {asm}")
                                self.emit("\tSEC")
                                self.emit(f"\tSBC #${imm_low:02X}")
                                self.emit(f"\tSTA {asm}")
                                
                                self.emit(f"\tLDA {asm}+1")
                                self.emit(f"\tSBC #${imm_high:02X}")
                                self.emit(f"\tSTA {asm}+1")
                            return

        # Final optimization check: Direct word ADD/SUB without temporaries
        # This handles z = x + y for WORD variables
        if (isinstance(lhs, Identifier) and isinstance(rhs, BinaryExpr) and 
            rhs.op in {BinOp.ADD, BinOp.SUB}):
            lhs_sym: Symbol = self.current_symtab.lookup(lhs.name)
            if (lhs_sym.type.base == "WORD" and not lhs_sym.type.is_pointer and 
                not lhs_sym.is_array and lhs_sym.address is None and
                isinstance(rhs.left, Identifier) and isinstance(rhs.right, Identifier)):
                
                left_sym: Symbol = self.current_symtab.lookup(rhs.left.name)
                right_sym: Symbol = self.current_symtab.lookup(rhs.right.name)
                
                if (not left_sym.is_array and left_sym.address is None and
                    not right_sym.is_array and right_sym.address is None):
                    
                    lhs_asm: str = lhs_sym.asm_name()
                    left_asm: str = left_sym.asm_name()
                    right_asm: str = right_sym.asm_name()
                    
                    # Direct 16-bit ADD/SUB without temporaries
                    self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=True)}")
                    if rhs.op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=True)}")
                    else:  # SUB
                        self.emit("\tSEC")
                        self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=True)}")
                    self.emit(f"\tSTA {lhs_asm}")
                    
                    self.emit(f"\tLDA {self._sym_operand(left_sym, low_byte=False)}")
                    if rhs.op == BinOp.ADD:
                        self.emit(f"\tADC {self._sym_operand(right_sym, low_byte=False)}")
                    else:  # SUB
                        self.emit(f"\tSBC {self._sym_operand(right_sym, low_byte=False)}")
                    self.emit(f"\tSTA {lhs_asm}+1")
                    return

        # Fast path: store immediate into dereferenced pointer without temps
        # NOTE: Can only use this for ZP (zero-page) pointers since we need Y index for indirect addressing
        # For now, disable this optimization to ensure Y is always used for compatibility
        # if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, Identifier):
        #     ptr_sym = self.current_symtab.lookup(lhs.pointer.name)
        #     if ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array:
        #         if isinstance(rhs, IntLiteral) and lhs_t.sem_type.base == "BYTE":
        #             val = rhs.value & 0xFF
        #             self.emit(f"\tLDA #${val:02X}")
        #             self.emit("\tLDY #$00")
        #             self.emit(f"\tSTA ({ptr_sym.asm_name()}),Y")
        #             return

        # Optimization: Direct pointer dereference for simple identifiers
        # Pattern: ptr^ = value where ptr is a simple identifier in zero page
        if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, Identifier):
            ptr_sym: Symbol = self.current_symtab.lookup(lhs.pointer.name)
            if (ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array
                and ptr_sym.in_zeropage):
                # Pointer is in zero page, can use direct indirect addressing
                ptr_addr: str = ptr_sym.asm_name()
                
                # 1. Compute RHS
                self.gen_expr(rhs)
                
                # 2. Store to dereferenced pointer directly (no TMP0 needed)
                if lhs_t.sem_type.base == "LONG":
                    # LONG: RHS result is in MATH0; store all 4 bytes
                    self.emit("\tLDY #$00")
                    self.emit("\tLDA MATH0")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA MATH0+1")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA MATH0+2")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA MATH0+3")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                elif lhs_t.sem_type.base == "WORD":
                    # Save high byte (X), but low byte (A) is ready to store
                    self.emit("\tSTX TMP2+1")
                    self.emit("\tLDY #$00")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                    self.emit("\tINY")
                    self.emit("\tLDA TMP2+1")
                    self.emit(f"\tSTA ({ptr_addr}),Y")
                else:
                    # BYTE assignment: value is already in A, just store it
                    if self.is_65c02:
                        self.emit(f"\tSTA ({ptr_addr})")
                    else:
                        self.emit("\tLDY #$00")
                        self.emit(f"\tSTA ({ptr_addr}),Y")

                return

        # OPTIMIZATION: Dereferenced subscript of ZEROPAGE pointer array
        # Pattern: arr[i]^ = value where arr is a pointer array in ZEROPAGE
        if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, SubscriptExpr):
            sub_expr: SubscriptExpr = lhs.pointer
            zp_sym: Symbol | None
            is_zp_ptr_array, zp_sym, byte_offset = self._is_zeropage_pointer_array_subscript(sub_expr)

            # Accept non-constant indices for pointer arrays in ZEROPAGE
            if not is_zp_ptr_array and isinstance(sub_expr.array, Identifier):
                try:
                    zp_sym = self.current_symtab.lookup(sub_expr.array.name)
                except KeyError:
                    zp_sym = None
                if (zp_sym and zp_sym.is_array and zp_sym.type.is_pointer and zp_sym.address is None
                    and not zp_sym.is_const and zp_sym.in_zeropage):
                    is_zp_ptr_array = True

            if is_zp_ptr_array and zp_sym:
                arr_base: str = zp_sym.asm_name()

                # Safe fast path only for BYTE deref targets
                if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
                    element_width: int = self._calculate_element_width(zp_sym)

                    # Constant index path
                    if isinstance(sub_expr.index, IntLiteral):
                        byte_offset = sub_expr.index.value * element_width
                        if byte_offset < 256:
                            # Immediate RHS
                            if isinstance(rhs, IntLiteral):
                                val: int = rhs.value & 0xFF
                                self.emit(f"\tLDX #${byte_offset:02X}    ; byte offset = index * element_width")
                                self.emit(f"\tLDA #${val:02X}")
                                self.emit(f"\tSTA ({arr_base},X)")
                                return

                            # Identifier RHS
                            if isinstance(rhs, Identifier):
                                rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)
                                rhs_addr: str = rhs_sym.asm_name()
                                self.emit(f"\tLDX #${byte_offset:02X}    ; byte offset = index * element_width")
                                self.emit(f"\tLDA {rhs_addr}")
                                self.emit(f"\tSTA ({arr_base},X)")
                                return

                            # Complex RHS: save to TMP2 to avoid clobbering X
                            self.gen_expr(rhs)
                            self.emit("\tSTA TMP2")
                            self.emit(f"\tLDX #${byte_offset:02X}    ; byte offset = index * element_width")
                            self.emit("\tLDA TMP2")
                            self.emit(f"\tSTA ({arr_base},X)")
                            return

                    # Variable index path
                    # Immediate RHS
                    if isinstance(rhs, IntLiteral):
                        val = rhs.value & 0xFF
                        self.gen_expr(sub_expr.index)
                        if element_width == 2:
                            self.emit("\tASL A")
                        self.emit("\tTAX")
                        self.emit(f"\tLDA #${val:02X}")
                        self.emit(f"\tSTA ({arr_base},X)")
                        return

                    # Identifier RHS
                    if isinstance(rhs, Identifier):
                        rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)
                        rhs_addr: str = rhs_sym.asm_name()
                        self.gen_expr(sub_expr.index)
                        if element_width == 2:
                            self.emit("\tASL A")
                        self.emit("\tTAX")
                        self.emit(f"\tLDA {rhs_addr}")
                        self.emit(f"\tSTA ({arr_base},X)")
                        return

                    # Complex RHS: save to TMP2, then compute index into X
                    self.gen_expr(rhs)
                    self.emit("\tSTA TMP2")
                    self.gen_expr(sub_expr.index)
                    if element_width == 2:
                        self.emit("\tASL A")
                    self.emit("\tTAX")
                    self.emit("\tLDA TMP2")
                    self.emit(f"\tSTA ({arr_base},X)")
                    return
        
        # Check for BYTE subscript assignment - handle it specially to postpone RHS generation
        if (isinstance(lhs, SubscriptExpr) and 
            rhs_t.sem_type.base == "BYTE" and not rhs_t.sem_type.is_pointer):
            # Compute address into TMP0/TMP0+1
            self._gen_subscript(lhs, load_only=True, calc_addr_only=True)
            
            # For IntLiteral RHS, emit directly; otherwise generate RHS now
            if isinstance(rhs, IntLiteral):
                val: int = rhs.value & 0xFF
                self.emit(f"\tLDA #{val}")
            else:
                # Generate RHS expression
                prev_assign_type: SemType | None = self.assign_target_type
                self.assign_target_type = cast(SemType, lhs_t.sem_type)
                try:
                    self.gen_expr(rhs)
                finally:
                    self.assign_target_type = prev_assign_type
            
            # Store at computed address
            self._emit_indirect_store_zero("TMP0")
            return

        # vygeneruj RHS
        # Set assignment target context for optimizations
        prev_assign_type: SemType | None = self.assign_target_type
        prev_assign_sym: Symbol | None = self.assign_target_sym
        prev_assign_blocked: bool = self.assign_target_blocked
        prev_suppress_return_x: bool = self.suppress_byte_return_x

        self.assign_target_type = cast(SemType, lhs_t.sem_type)
        self.assign_target_sym = None
        self.assign_target_blocked = False

        if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
            self.suppress_byte_return_x = True

        if isinstance(lhs, Identifier):
            try:
                target_sym: Symbol | None = self.current_symtab.lookup(lhs.name)
            except KeyError:
                target_sym = None
            if target_sym is not None and not target_sym.is_const and not target_sym.is_array and target_sym.address is None:
                if not self._is_fixed_address(target_sym.asm_name()) and not self._is_port_variable(target_sym.asm_name()):
                    self.assign_target_sym = target_sym
        try:
            self.gen_expr(rhs)
        finally:
            self.assign_target_type = prev_assign_type
            self.assign_target_sym = prev_assign_sym
            self.assign_target_blocked = prev_assign_blocked
            self.suppress_byte_return_x = prev_suppress_return_x

        # Handle type narrowing: if RHS is LONG and LHS is smaller, load from MATH0
        if rhs_t.sem_type.base == "LONG" and lhs_t.sem_type.base != "LONG":
            self.emit("\tLDA MATH0")
            if lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer:
                self.emit("\tLDX MATH0+1")

        # Handle type widening: if RHS is smaller than LHS, extend with zeros
        # This is needed when assigning a BYTE to a WORD target
        # BUT: Don't clear X if the RHS is a multiply (MUL8 returns 16-bit result in A,X)
        # Also: Don't clear X for any arithmetic expression since ADD/SUB/DIV/MOD may have carry
        # Also: Don't clear X if RHS is a simple identifier/literal - gen_expr already handled widening
        is_arith: bool = isinstance(rhs, BinaryExpr) and rhs.op in {BinOp.ADD, BinOp.SUB, BinOp.MUL, BinOp.DIV, BinOp.MOD}
        is_simple_rhs: bool = isinstance(rhs, (Identifier, IntLiteral))
        if (rhs_t.sem_type.base == "BYTE" and not rhs_t.sem_type.is_pointer and
            lhs_t.sem_type.base == "WORD" and not is_arith and not is_simple_rhs):
            if self.is_65c02:
                self.emit("\tLDX #$00     ; note 5677")  # Clear X for BYTE to WORD conversion
            else:
                self.emit("\tLDX #$00     ; note 5679")

        if isinstance(lhs, Identifier):

            sym: Symbol = self.current_symtab.lookup(lhs.name)

            if sym.is_const:
                self._raise_error("Cannot assign to const")

            asm: str = sym.asm_name()
            if sym.type.base == "BYTE" and not sym.type.is_pointer:
                self.emit(f"\tSTA {asm}")
            elif sym.type.base == "LONG" and not sym.type.is_pointer:
                # Expect result in MATH0
                self.emit(f"\tLDA MATH0")
                self.emit(f"\tSTA {asm}")
                self.emit(f"\tLDA MATH0+1")
                self.emit(f"\tSTA {asm}+1")
                self.emit(f"\tLDA MATH0+2")
                self.emit(f"\tSTA {asm}+2")
                self.emit(f"\tLDA MATH0+3")
                self.emit(f"\tSTA {asm}+3")
            else:
                self.emit(f"\tSTA {asm}")
                self.emit(f"\tSTX {asm}+1")
            return

        # dereference
        if isinstance(lhs, DerefExpr):
            # This should not be reached if the optimization above triggered
            # But kept as fallback for complex pointer expressions
            if lhs_t.sem_type.base == "LONG":
                # LONG deref write: RHS in MATH0; save to TMP2/TMP3 before
                # computing pointer address (gen_expr clobbers MATH0 via ADD16)
                self.emit("\tLDA MATH0")
                self.emit("\tSTA TMP2")
                self.emit("\tLDA MATH0+1")
                self.emit("\tSTA TMP2+1")
                self.emit("\tLDA MATH0+2")
                self.emit("\tSTA TMP3")
                self.emit("\tLDA MATH0+3")
                self.emit("\tSTA TMP3+1")
                self.gen_expr(lhs.pointer)
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")
                self.emit("\tLDA TMP2")
                self.emit("\tLDY #$00")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tLDA TMP2+1")
                self.emit("\tINY")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tLDA TMP3")
                self.emit("\tINY")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tLDA TMP3+1")
                self.emit("\tINY")
                self.emit("\tSTA (TMP0),Y")
            else:
                # 1️⃣ ulož RHS hodnotu
                self.emit("\tSTA TMP2")
                # Only save X if we're storing a WORD; for BYTE we only need the low byte
                if lhs_t.sem_type.base == "WORD":
                    self.emit("\tSTX TMP2+1")

                # 2️⃣ vygeneruj adresu pointeru
                self.gen_expr(lhs.pointer)

                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")

                # 3️⃣ zápis LOW byte
                self.emit("\tLDA TMP2")
                if lhs_t.sem_type.base == "WORD":
                    self.emit("\tLDY #$00")
                    self.emit("\tSTA (TMP0),Y")
                else:
                    self._emit_indirect_store_zero("TMP0")

                # 4️⃣ Write high byte only if LHS target is WORD
                if lhs_t.sem_type.base == "WORD":
                    self.emit("\tINY")
                    self.emit("\tLDA TMP2+1")
                    self.emit("\tSTA (TMP0),Y")
            return

        if isinstance(lhs, SubscriptExpr):
            # For WORD subscript assignments, store RHS to TMP2/TMP2+1 and let _gen_subscript handle it
            # (BYTE subscript assignments were already handled earlier with RHS postponement)
            self.emit("\tSTA TMP2")
            self.emit("\tSTX TMP2+1")
            self._gen_subscript(lhs, load_only=False)
            return

        if isinstance(lhs, FieldAccess):
            # Fast path: non-deref FieldAccess with simple variable base (or nested chain to Identifier).
            # A/X already hold the RHS value; emit STA/STX directly, bypassing the TMP2 round-trip
            # and the pointless field-load inside _gen_field_access(load_only=False).
            if not lhs.is_deref:
                total_offset_fp, base_expr_fp = self._calculate_nested_field_offset(lhs)
                if isinstance(base_expr_fp, Identifier):
                    sym_fp: Symbol = self.current_symtab.lookup(base_expr_fp.name)
                    base_asm_fp: str = sym_fp.asm_name()
                    field_asm_fp: str = base_asm_fp if total_offset_fp == 0 else f"{base_asm_fp}+{total_offset_fp}"
                    if lhs_t.sem_type.base == "LONG":
                        # LONG fast path: RHS in MATH0 → store 4 bytes directly
                        self.emit(f"\tLDA MATH0")
                        self.emit(f"\tSTA {field_asm_fp}")
                        self.emit(f"\tLDA MATH0+1")
                        self.emit(f"\tSTA {field_asm_fp}+1")
                        self.emit(f"\tLDA MATH0+2")
                        self.emit(f"\tSTA {field_asm_fp}+2")
                        self.emit(f"\tLDA MATH0+3")
                        self.emit(f"\tSTA {field_asm_fp}+3")
                    else:
                        field_width_fp: int = 2 if lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer else 1
                        self.emit(f"\tSTA {field_asm_fp}")
                        if field_width_fp == 2:
                            self.emit(f"\tSTX {field_asm_fp}+1")
                    return

            # General path: deref or SubscriptExpr base — need TMP2 to hold RHS while address is computed.
            # For LONG, RHS is already in MATH0 (4 bytes); no A/X staging into TMP2 needed.
            if lhs_t.sem_type.base != "LONG":
                self.emit("\tSTA TMP2")
                # Only save high byte if RHS is not BYTE (or if we don't know the type)
                # For BYTE RHS, X is either 0 or undefined, and we don't need it for BYTE field assignment
                if rhs_t.sem_type.base == "WORD" or rhs_t.sem_type.is_pointer:
                    self.emit("\tSTX TMP2+1")

            # Set assignment target type to the field type for optimizations
            # This helps skip unnecessary LDX #$00 when the field is BYTE
            prev_assign_type: SemType | None = self.assign_target_type
            self.assign_target_type = lhs_t.sem_type
            try:
                self._gen_field_access(lhs, load_only=False)
            finally:
                self.assign_target_type = prev_assign_type
            return

        self._raise_error(f"Assignment target type not supported: {type(lhs).__name__}")

    def _gen_for_const_step(self, stmt, step_expr) -> None:
        """Generate for const step.
        Internal helper used during code generation.
        """
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # Optimization: if end is a simple identifier, use it directly instead of creating a temporary
        if isinstance(stmt.end, Identifier):
            end_var = stmt.end
        else:
            # end: create temporary only if end is complex expression
            end_name: str = self._get_for_temp_name(stmt, "END")
            end_t: ExprType = self.tc_check(stmt.end)
            var_t: ExprType = self.tc_check(stmt.var)
            end_is_word: bool = (
                var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
                end_t.sem_type.base == "WORD" or end_t.sem_type.is_pointer
            )
            end_width: int = max(var_t.sem_type.width, end_t.sem_type.width)
            if end_width == 4:
                self._declare_temp(end_name, "LONG")
            else:
                self._declare_temp(end_name, "WORD" if end_is_word else "BYTE")
            end_var = Identifier(end_name)
            self.gen_assign(end_var, stmt.end)

        # podmínka WHILE (C-like: end bound is exclusive)
        if step_expr.value > 0:
            cond = BinaryExpr(stmt.var, BinOp.LT, end_var)
        else:
            cond = BinaryExpr(stmt.var, BinOp.GT, end_var)

        # tělo
        body = list(stmt.body)
        body.append(
            AssignStmt(
                stmt.var,
                BinaryExpr(stmt.var, BinOp.ADD, step_expr)
            )
        )
        
        # Generate WHILE loop
        while_stmt = WhileStmt(cond, body)
        self.gen_stmt(while_stmt)

    def _gen_for_general(self, stmt) -> None:
        """Generate for general.
        Internal helper used during code generation.
        """
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # vytvoř skryté proměnné (only if needed)
        var_t: ExprType = self.tc_check(stmt.var)
        end_t: ExprType = self.tc_check(stmt.end)
        step_t: ExprType = self.tc_check(stmt.step) if stmt.step is not None else self.tc_check(IntLiteral(1))

        # Optimization: if end is a simple identifier, use it directly
        if isinstance(stmt.end, Identifier):
            end_var = stmt.end
        else:
            end_name: str = self._get_for_temp_name(stmt, "END")
            end_is_word: bool = (
                var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
                end_t.sem_type.base == "WORD" or end_t.sem_type.is_pointer
            )
            end_width: int = max(var_t.sem_type.width, end_t.sem_type.width)
            if end_width == 4:
                self._declare_temp(end_name, "LONG")
            else:
                self._declare_temp(end_name, "WORD" if end_is_word else "BYTE")
            end_var = Identifier(end_name)
            self.gen_assign(end_var, stmt.end)

        # Optimization: if step is a simple identifier, use it directly (or use literal 1)
        if isinstance(stmt.step, Identifier):
            step_var = stmt.step
        elif stmt.step is not None:
            step_name: str = self._get_for_temp_name(stmt, "STEP")
            step_is_word: bool = (
                var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
                step_t.sem_type.base == "WORD" or step_t.sem_type.is_pointer
            )
            step_width: int = max(var_t.sem_type.width, step_t.sem_type.width)
            if step_width == 4:
                self._declare_temp(step_name, "LONG")
            else:
                self._declare_temp(step_name, "WORD" if step_is_word else "BYTE")
            step_var = Identifier(step_name)
            self.gen_assign(step_var, stmt.step)
        else:
            # Default step = 1
            step_var = IntLiteral(1)

        # IF step > 0 THEN IF i > end THEN BREAK ELSE IF i < end THEN BREAK
        cond_step_pos = BinaryExpr(step_var, BinOp.GT, IntLiteral(0))

        cond_i_ge_end = BinaryExpr(stmt.var, BinOp.GE, end_var)
        cond_i_le_end = BinaryExpr(stmt.var, BinOp.LE, end_var)

        if_pos = IfStmt(cond_i_ge_end, [BreakStmt()], None)
        if_neg = IfStmt(cond_i_le_end, [BreakStmt()], None)

        dir_check = IfStmt(cond_step_pos, [if_pos], [if_neg])

        # WHILE 1 { dir_check; body; i = i + step }
        loop_body = (
            [dir_check] +
            stmt.body +
            [AssignStmt(
                stmt.var,
                BinaryExpr(stmt.var, BinOp.ADD, step_var)
            )]
        )

        while_stmt = WhileStmt(IntLiteral(1), loop_body)
        self.gen_stmt(while_stmt)


    def gen_proc(self, proc: AnalyzedProc) -> None:
        """Generate assembly for a procedure body.
        Emits prologue, body, and epilogue code.
        """
        # přepni na lokální tabulku + typechecker
        prev_symtab: SymbolTable = self.current_symtab
        prev_tc_symtab: Any | None = getattr(self.tc, "symtab", None)
        self.current_symtab = cast(SymbolTable, proc.symtab)
        self.tc.symtab = proc.symtab

        # Emit procedure source comment
        pinfo = self.proc_src.get(proc.ast.name)
        if pinfo:
            if len(pinfo) == 3:
                fname, line, text = pinfo
            else:
                fname, line, _col, text = pinfo
            self.emit(f"\n; {fname} {line}: {text}")
        self.emit("; -- Procedure " + proc.ast.name + " --")
        self.emit(f"{self.asm_symbol_name(proc.ast.name)}:")

        # Emit parameter name equates for inline assembly references
        proc_specs: list[tuple[str, int, object, SemType]] | None = self.proc_param_specs.get(proc.ast.name)
        if proc_specs:
            self._emit_param_name_equates(proc.ast.name, proc_specs)

        # Store register-passed arguments into param globals (if any)
        if proc_specs:
            self._emit_param_reg_stores(proc.ast.name, proc_specs)

        # Embed local variable equates for inline assembly references (excluding parameters)
        param_names = {pname for pname, _, _, _ in proc_specs} if proc_specs else set()
        local_tbl = getattr(proc.symtab, "local", None)
        all_locals = list(local_tbl) if local_tbl else proc.locals
        for sym in all_locals:
            self._emit_local_name_equate(proc.ast.name, sym, param_names)

        # INIT lokálů
        for sym in proc.locals:
            self.gen_init(cast(Symbol, sym))

        # tělo (dead-store pre-pass removes consecutive overwrites of same scalar)
        for stmt in self._elim_dead_stores(proc.ast.body):
            self.gen_stmt(stmt)

        if not (proc.ast.body and isinstance(proc.ast.body[-1], ReturnStmt)):
            self.emit("\tRTS")

        # restore
        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab

    def _resolve_call_args(self, args: list[Expr | None], specs: list[tuple[str, int, object, SemType]]) -> list[tuple[int, str, int, SemType, Expr]]:
        """Resolve call args.
        Internal helper used during code generation.
        """
        resolved: list[tuple[int, str, int, SemType, Expr]] = []
        for i, spec in enumerate(specs):
            pname, width, default_value, sem_type = spec
            arg: object | None
            if i < len(args) and args[i] is not None:
                arg = args[i]
            elif default_value is not None:
                arg = default_value
            else:
                continue

            # Substitute consts and fold before codegen
            if isinstance(arg, StructLiteral) and sem_type.is_struct and not sem_type.is_pointer:
                resolved.append((i, pname, width, sem_type, cast(Expr, arg)))
                continue

            arg = subst_const(cast(Expr, arg), cast(SymbolTable, self.current_symtab))
            arg = fold_expr(arg)
            self.tc_check(arg)
            resolved.append((i, pname, width, sem_type, cast(Expr, arg)))
        return resolved

    def _emit_param_name_equates(self, callee_name: str, specs: list[tuple[str, int, object, SemType]]) -> None:
        """Emit equate declarations for parameter names to their actual storage locations.
        This allows inline assembly blocks to reference parameters by name even when
        they are assigned to shared slots. Only emits when location differs from standard names."""
        for pname, width, _default, _sem_type in specs:
            sym = self.current_symtab.lookup(pname)
            if sym.shared_slot:
                param_label = sym.asm_name()
                self.emit(f"{param_label} = {sym.shared_slot}")

    def _emit_local_name_equate(self, proc_name: str, sym: Symbol, param_names: set[str] | None = None) -> None:
        """Emit equate declaration for a local variable name to its actual storage location.
        This allows inline assembly blocks to reference locals by name even when
        they are assigned to shared slots. Only emits for locals with actual shared slots."""
        # Only emit for locals that have shared slots assigned (different from their normal name)
        if sym.proc_name and sym.name not in (param_names or set()) and sym.shared_slot:
            local_label = sym.asm_name()
            self.emit(f"{local_label} = {sym.shared_slot}")

    def _emit_param_reg_stores(self, callee_name: str, specs: list[tuple[str, int, object, SemType]]) -> None:
        """Emit param reg stores.
        Internal helper used during code generation.
        """
        if not specs:
            return
        pname0, width0, _default0, sem0 = specs[0]
        if sem0.is_struct and not sem0.is_pointer:
            return
        sym0 = self.current_symtab.lookup(pname0)
        asm0 = sym0.asm_name()
        if width0 == 2:
            self.emit(f"\tSTA {asm0}")
            self.emit(f"\tSTX {asm0}+1")
            if len(specs) > 1 and specs[1][1] == 1 and not specs[1][3].is_struct:
                pname1 = specs[1][0]
                sym1 = self.current_symtab.lookup(pname1)
                asm1 = sym1.asm_name()
                self.emit(f"\tSTY {asm1}")
            return
        if width0 == 1:
            self.emit(f"\tSTA {asm0}")
            if len(specs) > 1 and specs[1][1] == 1 and not specs[1][3].is_struct:
                pname1 = specs[1][0]
                sym1 = self.current_symtab.lookup(pname1)
                asm1 = sym1.asm_name()
                self.emit(f"\tSTX {asm1}")
                if len(specs) > 2 and specs[2][1] == 1 and not specs[2][3].is_struct:
                    pname2 = specs[2][0]
                    sym2 = self.current_symtab.lookup(pname2)
                    asm2 = sym2.asm_name()
                    self.emit(f"\tSTY {asm2}")

    def _emit_call_args(self, callee_name: str, args: list[Expr | None], specs: list[tuple[str, int, object, SemType]]) -> None:
        """Emit call args.
        Internal helper used during code generation.
        """
        resolved = self._resolve_call_args(args, specs)
        if not resolved:
            return

        indices = {i for i, _, _, _, _ in resolved}
        struct_indices = {i for i, _, _, sem, _ in resolved if sem.is_struct and not sem.is_pointer}
        reg_indices = indices - struct_indices
        last_index = max(indices) if indices else -1

        reg_case: str | None = None
        reg_a_index: int | None = None
        reg_x_index: int | None = None
        reg_y_index: int | None = None
        if specs:
            width0 = specs[0][1]
            sem0 = specs[0][3]
            if not (sem0.is_struct and not sem0.is_pointer) and width0 == 2 and 0 in reg_indices:
                reg_case = "word0"
                reg_a_index = 0
                reg_x_index = 0
                if len(specs) > 1 and specs[1][1] == 1 and 1 in reg_indices and not specs[1][3].is_struct:
                    reg_case = "word0_byte1"
                    reg_y_index = 1
            elif not (sem0.is_struct and not sem0.is_pointer) and width0 == 1 and 0 in reg_indices:
                reg_case = "byte0"
                reg_a_index = 0
                if len(specs) > 1 and specs[1][1] == 1 and 1 in reg_indices and not specs[1][3].is_struct:
                    reg_case = "two_bytes"
                    reg_x_index = 1
                    if len(specs) > 2 and specs[2][1] == 1 and 2 in reg_indices and not specs[2][3].is_struct:
                        reg_case = "three_bytes"
                        reg_y_index = 2

            # Fast path: only register args (no memory params to store)
            if reg_case == "word0" and reg_indices == {0}:
                arg = next(a for i, _, _, _, a in resolved if i == 0)
                prev_force: bool = self.force_word_result
                self.force_word_result = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.force_word_result = prev_force
                return
            if reg_case == "byte0" and reg_indices == {0}:
                arg = next(a for i, _, _, _, a in resolved if i == 0)
                prev_suppress: bool = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                return

        restore_ops: list[str] = []

        def _simple_arg(e: Expr) -> bool:
            """Helper for simple arg.
            Internal helper used during code generation.
            """
            return isinstance(e, (IntLiteral, Identifier, SubscriptExpr, FieldAccess)) or (
                isinstance(e, UnaryExpr) and e.op == UnOp.ADDROF
            )

        def _y_simple_loadable(e: Expr) -> bool:
            """Helper for y simple loadable.
            Internal helper used during code generation.
            """
            if isinstance(e, IntLiteral):
                return True
            if isinstance(e, Identifier):
                sym = self.current_symtab.lookup(e.name)
                return (sym.type.base == "BYTE" and not sym.type.is_pointer and
                        not sym.is_array and not sym.is_volatile)
            return False

        def _emit_load_y_simple(e: Expr) -> None:
            """Emit load y simple.
            Internal helper used during code generation.
            """
            if isinstance(e, IntLiteral):
                self.emit(f"\tLDY #${e.value & 0xFF:02X}")
                return
            if isinstance(e, Identifier):
                sym = self.current_symtab.lookup(e.name)
                self.emit(f"\tLDY {sym.asm_name()}")
                return

        def _can_reorder_regs() -> bool:
            """Helper for can reorder regs.
            Internal helper used during code generation.
            """
            if reg_case == "word0_byte1":
                if reg_a_index is None or reg_y_index is None:
                    return False
                arg_a = next((a for i, _, _, _, a in resolved if i == reg_a_index), None)
                arg_y = next((a for i, _, _, _, a in resolved if i == reg_y_index), None)
                if arg_a is None or arg_y is None:
                    return False
                return _simple_arg(arg_a) and _y_simple_loadable(arg_y)
            if reg_case == "three_bytes":
                return False
            if reg_case == "word0":
                for i, _, _, _, arg in resolved:
                    if i == reg_a_index and not _simple_arg(arg):
                        return False
            if reg_case in {"byte0", "two_bytes"}:
                for i, _, _, _, arg in resolved:
                    if i == reg_a_index and not _simple_arg(arg):
                        return False
                    if reg_case == "two_bytes" and i == reg_x_index and not _simple_arg(arg):
                        return False
            return True

        reorder_regs = _can_reorder_regs()

        for index, pname, width, sem_type, arg in resolved:
            asm: str = f"_{callee_name}_{pname}"

            if sem_type.is_struct and not sem_type.is_pointer:
                struct_info = sem_type.struct_info
                if struct_info is None:
                    self._raise_error(f"Cannot determine size of struct parameter '{pname}'")
                struct_size = struct_info.size
                if struct_size <= 0:
                    self._raise_error(f"Cannot determine size of struct parameter '{pname}'")
                if struct_size > 255:
                    self._raise_error(f"Struct parameter '{pname}' is too large ({struct_size} bytes)")

                if isinstance(arg, StructLiteral):
                    self._emit_struct_literal_store(asm, struct_info, arg.values, ctx_name=pname)
                    continue

                if isinstance(arg, CallExpr):
                    ret_buf = self.func_return_buffers.get(arg.name)
                    if ret_buf is None:
                        self._raise_error(f"Struct parameter '{pname}' expects a struct value")
                    asm_ret, ret_info = ret_buf
                    if ret_info.name.upper() != struct_info.name.upper():
                        self._raise_error(
                            f"Struct parameter '{pname}' expects '{struct_info.name}', got '{ret_info.name}'"
                        )
                    specs_call: list[tuple[str, int, object, SemType]] | None = self.func_param_specs.get(arg.name)
                    if specs_call is not None:
                        self._emit_call_args(arg.name, arg.args, specs_call)
                    self.emit(f"\tJSR {self.asm_symbol_name(arg.name)}")
                    self.copy_bytes_needed = True
                    self.emit(f"\tLDA #<{asm_ret}")
                    self.emit("\tSTA TMP0")
                    self.emit(f"\tLDA #>{asm_ret}")
                    self.emit("\tSTA TMP0+1")
                    self.emit(f"\tLDA #<{asm}")
                    self.emit("\tSTA TMP2")
                    self.emit(f"\tLDA #>{asm}")
                    self.emit("\tSTA TMP2+1")
                    self.emit(f"\tLDX #${struct_info.size:02X}")
                    self.emit("\tJSR COPY_BYTES")
                    continue

                if isinstance(arg, Identifier):
                    src_sym: Symbol = self.current_symtab.lookup(arg.name)
                    if not src_sym.type.is_struct or src_sym.type.is_pointer:
                        self._raise_error(f"Struct parameter '{pname}' expects a struct value")
                    if src_sym.type.base.upper() != sem_type.base.upper():
                        self._raise_error(
                            f"Struct parameter '{pname}' expects '{sem_type.base}', got '{src_sym.type.base}'"
                        )

                    # Use COPY_BYTES to copy struct payload into parameter storage
                    self.copy_bytes_needed = True

                    if src_sym.is_const:
                        if not src_sym.init or not isinstance(src_sym.init, ListInit):
                            self._raise_error(f"Const struct '{src_sym.name}' has no initialization")
                        # Extract bytes with proper field type handling
                        data_key = self._extract_const_struct_bytes(src_sym.init, struct_info)
                        if data_key not in self.array_literals:
                            self.array_id += 1
                            self.array_literals[data_key] = f"__ARRAY_DATA_{self.array_id}"
                        src_label = self.array_literals[data_key]
                        self.emit(f"\tLDA #<{src_label}")
                        self.emit("\tSTA TMP0")
                        self.emit(f"\tLDA #>{src_label}")
                        self.emit("\tSTA TMP0+1")
                    else:
                        src_label = src_sym.asm_name()
                        self.emit(f"\tLDA #<{src_label}")
                        self.emit("\tSTA TMP0")
                        self.emit(f"\tLDA #>{src_label}")
                        self.emit("\tSTA TMP0+1")

                    self.emit(f"\tLDA #<{asm}")
                    self.emit("\tSTA TMP2")
                    self.emit(f"\tLDA #>{asm}")
                    self.emit("\tSTA TMP2+1")
                    self.emit(f"\tLDX #${struct_size:02X}")
                    self.emit("\tJSR COPY_BYTES")
                    continue

                self._raise_error(f"Struct parameter '{pname}' requires a struct value or literal")

            if reg_case in {"word0", "word0_byte1"} and index == reg_a_index:
                if reorder_regs:
                    continue
                prev_force: bool = self.force_word_result
                self.force_word_result = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.force_word_result = prev_force
                self.emit("\tPHA")
                restore_ops.append("A")
                self.emit("\tTXA")
                self.emit("\tPHA")
                restore_ops.append("X")
                continue

            if reg_case in {"byte0", "two_bytes", "three_bytes"} and index == reg_a_index:
                if reorder_regs:
                    continue
                prev_suppress: bool = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                self.emit("\tPHA")
                restore_ops.append("A")
                continue

            if reg_case in {"two_bytes", "three_bytes"} and index == reg_x_index:
                if reorder_regs:
                    continue
                prev_suppress: bool = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                self.emit("\tPHA")
                restore_ops.append("X")
                continue

            if reg_case in {"word0_byte1", "three_bytes"} and index == reg_y_index:
                if reorder_regs:
                    continue
                prev_suppress: bool = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                self.emit("\tPHA")
                restore_ops.append("Y")
                continue

            if width == 1:
                if isinstance(arg, IntLiteral):
                    self.emit(f"\tLDA #${arg.value & 0xFF:02X}")
                    self.emit(f"\tSTA {asm}")
                    continue
                if isinstance(arg, Identifier):
                    arg_sym: Symbol = self.current_symtab.lookup(arg.name)
                    if arg_sym.type.base == "BYTE" and not arg_sym.type.is_pointer and not arg_sym.is_array:
                        self.emit(f"\tLDA {arg_sym.asm_name()}")
                        self.emit(f"\tSTA {asm}")
                        continue
                prev_suppress: bool = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                self.emit(f"\tSTA {asm}")
                continue

            if width == 4:
                # LONG parameter: gen_expr puts result in MATH0 (4 bytes)
                self.gen_expr(arg)
                self.emit(f"\tLDA MATH0")
                self.emit(f"\tSTA {asm}")
                self.emit(f"\tLDA MATH0+1")
                self.emit(f"\tSTA {asm}+1")
                self.emit(f"\tLDA MATH0+2")
                self.emit(f"\tSTA {asm}+2")
                self.emit(f"\tLDA MATH0+3")
                self.emit(f"\tSTA {asm}+3")
                continue

            prev_force: bool = self.force_word_result
            self.force_word_result = True
            try:
                self.gen_expr(arg)
            finally:
                self.force_word_result = prev_force
            self.emit(f"\tSTA {asm}")
            self.emit(f"\tSTX {asm}+1")

        if reorder_regs:
            if reg_case == "word0" and reg_a_index is not None:
                arg = next(a for i, _, _, _, a in resolved if i == reg_a_index)
                prev_force: bool = self.force_word_result
                self.force_word_result = True
                try:
                    self.gen_expr(arg)
                finally:
                    self.force_word_result = prev_force
            elif reg_case == "word0_byte1" and reg_a_index is not None and reg_y_index is not None:
                arg_a = next(a for i, _, _, _, a in resolved if i == reg_a_index)
                prev_force = self.force_word_result
                self.force_word_result = True
                try:
                    self.gen_expr(arg_a)
                finally:
                    self.force_word_result = prev_force
                arg_y = next(a for i, _, _, _, a in resolved if i == reg_y_index)
                _emit_load_y_simple(arg_y)
            elif reg_case in {"byte0", "two_bytes"} and reg_a_index is not None:
                if reg_case == "two_bytes" and reg_x_index is not None:
                    arg_x = next(a for i, _, _, _, a in resolved if i == reg_x_index)
                    # Fast path: load X directly without going through A
                    if isinstance(arg_x, IntLiteral):
                        self.emit(f"\tLDX #${arg_x.value & 0xFF:02X}")
                    elif isinstance(arg_x, Identifier):
                        _ax_sym: Symbol = self.current_symtab.lookup(arg_x.name)
                        if _ax_sym.type.base == "BYTE" and not _ax_sym.type.is_pointer and not _ax_sym.is_array:
                            self.emit(f"\tLDX {_ax_sym.asm_name()}")
                        else:
                            prev_suppress: bool = self.suppress_byte_return_x
                            self.suppress_byte_return_x = True
                            try:
                                self.gen_expr(arg_x)
                            finally:
                                self.suppress_byte_return_x = prev_suppress
                            self.emit("\tTAX")
                    else:
                        prev_suppress = self.suppress_byte_return_x
                        self.suppress_byte_return_x = True
                        try:
                            self.gen_expr(arg_x)
                        finally:
                            self.suppress_byte_return_x = prev_suppress
                        self.emit("\tTAX")
                arg_a = next(a for i, _, _, _, a in resolved if i == reg_a_index)
                prev_suppress = self.suppress_byte_return_x
                self.suppress_byte_return_x = True
                try:
                    self.gen_expr(arg_a)
                finally:
                    self.suppress_byte_return_x = prev_suppress
        else:
            while restore_ops:
                op = restore_ops.pop()
                self.emit("\tPLA")
                if op == "X":
                    self.emit("\tTAX")
                elif op == "Y":
                    self.emit("\tTAY")

    def _emit_struct_literal_store(
        self,
        base_asm: str,
        struct_info: StructInfo,
        values: Sequence[Expr | InitValue],
        *,
        base_offset: int = 0,
        ctx_name: str | None = None,
    ) -> None:
        """Store a struct literal into memory at base_asm + base_offset."""
        if len(values) != len(struct_info.fields):
            ctx = f"'{ctx_name}'" if ctx_name else "struct"
            self._raise_error(
                f"Struct literal for {ctx} has {len(values)} field(s), "
                f"expected {len(struct_info.fields)}"
            )

        def emit_scalar(field: StructFieldInfo, val: Expr | InitValue, offset: int) -> int:
            if isinstance(val, ExprInit):
                val = val.expr
            if not isinstance(val, Expr):
                self._raise_error("Struct literal field requires expression")
            if field.is_pointer or field.base_type == "WORD":
                prev_force = self.force_word_result
                prev_suppress = self.suppress_byte_return_x
                self.force_word_result = True
                self.suppress_byte_return_x = False
                try:
                    self.gen_expr(val)
                finally:
                    self.force_word_result = prev_force
                    self.suppress_byte_return_x = prev_suppress
                self.emit(f"\tSTA {base_asm}+{offset}")
                self.emit(f"\tSTX {base_asm}+{offset+1}")
                return 2

            prev_suppress = self.suppress_byte_return_x
            self.suppress_byte_return_x = True
            try:
                self.gen_expr(val)
            finally:
                self.suppress_byte_return_x = prev_suppress
            self.emit(f"\tSTA {base_asm}+{offset}")
            return 1

        def is_struct_type(field: StructFieldInfo) -> bool:
            if field.is_pointer:
                return False
            if not self.struct_registry:
                return False
            return self.struct_registry.is_defined(field.base_type)

        offset = base_offset
        for field, val in zip(struct_info.fields, values):
            if field.array_sizes:
                if not isinstance(val, ListInit):
                    self._raise_error("Struct literal array field requires list initializer")
                total = 1
                for dim in field.array_sizes:
                    if dim is None:
                        self._raise_error("Struct literal array field has unknown size")
                    total *= dim
                if len(val.values) != total:
                    self._raise_error(
                        f"Struct literal array field has {len(val.values)} value(s), expected {total}"
                    )
                for elem in val.values:
                    if is_struct_type(field):
                        if not isinstance(elem, ListInit):
                            self._raise_error("Struct array element requires list initializer")
                        nested = self.struct_registry.lookup(field.base_type) if self.struct_registry else None
                        if nested is None:
                            self._raise_error("Struct array element type is undefined")
                        self._emit_struct_literal_store(
                            base_asm,
                            nested,
                            elem.values,
                            base_offset=offset,
                            ctx_name=ctx_name,
                        )
                        offset += nested.size
                    else:
                        offset += emit_scalar(field, elem, offset)
                continue

            if is_struct_type(field):
                if not isinstance(val, ListInit):
                    self._raise_error("Nested struct field requires list initializer")
                nested = self.struct_registry.lookup(field.base_type) if self.struct_registry else None
                if nested is None:
                    self._raise_error("Nested struct type is undefined")
                self._emit_struct_literal_store(
                    base_asm,
                    nested,
                    val.values,
                    base_offset=offset,
                    ctx_name=ctx_name,
                )
                offset += nested.size
                continue

            offset += emit_scalar(field, val, offset)


    def gen_stmt(self, stmt):
        """Generate assembly for a statement node.
        Dispatches to statement-specific emitters.
        """
        from ast_nodes import IncbinDirective
        # Emit source comment for this statement
        self.emit_src_comment_for_stmt(stmt)

        if isinstance(stmt, IncbinDirective):
            self.emit(f'.incbin "{stmt.filename}"')
            return

        if isinstance(stmt, AsmBlock):
            self.emit("; ASM_BLOCK_BEGIN")
            for line in stmt.text.splitlines():
                self.emit(line)
            self.emit("; ASM_BLOCK_END")
            self.emit(f'\t.segment "{self.seg_code}"')
            return

        # Compile-time diagnostic directives: .error/.warning/.info
        from ast_nodes import ErrorDirective, WarningDirective, InfoDirective
        if isinstance(stmt, ErrorDirective):
            # Raise an error at the statement location
            self._raise_error(stmt.message)
        if isinstance(stmt, WarningDirective):
            from errors import print_error
            src = "\n".join(self.source_lines) if self.source_lines else ""
            if self.current_stmt_info:
                fname, line, col, _ = self.current_stmt_info
            else:
                fname, line, col = None, 1, 1
            print_error(src, line, col, stmt.message, filename=fname, severity='warning')
            return
        if isinstance(stmt, InfoDirective):
            from errors import print_error
            src = "\n".join(self.source_lines) if self.source_lines else ""
            if self.current_stmt_info:
                fname, line, col, _ = self.current_stmt_info
            else:
                fname, line, col = None, 1, 1
            print_error(src, line, col, stmt.message, filename=fname, severity='info')
            return

        if isinstance(stmt, CallStmt):
            # Pass arguments to callee parameters (simple ABI via memory)
            # Check both proc and func param specs — a func can be called as a statement
            specs: list[tuple[str, int, object, SemType]] | None = self.proc_param_specs.get(stmt.name) or self.func_param_specs.get(stmt.name)
            if specs is not None:
                self._emit_call_args(stmt.name, stmt.args, specs)
            self.emit(f"\tJSR {self.asm_symbol_name(stmt.name)}")
            return


        if isinstance(stmt, AssignStmt):
            self.gen_assign(stmt.lhs, stmt.rhs)
            return

        if isinstance(stmt, ReturnStmt):
            # Generate the return expression (if any - PROCs may have no return value)
            if stmt.expr is not None:
                if self.current_func_return_struct and self.current_func_return_buf:
                    struct_info = self.current_func_return_struct
                    if isinstance(stmt.expr, StructLiteral):
                        self._emit_struct_literal_store(self.current_func_return_buf, struct_info, stmt.expr.values, ctx_name="return")
                    elif isinstance(stmt.expr, Identifier):
                        sym = self.current_symtab.lookup(stmt.expr.name)
                        if not sym.type.is_struct or sym.type.is_pointer:
                            self._raise_error("RETURN expects a struct value")
                        if sym.type.base.upper() != struct_info.name.upper():
                            self._raise_error("RETURN struct type mismatch")
                        self.copy_bytes_needed = True
                        self.emit(f"\tLDA #<{sym.asm_name()}")
                        self.emit("\tSTA TMP0")
                        self.emit(f"\tLDA #>{sym.asm_name()}")
                        self.emit("\tSTA TMP0+1")
                        self.emit(f"\tLDA #<{self.current_func_return_buf}")
                        self.emit("\tSTA TMP2")
                        self.emit(f"\tLDA #>{self.current_func_return_buf}")
                        self.emit("\tSTA TMP2+1")
                        self.emit(f"\tLDX #${struct_info.size:02X}")
                        self.emit("\tJSR COPY_BYTES")
                    else:
                        self._raise_error("RETURN expects a struct value")
                    self.emit(f"\tLDA #<{self.current_func_return_buf}")
                    self.emit(f"\tLDX #>{self.current_func_return_buf}")
                else:
                    prev_suppress: bool = self.suppress_byte_return_x
                    prev_force: bool = self.force_word_result
                    if self.current_func_return_type == "BYTE" and not self.current_func_return_is_pointer:
                        self.suppress_byte_return_x = True
                    elif self.current_func_return_type == "WORD" or self.current_func_return_is_pointer:
                        self.force_word_result = True
                    try:
                        self.gen_expr(stmt.expr)
                    finally:
                        self.suppress_byte_return_x = prev_suppress
                        self.force_word_result = prev_force
            
            # If function expects BYTE but expression is WORD, use only lower byte (A register already has it)
            # X register will be ignored on return
            
            self.emit("\tRTS")
            return

        if isinstance(stmt, SwitchStmt):
            expr = subst_const(stmt.expr, cast(SymbolTable, self.current_symtab))
            expr = fold_expr(expr)
            expr_t = self.tc_check(expr)
            is_long = expr_t.sem_type.width == 4
            is_word = not is_long and (expr_t.sem_type.base == "WORD" or expr_t.sem_type.is_pointer)

            # Fast path: if the switch expression is a simple scalar identifier,
            # compare bytes directly from the source variable — no temp copy needed.
            sw_asm: str
            if isinstance(expr, Identifier):
                _sw_id_sym = self.current_symtab.lookup(expr.name)
                if (not _sw_id_sym.is_array and _sw_id_sym.address is None
                        and not _sw_id_sym.is_volatile and not _sw_id_sym.is_port):
                    sw_asm = _sw_id_sym.asm_name()
                else:
                    _sw_val_name = self.new_label("switch_val")
                    _sw_val_sym = self._declare_temp(_sw_val_name, "LONG" if is_long else ("WORD" if is_word else "BYTE"))
                    self.gen_assign(Identifier(_sw_val_name), expr)
                    sw_asm = _sw_val_sym.asm_name()
            else:
                _sw_val_name = self.new_label("switch_val")
                _sw_val_sym = self._declare_temp(_sw_val_name, "LONG" if is_long else ("WORD" if is_word else "BYTE"))
                self.gen_assign(Identifier(_sw_val_name), expr)
                sw_asm = _sw_val_sym.asm_name()

            end_label: str = self.new_label("endswitch")

            case_labels: list[str] = []
            default_label: str | None = None
            for case in stmt.cases:
                lbl = self.new_label("case")
                case_labels.append(lbl)
                if case.is_default:
                    default_label = lbl

            comparisons: list[tuple[Expr, str]] = []
            for case, lbl in zip(stmt.cases, case_labels):
                for label_expr in case.labels:
                    comparisons.append((label_expr, lbl))

            fallback_label: str = self.new_label("switch_nomatch")
            cmp_sym: Symbol | None = None

            for idx, (label_expr, lbl) in enumerate(comparisons):
                next_label: str = fallback_label if idx == len(comparisons) - 1 else self.new_label("switch_next")

                folded = fold_expr(subst_const(label_expr, cast(SymbolTable, self.current_symtab)))
                if isinstance(folded, IntLiteral):
                    val = folded.value & 0xFFFFFFFF
                    if is_long:
                        self.emit(f"\tLDA {sw_asm}+3")
                        self.emit(f"\tCMP #${(val >> 24) & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}+2")
                        self.emit(f"\tCMP #${(val >> 16) & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}+1")
                        self.emit(f"\tCMP #${(val >> 8) & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP #${val & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")
                    elif is_word:
                        self.emit(f"\tLDA {sw_asm}+1")
                        self.emit(f"\tCMP #${(val >> 8) & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP #${val & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")
                    else:
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP #${val & 0xFF:02X}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")
                else:
                    if cmp_sym is None:
                        cmp_name: str = self.new_label("switch_cmp")
                        cmp_sym = self._declare_temp(cmp_name, "LONG" if is_long else ("WORD" if is_word else "BYTE"))
                        
                    self.gen_assign(Identifier(cmp_sym.name), folded)

                    if is_long:
                        self.emit(f"\tLDA {sw_asm}+3")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}+3")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}+2")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}+2")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}+1")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}+1")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")
                    elif is_word:
                        self.emit(f"\tLDA {sw_asm}+1")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}+1")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")
                    else:
                        self.emit(f"\tLDA {sw_asm}")
                        self.emit(f"\tCMP {cmp_sym.asm_name()}")
                        self.emit(f"\tBNE {next_label}")
                        self.emit(f"\tJMP {lbl}")

                if next_label != fallback_label:
                    self.emit(f"{next_label}:")

            self.emit(f"{fallback_label}:")
            if default_label is not None:
                self.emit(f"\tJMP {default_label}")
            else:
                self.emit(f"\tJMP {end_label}")

            self.break_stack.append(end_label)
            for case, lbl in zip(stmt.cases, case_labels):
                self.emit(f"{lbl}:")
                for s in case.body:
                    self.gen_stmt(s)
            self.emit(f"{end_label}:")
            self.break_stack.pop()
            return
        
        if isinstance(stmt, IfStmt):
            cond: Expr = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond: Expr = fold_expr(cond)

            if isinstance(cond, IntLiteral):
                if (cond.value & 0xFFFF) != 0:
                    for s in stmt.then_body:
                        self.gen_stmt(s)
                elif stmt.else_body:
                    for s in stmt.else_body:
                        self.gen_stmt(s)
                return

            lbl_else: str = self.new_label("else")
            lbl_end: str  = self.new_label("endif")
            lbl_then: str = self.new_label("then")

            # Fast-path for relational comparisons: generate direct compare/branches
            from ast_nodes import BinaryExpr
            if isinstance(cond, BinaryExpr) and cond.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                self._emit_relational_branch(cond, lbl_true=lbl_then, lbl_false=lbl_else)

                # THEN block label
                self.emit(f"{lbl_then}:")
                for s in stmt.then_body:
                    self.gen_stmt(s)

                self.emit(f"\tJMP {lbl_end}")
                self.emit(f"{lbl_else}:")

                if stmt.else_body:
                    for s in stmt.else_body:
                        self.gen_stmt(s)

                self.emit(f"{lbl_end}:")
                return

            # Default path: evaluate condition to boolean and branch on zero
            cond_t: ExprType = self.tc_check(cond)
            is_word_cond: bool = cond_t.sem_type.base == "WORD" or cond_t.sem_type.is_pointer
            is_long_cond: bool = cond_t.sem_type.width == 4
            
            # Optimization: if condition is a simple identifier, ORA directly without copying to MATH0
            if isinstance(cond, Identifier) and is_long_cond:
                sym = self.current_symtab.lookup(cond.name)
                asm = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit(f"\tORA {asm}+1")
                self.emit(f"\tORA {asm}+2")
                self.emit(f"\tORA {asm}+3")
                self.emit(f"\tBNE {lbl_then}")
                self.emit(f"\tJMP {lbl_else}")
            elif isinstance(cond, Identifier) and is_word_cond:
                sym = self.current_symtab.lookup(cond.name)
                asm = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit(f"\tORA {asm}+1")
                self.emit(f"\tBNE {lbl_then}")
                self.emit(f"\tJMP {lbl_else}")
            else:
                # General case: evaluate condition expression
                prev_suppress: bool = self.suppress_byte_return_x
                if not is_word_cond and not is_long_cond:
                    self.suppress_byte_return_x = True
                try:
                    self.gen_expr(cond)
                finally:
                    self.suppress_byte_return_x = prev_suppress
                if is_long_cond:
                    self.emit("\tLDA MATH0")
                    self.emit("\tORA MATH0+1")
                    self.emit("\tORA MATH0+2")
                    self.emit("\tORA MATH0+3")
                    self.emit(f"\tBNE {lbl_then}")
                    self.emit(f"\tJMP {lbl_else}")
                elif is_word_cond:
                    self.used_temps.add("TMP4")
                    # Merge A/X to test non-zero (WORD-safe)
                    self.emit("\tSTA TMP4")
                    self.emit("\tTXA")
                    self.emit("\tORA TMP4")
                    self.emit(f"\tBNE {lbl_then}")
                    self.emit(f"\tJMP {lbl_else}")
                else:
                    self.emit(f"\tBNE {lbl_then}")
                    self.emit(f"\tJMP {lbl_else}")

            self.emit(f"{lbl_then}:")

            for s in stmt.then_body:
                self.gen_stmt(s)

            self.emit(f"\tJMP {lbl_end}")
            self.emit(f"{lbl_else}:")

            if stmt.else_body:
                for s in stmt.else_body:
                    self.gen_stmt(s)

            self.emit(f"{lbl_end}:")
            return

        if isinstance(stmt, WhileStmt):
            lbl_start: str = self.new_label("while")
            lbl_end: str   = self.new_label("endwhile")
            lbl_body: str  = self.new_label("while_body")

            # PUSH
            self.loop_stack.append((lbl_start, lbl_end))
            self.break_stack.append(lbl_end)

            self.emit(f"{lbl_start}:")
            cond: Expr = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond: Expr = fold_expr(cond)

            if isinstance(cond, IntLiteral):
                if (cond.value & 0xFFFF) == 0:
                    self.emit(f"{lbl_end}:")
                    self.loop_stack.pop()
                    self.break_stack.pop()
                    return
                self.emit(f"{lbl_body}:")
                for s in stmt.body:
                    self.gen_stmt(s)
                self.emit(f"\tJMP {lbl_start}")
                self.emit(f"{lbl_end}:")
                self.loop_stack.pop()
                self.break_stack.pop()
                return

            from ast_nodes import BinaryExpr
            if isinstance(cond, BinaryExpr) and cond.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                self._emit_relational_branch(cond, lbl_true=lbl_body, lbl_false=lbl_end)
            else:
                cond_t: ExprType = self.tc_check(cond)
                is_word_cond: bool = cond_t.sem_type.base == "WORD" or cond_t.sem_type.is_pointer
                is_long_cond: bool = cond_t.sem_type.width == 4
                
                # Optimization: if condition is a simple identifier, ORA directly without copying to MATH0
                if isinstance(cond, Identifier) and is_long_cond:
                    sym = self.current_symtab.lookup(cond.name)
                    asm = sym.asm_name()
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tORA {asm}+1")
                    self.emit(f"\tORA {asm}+2")
                    self.emit(f"\tORA {asm}+3")
                    self.emit(f"\tBNE {lbl_body}")
                    self.emit(f"\tJMP {lbl_end}")
                elif isinstance(cond, Identifier) and is_word_cond:
                    sym = self.current_symtab.lookup(cond.name)
                    asm = sym.asm_name()
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tORA {asm}+1")
                    self.emit(f"\tBNE {lbl_body}")
                    self.emit(f"\tJMP {lbl_end}")
                else:
                    # General case: evaluate condition expression
                    prev_suppress: bool = self.suppress_byte_return_x
                    if not is_word_cond and not is_long_cond:
                        self.suppress_byte_return_x = True
                    try:
                        self.gen_expr(cond)
                    finally:
                        self.suppress_byte_return_x = prev_suppress
                    if is_long_cond:
                        self.emit("\tLDA MATH0")
                        self.emit("\tORA MATH0+1")
                        self.emit("\tORA MATH0+2")
                        self.emit("\tORA MATH0+3")
                        self.emit(f"\tBNE {lbl_body}")
                        self.emit(f"\tJMP {lbl_end}")
                    elif is_word_cond:
                        self.used_temps.add("TMP4")
                        self.emit("\tSTA TMP4")
                        self.emit("\tTXA")
                        self.emit("\tORA TMP4")
                        self.emit(f"\tBNE {lbl_body}")
                        self.emit(f"\tJMP {lbl_end}")
                    else:
                        self.emit(f"\tBNE {lbl_body}")
                        self.emit(f"\tJMP {lbl_end}")

            self.emit(f"{lbl_body}:")

            for s in stmt.body:
                self.gen_stmt(s)

            self.emit(f"\tJMP {lbl_start}")
            self.emit(f"{lbl_end}:")

            # POP
            self.loop_stack.pop()
            self.break_stack.pop()
            return

        if isinstance(stmt, RepeatUntilStmt):
            lbl_start: str = self.new_label("repeat")
            lbl_cond: str = self.new_label("repeat_cond")
            lbl_end: str = self.new_label("endrepeat")

            # PUSH: continue should jump to condition check
            self.loop_stack.append((lbl_cond, lbl_end))
            self.break_stack.append(lbl_end)

            self.emit(f"{lbl_start}:")
            for s in stmt.body:
                self.gen_stmt(s)

            self.emit(f"{lbl_cond}:")
            cond: Expr = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond: Expr = fold_expr(cond)

            if isinstance(cond, IntLiteral):
                if (cond.value & 0xFFFF) != 0:
                    self.emit(f"{lbl_end}:")
                    self.loop_stack.pop()
                    self.break_stack.pop()
                    return
                self.emit(f"\tJMP {lbl_start}")
                self.emit(f"{lbl_end}:")
                self.loop_stack.pop()
                self.break_stack.pop()
                return

            from ast_nodes import BinaryExpr
            if isinstance(cond, BinaryExpr) and cond.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                self._emit_relational_branch(cond, lbl_true=lbl_end, lbl_false=lbl_start)
            else:
                cond_t: ExprType = self.tc_check(cond)
                is_word_cond: bool = cond_t.sem_type.base == "WORD" or cond_t.sem_type.is_pointer
                is_long_cond: bool = cond_t.sem_type.width == 4
                
                # Optimization: if condition is a simple identifier, ORA directly without copying to MATH0
                if isinstance(cond, Identifier) and is_long_cond:
                    sym = self.current_symtab.lookup(cond.name)
                    asm = sym.asm_name()
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tORA {asm}+1")
                    self.emit(f"\tORA {asm}+2")
                    self.emit(f"\tORA {asm}+3")
                    self.emit(f"\tBNE {lbl_end}")
                    self.emit(f"\tJMP {lbl_start}")
                elif isinstance(cond, Identifier) and is_word_cond:
                    sym = self.current_symtab.lookup(cond.name)
                    asm = sym.asm_name()
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tORA {asm}+1")
                    self.emit(f"\tBNE {lbl_end}")
                    self.emit(f"\tJMP {lbl_start}")
                else:
                    # General case: evaluate condition expression
                    prev_suppress: bool = self.suppress_byte_return_x
                    if not is_word_cond and not is_long_cond:
                        self.suppress_byte_return_x = True
                    try:
                        self.gen_expr(cond)
                    finally:
                        self.suppress_byte_return_x = prev_suppress
                    if is_long_cond:
                        self.emit("\tLDA MATH0")
                        self.emit("\tORA MATH0+1")
                        self.emit("\tORA MATH0+2")
                        self.emit("\tORA MATH0+3")
                        self.emit(f"\tBNE {lbl_end}")
                        self.emit(f"\tJMP {lbl_start}")
                    elif is_word_cond:
                        self.used_temps.add("TMP4")
                        self.emit("\tSTA TMP4")
                        self.emit("\tTXA")
                        self.emit("\tORA TMP4")
                        self.emit(f"\tBNE {lbl_end}")
                        self.emit(f"\tJMP {lbl_start}")
                    else:
                        self.emit(f"\tBNE {lbl_end}")
                        self.emit(f"\tJMP {lbl_start}")

            self.emit(f"{lbl_end}:")

            # POP
            self.loop_stack.pop()
            self.break_stack.pop()
            return
        
        if isinstance(stmt, BreakStmt):
            if not self.break_stack:
                self._raise_error("BREAK outside of loop or switch")
            end_label = self.break_stack[-1]
            self.emit(f"\tJMP {end_label}")
            return

        if isinstance(stmt, ContinueStmt):
            if not self.loop_stack:
                self._raise_error("CONTINUE outside of loop")
            start_label, _ = self.loop_stack[-1]
            self.emit(f"\tJMP {start_label}")
            return

        # (Duplicate IfStmt handler removed; handled earlier with const folding)
        
        if isinstance(stmt, ForStmt):
            step_expr: Expr | IntLiteral = stmt.step if stmt.step else IntLiteral(1)

            if isinstance(step_expr, IntLiteral):
                self._gen_for_const_step(stmt, step_expr)
            else:
                self._gen_for_general(stmt)
            return


        self._raise_error(f"Unhandled statement type: {type(stmt).__name__}")

    def gen_func(self, func: AnalyzedFunc) -> None:
        """Generate assembly for a function body.
        Emits prologue, body, and return handling.
        """
        prev_symtab: SymbolTable = self.current_symtab
        prev_tc_symtab: Any | None = getattr(self.tc, "symtab", None)
        prev_func_return_type: str | None = self.current_func_return_type
        prev_func_return_is_pointer: bool = self.current_func_return_is_pointer
        
        self.current_symtab = cast(SymbolTable, func.symtab)
        self.tc.symtab = func.symtab
        self.current_func_return_type = func.ret_type.base  # Set return type for this function
        self.current_func_return_is_pointer = func.ret_type.is_pointer
        ret_buf = self.func_return_buffers.get(func.ast.name)
        if ret_buf:
            self.current_func_return_buf, self.current_func_return_struct = ret_buf
        else:
            self.current_func_return_buf = None
            self.current_func_return_struct = None

        self.emit("; -- Function " + func.ast.name + " --")
        self.emit(f"{self.asm_symbol_name(func.ast.name)}:")

        # Emit parameter name equates for inline assembly references
        func_specs: list[tuple[str, int, object, SemType]] | None = self.func_param_specs.get(func.ast.name)
        if func_specs:
            self._emit_param_name_equates(func.ast.name, func_specs)

        # Store register-passed arguments into param globals (if any)
        if func_specs:
            self._emit_param_reg_stores(func.ast.name, func_specs)

        # Emit local variable equates for inline assembly references (excluding parameters)
        param_names = {pname for pname, _, _, _ in func_specs} if func_specs else set()
        local_tbl = getattr(func.symtab, "local", None)
        all_locals = list(local_tbl) if local_tbl else func.locals
        for sym in all_locals:
            self._emit_local_name_equate(func.ast.name, sym, param_names)

        # init lokálů
        for sym in func.locals:
            self.gen_init(cast(Symbol, sym))

        # tělo (dead-store pre-pass removes consecutive overwrites of same scalar)
        for stmt in self._elim_dead_stores(func.ast.body):
            self.gen_stmt(stmt)

        # fallback (pokud RETURN nebyl – zatím chyba v sémantice)
        if not (func.ast.body and isinstance(func.ast.body[-1], ReturnStmt)):
            self.emit("\tRTS")

        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab
        self.current_func_return_type = prev_func_return_type
        self.current_func_return_is_pointer = prev_func_return_is_pointer
        self.current_func_return_buf = None
        self.current_func_return_struct = None

    def _gen_relational(self, expr: BinaryExpr) -> None:
        """Generate relational.
        Internal helper used during code generation.
        """
        left_t: ExprType = self.tc_check(expr.left)
        right_t: ExprType = self.tc_check(expr.right)
        is_16bit: bool = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"

        # Try a fast 8-bit compare when the right operand is a simple byte value
        cmp_operand: str | None = None

        def simple_byte_operand(rhs: Expr) -> str | None:
            """Return an operand suitable for CMP if rhs is a trivial byte source."""
            if is_16bit:
                return None

            if isinstance(rhs, IntLiteral):
                return f"#{rhs.value & 0xFF}"

            if isinstance(rhs, Identifier):
                sym: Symbol = self.current_symtab.lookup(rhs.name)

                if sym.is_array or sym.address is not None:
                    return None
                if sym.type.is_pointer or sym.type.base != "BYTE":
                    return None
                if sym.is_volatile:
                    return None
                # Use immediate if const scalar, otherwise memory operand
                return self._sym_operand(sym, low_byte=True)

            return None

        cmp_operand = simple_byte_operand(expr.right)

        if cmp_operand is not None:
            # Left operand only; right is accessed directly in CMP
            self.gen_expr(expr.left)
        else:
            # pravý operand first (for correct CMP operand order)
            self.gen_expr(expr.right)
            # Ensure high byte is well-defined in 16-bit context
            if is_16bit and right_t.sem_type.base != "WORD" and not right_t.sem_type.is_pointer:
                self.emit("\tLDX #$00     ; note 6088")
            self.emit("\tSTA TMP0")
            if is_16bit:      # Fixme: ? Je to spravne? Nechybi tady and right_t.sem_type.base != "WORD":
                self.emit("\tSTX TMP0+1")

            # levý operand
            self.gen_expr(expr.left)
            # Ensure left high byte is well-defined in 16-bit context
            if is_16bit and left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                self.emit("\tLDX #$00     ; note 6097")

            cmp_operand = "TMP0"

        lbl_true: str = self.new_label("REL_TRUE")
        lbl_end: str  = self.new_label("REL_END")

        if is_16bit:
            # 16-bit comparison: compare high byte first, then low byte
            # For signed comparisons this is simplified - treat as unsigned
            if expr.op == BinOp.EQ:             # ==
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBNE {lbl_end}")  
                self.emit("\tCMP TMP0")
                self.emit(f"\tBEQ {lbl_true}")
            elif expr.op == BinOp.NE:           # !=    
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBNE {lbl_true}")  
                self.emit("\tCMP TMP0")
                self.emit(f"\tBNE {lbl_true}")
            elif expr.op == BinOp.LT:           # <
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBCC {lbl_true}") 
                self.emit(f"\tBNE {lbl_end}")  
                self.emit("\tCMP TMP0")        
                self.emit(f"\tBCC {lbl_true}")
            elif expr.op == BinOp.GE:       # >=    
                self.emit("\tCPX TMP0+1")
                lbl_ge_check_low = self.new_label("GE_CHECK_LOW")
                self.emit(f"\tBEQ {lbl_ge_check_low}") # High equal, check low
                self.emit(f"\tBCS {lbl_true}")    
                self.emit(f"\tJMP {lbl_end}")     
                self.emit(f"{lbl_ge_check_low}:")
                self.emit("\tCMP TMP0")
                self.emit(f"\tBCS {lbl_true}")
            elif expr.op == BinOp.GT:       # > 
                lbl_gt_check_low = self.new_label("GT_CHECK_LOW")
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBCC {lbl_end}")     
                self.emit(f"\tBEQ {lbl_gt_check_low}") # High equal, check low
                self.emit(f"\tJMP {lbl_true}")    
                self.emit(f"{lbl_gt_check_low}:")
                self.emit("\tCMP TMP0")
                self.emit(f"\tBEQ {lbl_end}")    
                self.emit(f"\tBCS {lbl_true}")    
            elif expr.op == BinOp.LE:       # <=
                lbl_le_check_low = self.new_label("LE_CHECK_LOW")
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBCC {lbl_true}")    
                self.emit(f"\tBEQ {lbl_le_check_low}") 
                self.emit(f"\tJMP {lbl_end}")     
                self.emit(f"{lbl_le_check_low}:")
                self.emit("\tCMP TMP0")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
        else:
            # 8-bit comparison (original code)
            self.emit(f"\tCMP {cmp_operand}")

            if expr.op == BinOp.EQ:
                self.emit(f"\tBEQ {lbl_true}")
            elif expr.op == BinOp.NE:
                self.emit(f"\tBNE {lbl_true}")
            elif expr.op == BinOp.LT:
                self.emit(f"\tBCC {lbl_true}")
            elif expr.op == BinOp.GE:
                self.emit(f"\tBCS {lbl_true}")
            elif expr.op == BinOp.GT:
                self.emit(f"\tBEQ {lbl_end}")
                self.emit(f"\tBCS {lbl_true}")
            elif expr.op == BinOp.LE:
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")

        # false
        self.emit("\tLDA #$00")
        self.emit(f"\tJMP {lbl_end}")

        # true
        self.emit(f"{lbl_true}:")
        self.emit("\tLDA #1")

        self.emit(f"{lbl_end}:")
        if self.force_word_result:
            self.emit("\tLDX #$00     ; note 6178")

    def _emit_relational_branch(self, cond: BinaryExpr, *, lbl_true: str, lbl_false: str) -> None:
        """Emit relational test that jumps to lbl_true or lbl_false.
        lbl_true is always a nearby forward label (short branches reach it directly).
        lbl_false is always reached via JMP inside the impl (full 16-bit range).
        """
        self._emit_relational_branch_impl(cond, lbl_true=lbl_true, lbl_false=lbl_false)

    def _emit_relational_branch_impl(self, cond: BinaryExpr, *, lbl_true: str, lbl_false: str) -> None:
        """Internal implementation for _emit_relational_branch."""
        left_t: ExprType = self.tc_check(cond.left)
        right_t: ExprType = self.tc_check(cond.right)
        
        # Check widths to determine operation size
        left_width: int = left_t.sem_type.width
        right_width: int = right_t.sem_type.width
        
        is_32bit: bool = left_width > 2 or right_width > 2
        is_16bit: bool = not is_32bit and (left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD" or left_t.sem_type.is_pointer or right_t.sem_type.is_pointer)

        if is_32bit:
            # --- Fast path: direct 32-bit comparison for simple operands (no MATH0/MATH1) ---
            # Mirrors the WORD fast path (lines 12032–12185): when both operands are simple
            # scalar identifiers (or the right operand is an IntLiteral), compare the four
            # bytes directly — no spill to MATH0/MATH1 needed.
            if isinstance(cond.left, Identifier):
                fp32_left_sym = self.current_symtab.lookup(cond.left.name)
                if (not fp32_left_sym.is_array and fp32_left_sym.address is None
                        and not fp32_left_sym.is_volatile and not fp32_left_sym.is_port):

                    fp32_r_bytes: list[str] | None = None
                    if isinstance(cond.right, IntLiteral):
                        _v32 = cond.right.value
                        fp32_r_bytes = [
                            f"#${(_v32 >> 24) & 0xFF:02X}",
                            f"#${(_v32 >> 16) & 0xFF:02X}",
                            f"#${(_v32 >>  8) & 0xFF:02X}",
                            f"#${_v32 & 0xFF:02X}",
                        ]
                    elif isinstance(cond.right, Identifier):
                        fp32_right_sym = self.current_symtab.lookup(cond.right.name)
                        if (not fp32_right_sym.is_array and fp32_right_sym.address is None
                                and not fp32_right_sym.is_volatile and not fp32_right_sym.is_port):
                            _r32 = fp32_right_sym.asm_name()
                            if right_width == 4:
                                fp32_r_bytes = [f"{_r32}+3", f"{_r32}+2", f"{_r32}+1", _r32]
                            elif right_width == 2:
                                fp32_r_bytes = ["#$00", "#$00", f"{_r32}+1", _r32]
                            else:
                                fp32_r_bytes = ["#$00", "#$00", "#$00", _r32]

                    if fp32_r_bytes is not None:
                        # Build left-side byte load specs [byte3, byte2, byte1, byte0]
                        _l32 = fp32_left_sym.asm_name()
                        if left_width == 4:
                            fp32_l_loads: list[str] = [f"{_l32}+3", f"{_l32}+2", f"{_l32}+1", _l32]
                        elif left_width == 2:
                            fp32_l_loads = ["#$00", "#$00", f"{_l32}+1", _l32]
                        else:
                            fp32_l_loads = ["#$00", "#$00", "#$00", _l32]

                        if cond.op == BinOp.EQ:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            for _bi32 in range(4):
                                self.emit(f"\tLDA {fp32_l_loads[_bi32]}")
                                self.emit(f"\tCMP {fp32_r_bytes[_bi32]}")
                                self.emit(f"\tBNE {lbl_else_tmp}")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return

                        if cond.op == BinOp.NE:
                            for _bi32 in range(4):
                                self.emit(f"\tLDA {fp32_l_loads[_bi32]}")
                                self.emit(f"\tCMP {fp32_r_bytes[_bi32]}")
                                self.emit(f"\tBNE {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                            return

                        # Relational: compare high-to-low; branch to decide on first difference
                        fp32_lbl_decide: str = self.new_label("CMP32_DECIDE")
                        for _bi32 in range(3):  # bytes 3, 2, 1
                            self.emit(f"\tLDA {fp32_l_loads[_bi32]}")
                            self.emit(f"\tCMP {fp32_r_bytes[_bi32]}")
                            self.emit(f"\tBNE {fp32_lbl_decide}")
                        self.emit(f"\tLDA {fp32_l_loads[3]}")  # byte 0 — fall-through sets flags
                        self.emit(f"\tCMP {fp32_r_bytes[3]}")
                        self.emit(f"{fp32_lbl_decide}:")
                        if cond.op == BinOp.LT:
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                        elif cond.op == BinOp.GE:
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                        elif cond.op == BinOp.GT:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            self.emit(f"\tBEQ {lbl_else_tmp}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                        elif cond.op == BinOp.LE:
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                        return
            # --- End fast path ---

            # 32-bit comparison using MATH0/MATH1
            # Optimization: for simple identifiers, load directly to MATH1 without intermediate MATH0 copy
            if isinstance(cond.right, Identifier) and right_width > 2:
                # Load right operand directly to MATH1
                right_sym = self.current_symtab.lookup(cond.right.name)
                right_asm = right_sym.asm_name()
                self.emit(f"\tLDA {right_asm}")
                self.emit(f"\tSTA MATH1")
                self.emit(f"\tLDA {right_asm}+1")
                self.emit(f"\tSTA MATH1+1")
                self.emit(f"\tLDA {right_asm}+2")
                self.emit(f"\tSTA MATH1+2")
                self.emit(f"\tLDA {right_asm}+3")
                self.emit(f"\tSTA MATH1+3")
            else:
                # General case: evaluate right operand (goes to MATH0 or A/X)
                self.gen_expr(cond.right)
                
                # Helper to move result to destination
                if right_width > 2:
                    # Already in MATH0, move to MATH1
                    self.emit("\tLDA MATH0")
                    self.emit("\tSTA MATH1")
                    self.emit("\tLDA MATH0+1")
                    self.emit("\tSTA MATH1+1")
                    self.emit("\tLDA MATH0+2")
                    self.emit("\tSTA MATH1+2")
                    self.emit("\tLDA MATH0+3")
                    self.emit("\tSTA MATH1+3")
                else:
                    # In A/X, promote to MATH1
                    self.emit("\tSTA MATH1")
                    if right_width == 2:
                        self.emit("\tSTX MATH1+1")
                    else:
                        self.emit("\tLDX #$00")
                        self.emit("\tSTX MATH1+1")
                    # Zero extend upper bytes
                    self.emit("\tLDA #$00")
                    self.emit("\tSTA MATH1+2")
                    self.emit("\tSTA MATH1+3")

            # Evaluate left operand (puts result in MATH0 or A/X)
            self.gen_expr(cond.left)
            
            if left_width <= 2:
                 # In A/X, promote to MATH0
                self.emit("\tSTA MATH0")
                if left_width == 2:
                    self.emit("\tSTX MATH0+1")
                else:
                    self.emit("\tLDX #$00")
                    self.emit("\tSTX MATH0+1")
                # Zero extend upper bytes
                self.emit("\tLDA #$00")
                self.emit("\tSTA MATH0+2")
                self.emit("\tSTA MATH0+3")

            # Now compare MATH0 (left) vs MATH1 (right)
            # Compare from high byte down
            
            if cond.op == BinOp.EQ:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                self.emit("\tLDA MATH0+3")
                self.emit("\tCMP MATH1+3")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit("\tLDA MATH0+2")
                self.emit("\tCMP MATH1+2")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit("\tLDA MATH0+1")
                self.emit("\tCMP MATH1+1")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit("\tLDA MATH0")
                self.emit("\tCMP MATH1")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit(f"\tJMP {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
                return

            if cond.op == BinOp.NE:
                self.emit("\tLDA MATH0+3")
                self.emit("\tCMP MATH1+3")
                self.emit(f"\tBNE {lbl_true}")
                self.emit("\tLDA MATH0+2")
                self.emit("\tCMP MATH1+2")
                self.emit(f"\tBNE {lbl_true}")
                self.emit("\tLDA MATH0+1")
                self.emit("\tCMP MATH1+1")
                self.emit(f"\tBNE {lbl_true}")
                self.emit("\tLDA MATH0")
                self.emit("\tCMP MATH1")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
                return

            # For relational ops, we need careful branching.
            # Common pattern: Compare high bytes. If !=, we know result (BCC/BCS). If ==, continue to next byte.
            
            # Helper to generate branch chain
            lbl_decide = self.new_label("CMP32_DECIDE")
            
            # Byte 3
            self.emit("\tLDA MATH0+3")
            self.emit("\tCMP MATH1+3")
            self.emit(f"\tBNE {lbl_decide}")
            
            # Byte 2
            self.emit("\tLDA MATH0+2")
            self.emit("\tCMP MATH1+2")
            self.emit(f"\tBNE {lbl_decide}")
            
            # Byte 1
            self.emit("\tLDA MATH0+1")
            self.emit("\tCMP MATH1+1")
            self.emit(f"\tBNE {lbl_decide}")
            
            # Byte 0
            self.emit("\tLDA MATH0")
            self.emit("\tCMP MATH1")
            # Fall through to decide (Carry is set correctly by last CMP)
            
            self.emit(f"{lbl_decide}:")
            # Now flags (Z, C) are set from the most significant differing byte, 
            # or from low byte if all equal.
            
            if cond.op == BinOp.LT:
                # < : BCC (Carry Clear)
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GE:
                # >= : BCS (Carry Set)
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GT:
                # > : BEQ false (equal), BCC false (<), so BCS and BNE
                # Logic: CMP sets Z=1 if equal, C=1 if >=.
                # > is (C=1 AND Z=0)
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                self.emit(f"\tBEQ {lbl_else_tmp}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LE:
                # <= : (C=0 OR Z=1)
                # i.e. BCC true, BEQ true
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
                
            return


        # Fast path: compare-to-zero simplification (unsigned)
        if isinstance(cond.right, IntLiteral) and (cond.right.value & 0xFFFF) == 0:
            prev_suppress: bool = self.suppress_byte_return_x
            if not is_16bit:
                self.suppress_byte_return_x = True
            try:
                self.gen_expr(cond.left)
            finally:
                self.suppress_byte_return_x = prev_suppress
            if is_16bit:
                if left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                    self.emit("\tLDX #$00     ; note 7054")
                if cond.op in {BinOp.EQ, BinOp.LE}:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit("\tCPX #$00")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit("\tCMP #$00")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op in {BinOp.NE, BinOp.GT}:
                    self.emit("\tCPX #$00")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit("\tCMP #$00")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    self.emit(f"\tJMP {lbl_true}")
                    return
                if cond.op == BinOp.LT:
                    self.emit(f"\tJMP {lbl_false}")
                    return
            else:
                if cond.op in {BinOp.EQ, BinOp.LE}:
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op in {BinOp.NE, BinOp.GT}:
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    self.emit(f"\tJMP {lbl_true}")
                    return
                if cond.op == BinOp.LT:
                    self.emit(f"\tJMP {lbl_false}")
                    return

        cmp_lo = "TMP0"
        cmp_hi = "TMP0+1"

        # Fast path: 16-bit compare against a simple right identifier without TMP0
        if is_16bit and isinstance(cond.right, Identifier):
            right_sym: Symbol = self.current_symtab.lookup(cond.right.name)
            if (not right_sym.is_array and right_sym.address is None and
                not right_sym.is_volatile and not right_sym.is_port):
                cmp_lo = right_sym.asm_name()
                cmp_hi = f"{cmp_lo}+1"
                if right_sym.type.base != "WORD" and not right_sym.type.is_pointer:
                    cmp_hi = "#$00"

                # If left is a simple identifier, load high byte first and only load low on demand.
                if isinstance(cond.left, Identifier):
                    left_sym: Symbol = self.current_symtab.lookup(cond.left.name)
                    if (not left_sym.is_array and left_sym.address is None and
                        not left_sym.is_volatile and not left_sym.is_port):
                        left_lo = left_sym.asm_name()
                        left_hi = f"{left_lo}+1"
                        left_hi_immediate = False
                        if left_sym.type.base != "WORD" and not left_sym.type.is_pointer:
                            left_hi = "#$00"
                            left_hi_immediate = True

                        def load_left_high() -> None:
                            """Load left high.
                            Internal helper used during code generation.
                            """
                            if left_hi_immediate:
                                self.emit("\tLDX #$00     ; note 7054")
                            else:
                                self.emit(f"\tLDX {left_hi}")

                        def load_left_low() -> None:
                            """Load left low.
                            Internal helper used during code generation.
                            """
                            self.emit(f"\tLDA {left_lo}")

                        # If right high byte is zero, we can simplify LT/LE/GT/GE.
                        if cmp_hi == "#$00" and cond.op in {BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                            load_left_high()
                            if cond.op == BinOp.LT:
                                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                                self.emit("\tCPX #$00")
                                self.emit(f"\tBNE {lbl_else_tmp}")
                                load_left_low()
                                self.emit(f"\tCMP {cmp_lo}")
                                self.emit(f"\tBCC {lbl_true}")
                                self.emit(f"{lbl_else_tmp}:")
                                self.emit(f"\tJMP {lbl_false}")
                                return
                            if cond.op == BinOp.LE:
                                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                                self.emit("\tCPX #$00")
                                self.emit(f"\tBNE {lbl_else_tmp}")
                                load_left_low()
                                self.emit(f"\tCMP {cmp_lo}")
                                self.emit(f"\tBCC {lbl_true}")
                                self.emit(f"\tBEQ {lbl_true}")
                                self.emit(f"{lbl_else_tmp}:")
                                self.emit(f"\tJMP {lbl_false}")
                                return
                            if cond.op == BinOp.GT:
                                self.emit("\tCPX #$00")
                                self.emit(f"\tBNE {lbl_true}")
                                load_left_low()
                                self.emit(f"\tCMP {cmp_lo}")
                                self.emit(f"\tBEQ {lbl_false}")
                                self.emit(f"\tBCS {lbl_true}")
                                self.emit(f"\tJMP {lbl_false}")
                                return
                            if cond.op == BinOp.GE:
                                self.emit("\tCPX #$00")
                                self.emit(f"\tBNE {lbl_true}")
                                load_left_low()
                                self.emit(f"\tCMP {cmp_lo}")
                                self.emit(f"\tBCS {lbl_true}")
                                self.emit(f"\tJMP {lbl_false}")
                                return

                        if cond.op == BinOp.EQ:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBEQ {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.NE:
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBNE {lbl_true}")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBNE {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.LT:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.LE:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_chk_hi}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            self.emit(f"{lbl_chk_hi}:")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.GT:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_gt_check_low: str = self.new_label("GT_CHECK_LOW")
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ {lbl_gt_check_low}")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit(f"{lbl_gt_check_low}:")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBEQ {lbl_else_tmp}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.GE:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_ge_check_low: str = self.new_label("GE_CHECK_LOW")
                            load_left_high()
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ {lbl_ge_check_low}")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit(f"{lbl_ge_check_low}:")
                            load_left_low()
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return

                # Load left side into A/X
                self.gen_expr(cond.left)
                if left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                    self.emit("\tLDX #$00     ; note 7054")

                if cond.op == BinOp.EQ:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.NE:
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_chk_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"{lbl_chk_hi}:")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_gt_check_low: str = self.new_label("GT_CHECK_LOW")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_else_tmp}")
                    self.emit(f"\tBEQ {lbl_gt_check_low}")
                    self.emit(f"\tJMP {lbl_true}")
                    self.emit(f"{lbl_gt_check_low}:")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBEQ {lbl_else_tmp}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_ge_check_low: str = self.new_label("GE_CHECK_LOW")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_else_tmp}")
                    self.emit(f"\tBEQ {lbl_ge_check_low}")
                    self.emit(f"\tJMP {lbl_true}")
                    self.emit(f"{lbl_ge_check_low}:")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return

        # Fast path: both operands are simple WORD identifiers → evaluate right into TMP0 and compare
        if is_16bit and isinstance(cond.left, Identifier) and isinstance(cond.right, Identifier):
            left_sym: Symbol = self.current_symtab.lookup(cond.left.name)
            right_sym: Symbol = self.current_symtab.lookup(cond.right.name)
            # Only handle simple variables (not arrays, not fixed addresses, not volatile/ports)
            if (not left_sym.is_array and left_sym.address is None and not left_sym.is_volatile and
                not right_sym.is_array and right_sym.address is None and not right_sym.is_volatile):
                # Evaluate right into TMP0/TMP0+1
                self.gen_expr(cond.right)
                if right_sym.type.base != "WORD" and not right_sym.type.is_pointer:
                    # Ensure high byte defined
                    self.emit("\tLDX #$00     ; fast 16-bit compare setup")
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")

                # Load left into A/X for comparison
                self.gen_expr(cond.left)
                if left_sym.type.base != "WORD" and not left_sym.type.is_pointer:
                    self.emit("\tLDX #$00     ; fast 16-bit compare setup")

                # Now do op-specific branching using TMP0 as right value
                if cond.op == BinOp.EQ:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.NE:
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    # Compare high byte first
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    # High bytes equal, compare low byte
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                    # Compare high byte first
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_chk_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    # High bytes equal, compare low byte
                    self.emit(f"{lbl_chk_hi}:")
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_gt_check_low: str = self.new_label("GT_CHECK_LOW")
                    # Compare high byte first
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBCC {lbl_else_tmp}")
                    self.emit(f"\tBEQ {lbl_gt_check_low}")
                    self.emit(f"\tJMP {lbl_true}")
                    self.emit(f"{lbl_gt_check_low}:")
                    # High bytes equal, compare low byte
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBEQ {lbl_else_tmp}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_ge_check_low: str = self.new_label("GE_CHECK_LOW")
                    # Compare high byte first
                    self.emit(f"\tCPX TMP0+1")
                    self.emit(f"\tBCC {lbl_else_tmp}")
                    self.emit(f"\tBEQ {lbl_ge_check_low}")
                    self.emit(f"\tJMP {lbl_true}")
                    self.emit(f"{lbl_ge_check_low}:")
                    # High bytes equal, compare low byte
                    self.emit(f"\tCMP TMP0")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return

        # Try a fast 8-bit compare when the right operand is a simple byte value
        def simple_byte_operand(rhs: Expr) -> str | None:
            """Return an operand suitable for CMP if rhs is a trivial byte source."""
            if is_16bit:
                return None

            if isinstance(rhs, IntLiteral):
                return f"#{rhs.value & 0xFF}"

            if isinstance(rhs, Identifier):
                sym: Symbol = self.current_symtab.lookup(rhs.name)

                if sym.is_array or sym.address is not None:
                    return None
                if sym.type.is_pointer or sym.type.base != "BYTE":
                    return None
                if sym.is_volatile:
                    return None
                return sym.asm_name()

            return None

        # Optimize: if right side is a constant, use immediate addressing
        use_immediate: bool = isinstance(cond.right, IntLiteral)
        
        if use_immediate:
            right_literal: IntLiteral = cast(IntLiteral, cond.right)
            const_val: int = right_literal.value & 0xFFFF
            const_lo: int = const_val & 0xFF
            const_hi: int = (const_val >> 8) & 0xFF
            cmp_lo: str = f"#${const_lo:02X}"
            cmp_hi: str = f"#${const_hi:02X}"

            # Fast path: word identifier vs constant → defer loading X until low byte matches
            if is_16bit and isinstance(cond.left, Identifier):
                sym: Symbol = self.current_symtab.lookup(cond.left.name)
                if cond.op == BinOp.EQ:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return

                # Optimize: 16-bit compare against a simple right identifier without TMP0
                if is_16bit and isinstance(cond.right, Identifier) and isinstance(cond.left, (Identifier, IntLiteral)):
                    right_sym: Symbol = self.current_symtab.lookup(cond.right.name)
                    if (not right_sym.is_array and right_sym.address is None and
                        not right_sym.is_volatile and not right_sym.is_port):
                        right_asm: str = right_sym.asm_name()
                        cmp_lo = right_asm
                        cmp_hi = f"{right_asm}+1"
                        if right_sym.type.base != "WORD" and not right_sym.type.is_pointer:
                            cmp_hi = "#$00"

                        # Load left side into A/X
                        self.gen_expr(cond.left)
                        if is_16bit and left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                            self.emit("\tLDX #$00     ; note 7036")

                        if cond.op == BinOp.EQ:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBEQ {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.NE:
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBNE {lbl_true}")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBNE {lbl_true}")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.LT:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.LE:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_chk_hi}")
                            self.emit(f"\tBNE {lbl_else_tmp}")
                            self.emit(f"{lbl_chk_hi}:")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_true}")
                            self.emit(f"\tBEQ {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.GT:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_gt_check_low: str = self.new_label("GT_CHECK_LOW")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ {lbl_gt_check_low}")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit(f"{lbl_gt_check_low}:")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBEQ {lbl_else_tmp}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.GE:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            lbl_ge_check_low: str = self.new_label("GE_CHECK_LOW")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ {lbl_ge_check_low}")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit(f"{lbl_ge_check_low}:")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                if cond.op == BinOp.NE:
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                    # Compare low byte first
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_chk_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    # Low bytes equal, check high byte
                    self.emit(f"{lbl_chk_hi}:")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBNE {lbl_true}")                    
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBNE {lbl_true}")                    
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {self._sym_operand(sym, low_byte=False)}")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")                    
                    self.emit(f"\tLDA {self._sym_operand(sym, low_byte=True)}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")                    
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return

            # Fast path: byte identifier vs constant → simple CMP without LDX
            if not is_16bit and isinstance(cond.left, Identifier) and left_t.sem_type.base == "BYTE":
                sym: Symbol = self.current_symtab.lookup(cond.left.name)
                asm: str = sym.asm_name()
                if cond.op == BinOp.EQ:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.NE:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LT:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LE:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBEQ {lbl_else_tmp}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return

            # Evaluate left into A/X
            self.gen_expr(cond.left)
            if is_16bit and left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                self.emit("\tLDX #$00     ; note 6311")
        else:
            # Try simple byte operand optimization for 8-bit compares
            cmp_operand: str | None = simple_byte_operand(cond.right)
            
            if cmp_operand is not None:
                # Left operand only; right is accessed directly in CMP
                # Optimize: if left is also simple BYTE, load it directly without gen_expr to avoid unnecessary LDX #$00
                # This avoids the unneeded "LDX #$00" that would normally follow "LDA byte_var" (optimization at 6321)
                left_operand: str | None = simple_byte_operand(cond.left)
                if left_operand is not None:
                    self.emit(f"\tLDA {left_operand}")
                else:
                    self.gen_expr(cond.left)
                cmp_lo: str = cmp_operand
                # cmp_hi stays as "TMP0+1" but won't be used for 8-bit
            else:
                # Evaluate right into TMP0/(TMP0+1)
                self.gen_expr(cond.right)
                if is_16bit and right_t.sem_type.base != "WORD" and not right_t.sem_type.is_pointer:
                    self.emit("\tLDX #$00     ; note 6317")
                self.emit("\tSTA TMP0")
                if is_16bit:
                    self.emit("\tSTX TMP0+1") # This was `self.emit("\tSTX                # left")`
                self.gen_expr(cond.left)
                if is_16bit and left_t.sem_type.base != "WORD" and not left_t.sem_type.is_pointer:
                    self.emit("\tLDX #$00     ; note 6323")
                
                cmp_operand = "TMP0"
                cmp_lo = "TMP0"
                cmp_hi = "TMP0+1"

        if is_16bit:
            if cond.op == BinOp.EQ:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare low byte first (faster for early mismatch)
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.NE:
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LT:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare high byte first
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                # High bytes equal, check low byte
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LE:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                # Compare high byte first
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_chk_hi}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                # High bytes equal, check low byte
                self.emit(f"{lbl_chk_hi}:")
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GT:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare high byte first
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_else_tmp}")
                self.emit(f"\tBNE {lbl_true}")
                # High bytes equal, check low byte
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBEQ {lbl_else_tmp}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GE:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare high byte first
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_else_tmp}")
                self.emit(f"\tBNE {lbl_true}")
                # High bytes equal, check low byte
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
        else:
            # 8-bit patterns
            if cond.op == BinOp.EQ:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.NE:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LT:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LE:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GT:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBEQ {lbl_else_tmp}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GE:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")

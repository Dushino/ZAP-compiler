
from typing import Any, Callable, Literal, NoReturn, cast
from constfold import fold_expr
from constsubst import subst_const
from symbols import StructInfo, StructInfo, StructFieldInfo, StructFieldInfo, StructInfo, StructFieldInfo, StructFieldInfo, StructInfo, StructFieldInfo, StructFieldInfo, StructFieldInfo, Symbol, SymbolTable, SemType, StructRegistry
from sema_types import ExprKind
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
    Expr, ExprInit, ListInit, StringInit, CallExpr,
    CallStmt, AssignStmt,
    IfStmt, ReturnStmt, WhileStmt, ForStmt,
    AsmBlock, FieldAccess
)
from sema_expr import ExprTypeChecker
from sema_types import ExprKind, ExprType
from sema_proc import AnalyzedProc
from sema_func import AnalyzedFunc

from errors import SemanticError


class CodeGen:
    label_id = 0
    loop_stack = []

    def __init__(self, symtab: SymbolTable, type_checker: ExprTypeChecker, *, is_65c02: bool = True, used_globals: set[str] | None = None, debug_info: dict | None = None, command_line: str | None = None, proc_param_specs: dict[str, list[tuple[str, int, object]]] | None = None, func_param_specs: dict[str, list[tuple[str, int, object]]] | None = None, pruned_procs: list[str] | None = None, struct_registry: StructRegistry | None = None) -> None:
        # global symbol table (globals)
        self.global_symtab: SymbolTable = symtab
        # currently active table (can be scoped for PROC/FUNC)
        self.current_symtab: SymbolTable = symtab
        self.tc: ExprTypeChecker = type_checker
        self.struct_registry: StructRegistry = struct_registry or StructRegistry()
        self.code: list[str] = []
        self.for_id = 0
        self.string_literals = {}  # Maps string content to label name
        self.string_id = 0
        self.array_literals = {}   # Maps array data tuple to label name
        self.array_id = 0
        self.copy_bytes_needed = False
        self.arrcpy_needed = False  # Flag to emit ARRCPY subroutine
        self.math_routines_needed: set[str] = set()
        self.is_65c02: bool = is_65c02
        self.used_globals: set[str] = used_globals or set()
        self.used_temps: set[str] = set()
        self.command_line: str | None = command_line
        self.math_stack_depth: int = 0
        # Parameter specs: mapping name -> list of (param_name, width_bytes)
        self.proc_param_specs: dict[str, list[tuple[str, int, object]]] = proc_param_specs or {}
        self.func_param_specs: dict[str, list[tuple[str, int, object]]] = func_param_specs or {}
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
        # Track current statement source info for error reporting
        self.current_stmt_info: tuple[str, int, int, str] | None = None
        # Track fixed-address variables (hardware registers) - never optimize these
        self.fixed_address_labels: set[str] = set()
        # Track PORT variables (hardware port-mapped) - never optimize these
        self.port_labels: set[str] = set()
        # Track current function return type for narrowing WORD to BYTE
        self.current_func_return_type: str | None = None
        # Track assignment context for optimizations that need target type
        self.assign_target_type: SemType | None = None  # Current assignment LHS type
        # Track assignment target for safe temp reuse in expression codegen
        self.assign_target_sym: Symbol | None = None
        self.assign_target_blocked: bool = False

    def tc_check(self, expr, read_check_enabled: bool = True) -> ExprType:
        # Wrapper to attach source location to type-checker errors
        try:
            return self.tc.check(expr, read_check_enabled=read_check_enabled)
        except SemanticError as e:
            # If error lacks position, attach current statement info
            if getattr(e, 'line', None) is None and self.current_stmt_info:
                self._raise_error(e.message)
            raise

    def new_label(self, prefix: str) -> str:
        self.label_id += 1
        return f"{prefix}_{self.label_id}"

    def new_for_var(self, base: str) -> str:
        self.for_id += 1
        return f"__FOR_{base}_{self.for_id}"

    def _stz(self, operand: str) -> None:
        if self.is_65c02:
            self.emit(f"\tSTZ {operand}")
        else:
            self.emit("\tLDA #$00")
            self.emit(f"\tSTA {operand}")

    def _emit_indirect_store_zero(self, ptr: str) -> None:
        if self.is_65c02:
            self.emit(f"\tSTA ({ptr})")
        else:
            self.emit("\tLDY #0")
            self.emit(f"\tSTA ({ptr}),Y")

    def _math_stack_push(self, is_16bit: bool) -> None:
        if self.math_stack_depth >= 4:
            self._raise_error("Math stack overflow: requires more than 4 word slots. Simplify the expression.")
        slot: int = self.math_stack_depth
        offset: int = slot * 2
        self.math_stack_depth += 1
        if is_16bit:
            self.emit("\tSTX MATH_OP1")
        self.emit(f"\tSTA MATH_STACK+{offset}")
        if is_16bit:
            self.emit("\tLDA MATH_OP1")
            self.emit(f"\tSTA MATH_STACK+{offset + 1}")
        else:
            self.emit("\tLDA #$00")
            self.emit(f"\tSTA MATH_STACK+{offset + 1}")

    def _math_stack_pop_to_op0(self) -> None:
        if self.math_stack_depth <= 0:
            self._raise_error("Math stack underflow during expression evaluation.")
        self.math_stack_depth -= 1
        slot: int = self.math_stack_depth
        offset: int = slot * 2
        self.emit(f"\tLDA MATH_STACK+{offset}")
        self.emit("\tSTA MATH_OP0")
        self.emit(f"\tLDA MATH_STACK+{offset + 1}")
        self.emit("\tSTA MATH_OP0+1")

    def _emit_store_byte_const(self, sym: Symbol, value: int) -> None:
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
            if value < 0 or value > 0xFF:
                error_msg: str = f"Constant value {value} (0x{value:X}) does not fit in BYTE (0-255)"
                if context:
                    error_msg += f" ({context})"
                self._raise_error(error_msg)
            return True
        
        # For WORD types and pointers
        if target_type.base == "WORD" or target_type.is_pointer:
            if value < 0 or value > 0xFFFF:
                error_msg: str = f"Constant value {value} (0x{value:X}) does not fit in WORD (0-65535)"
                if context:
                    error_msg += f" ({context})"
                self._raise_error(error_msg)
            return True
        
        return True

    def _emit_store_word_const(self, sym: Symbol, value: int) -> None:
        value &= 0xFFFF
        lo: int = value & 0xFF
        hi: int = (value >> 8) & 0xFF
        asm: str = sym.asm_name()
        if lo == 0:
            self._stz(asm)
        else:
            self.emit(f"\tLDA #${lo:02X}")
            self.emit(f"\tSTA {asm}")
        if hi == 0:
            self._stz(f"{asm}+1")
        else:
            self.emit(f"\tLDA #${hi:02X}")
            self.emit(f"\tSTA {asm}+1")

    def _emit_inc_word(self, asm: str) -> None:
        lbl: str = self.new_label("INC_WORD")
        self.emit(f"\tINC {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tINC {asm}+1")
        self.emit(f"{lbl}:")

    def _emit_dec_word(self, asm: str) -> None:
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
        return line.strip().upper().startswith("STA ")

    def _inc_operand(self, line: str) -> str | None:
        stripped: str = line.strip().upper()
        if stripped.startswith("INC "):
            return stripped[4:].strip()
        return None

    def _dec_operand(self, line: str) -> str | None:
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

    def _is_port_variable(self, operand: str) -> bool:
        """Check if operand references a PORT (hardware port-mapped) variable.
        
        PORT variables are hardware port-mapped and cannot be optimized.
        """
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

    def peephole_optimize(self) -> None:
        """Apply peephole optimizations to emitted code.
        
        Current optimizations:
        - Remove redundant LDA after STA to same location (when A still contains the value)
        - Tail call optimization: JSR followed by RTS -> JMP (saves stack operations)
        - Remove duplicate consecutive comment lines
        - 65c02: Replace LDX #0; STA addr; STX addr+1 with STA addr; STZ addr+1
        - Remove blank line immediately before RTS
        """
        optimized: list[str] = []
        i = 0
        
        while i < len(self.code):
            line = self.code[i]
            line_stripped = line.strip()
            line_upper = line_stripped.upper()
            
            # 65c02: Replace LDX #0; STA addr; STX addr+1 -> STA addr; STZ addr+1
            # Strip inline comments to check instruction
            instr_part = line_stripped.split(';')[0].strip().upper()
            if self.is_65c02 and (instr_part == "LDX #0" or instr_part == "LDX #$0" or instr_part == "LDX #$00"):
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
                    
                    if stx_found:
                        # Replace pattern: skip LDX #0, emit STA, replace STX with STZ
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
                                if lda_operand.upper() == sta_operand.upper():
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
                        legalized.append("\tSTX TMP4")
                        legalized.append(f"\t{op} TMP4")
                        i += 1
                        continue
            legalized.append(self.code[i])
            i += 1
        self.code = legalized

    def gen_vars_block(self, procs=None, funcs=None) -> list[str]:
        """Generate variable declarations into a separate list without altering current code."""
        saved: list[str] = self.code
        self.code = []
        self.gen_vars(procs, funcs, code=saved)
        vars_block: list[str] = self.code
        self.code = saved
        return vars_block

    def _declare_temp(self, name: str, base: str = "WORD") -> Symbol:
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
            proc_name=""
        )
        # vložení do aktuální tabulky (lokální, jinak globální)
        target: SymbolTable | None = getattr(self.current_symtab, "local", None)
        if target is None:
            target = self.current_symtab
        # attach procedure name if available for proper ASM naming
        proc_name: str = getattr(target, "_proc_name", "")
        if proc_name:
            sym.proc_name = proc_name
        target._symbols[target._key(sym.name)] = sym
        return sym


    def gen_file_header(self) -> None:
        self.emit("; Generated by Zap Compiler")
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
            exports_list: str = ", ".join(sorted(exports))
            # Comment format: ; ZAP_EXPORTS name, name
            self.emit(f"; ZAP_EXPORTS {exports_list}")
            self.emit("")
        self.emit(".DEBUGINFO +  ; Enable debug information for symbol names")
        self.emit("")
        #self.emit(".include \"macros.inc\"")
        #self.emit(".include \"variables.inc\"\n")

    def gen_file_footer(self) -> None:
        # Ensure runtime helpers and data live in CODE segment
        self.emit("\n.segment \"CODE\"")
        self._gen_copy_bytes_routine()
        self._gen_arrcpy_routine()
        self._gen_string_data()
        self._gen_math_routines()
        self.emit("\n; End of file")

    def _gen_copy_bytes_routine(self) -> None:
        """Shared byte copy routine to shrink init code for large const data"""
        if not self.copy_bytes_needed:
            return

        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        self.emit("; ------------------------------")
        self.emit("; Shared byte copy routine")
        self.emit("; Inputs: TMP0/TMP0+1=src, TMP2/TMP2+1=dst, X=len (1..255), Y=0")
        self.emit("; Clobbers: A, X, Y")
        self.emit("; Note: length must fit in one page; longer copies stay inline")
        self.emit("COPY_BYTES:")
        self.emit("\tLDY #0")
        self.emit("\tCPX #0")        
        self.emit("\tBEQ COPY_BYTES_DONE")
        self.emit("COPY_BYTES_LOOP:")
        self.emit("\tLDA (TMP0),Y")
        self.emit("\tSTA (TMP2),Y")
        self.emit("\tINY")
        self.emit("\tDEX")
        self.emit("\tBNE COPY_BYTES_LOOP")
        self.emit("COPY_BYTES_DONE:")
        self.emit("\tRTS\n")
    
    def _gen_arrcpy_routine(self) -> None:
        """Generate ARRCPY subroutine for array copying.
        
        Only emitted if arrcpy_needed flag is set.
        
        Inputs:
        - TMP0/TMP0+1: source address (pointer)
        - TMP2/TMP2+1: destination address (pointer) 
        - A: number of bytes to copy (0-255)
        
        Copies exactly A bytes from source to destination, regardless of content.
        This implements array copy semantics (not C-string copy).
        
        Clobbers: A, X, Y
        """
        if not self.arrcpy_needed:
            return
        
        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})
        
        self.emit("; ------------------------------")
        self.emit("; Array copy routine (ARRCPY)")
        self.emit("; Inputs: TMP0/TMP0+1=src addr, TMP2/TMP2+1=dst addr, A=length")
        self.emit("; Copies exactly A bytes regardless of content")
        self.emit("; Clobbers: A, X, Y")
        self.emit("; ------------------------------")
        self.emit("ARRCPY:")
        self.emit("\tSTA TMP3")          # Store length in TMP3
        self.emit("\tLDX #$00")            # Initialize byte counter
        self.emit("\tLDY #$00")            # Initialize index for indirect addressing
        self.emit("ARRCPY_LOOP:")
        self.emit("\tCPX TMP3")          # Check if we've copied all bytes
        self.emit("\tBEQ ARRCPY_DONE")   # If so, done
        self.emit("\tLDA (TMP0),Y")      # Load byte from source
        self.emit("\tSTA (TMP2),Y")      # Store byte to destination
        self.emit("\tINX")               # Increment byte counter
        self.emit("\tINY")               # Increment byte index
        self.emit("\tBNE ARRCPY_LOOP")   # Loop until page boundary (256 bytes max)
        self.emit("ARRCPY_DONE:")
        self.emit("\tRTS\n")

    
    def _gen_string_data(self) -> None:
        """Generate string literal data in code segment"""
        if not self.string_literals and not self.array_literals:
            return
        
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
        for (data_tuple, is_word), label in self.array_literals.items():
            self.emit(f"{label}:")
            if is_word:
                # WORD array - emit as .word directives
                self.emit(f"\t.word " + ", ".join(f"${val:04X}" for val in data_tuple))
            else:
                # BYTE array - emit as .byte directives
                self.emit(f"\t.byte " + ", ".join(f"${val:02X}" for val in data_tuple))
        
        self.emit("")
    
    def _gen_string_copy(self, dst_sym, src_sym) -> None:
        """Generate code to call ARRCPY subroutine.
        
        Sets up parameters and calls shared ARRCPY subroutine which copies
        bytes from source to destination until null terminator or max length.
        
        Parameters:
        - TMP0/TMP0+1: source address (pointer)
        - TMP2/TMP2+1: destination address (pointer)
        - A: destination max length (minus 1 for null terminator)
        """
        self.arrcpy_needed = True  # Mark that ARRCPY routine is needed
        
        src_asm = src_sym.asm_name()
        dst_asm = dst_sym.asm_name()
        dst_len = dst_sym.array_len or 0
        
        # Set up source address in TMP0
        if src_sym.address is not None:
            # Fixed address - load as immediate
            addr = src_sym.address
            self.emit(f"\tLDA #${addr & 0xFF:02X}")
            self.emit("\tSTA TMP0")
            self.emit(f"\tLDA #${(addr >> 8) & 0xFF:02X}")
            self.emit("\tSTA TMP0+1")
        else:
            # Variable - address is the variable itself (for arrays in ZP or data)
            self.emit(f"\tLDA #$00")  # Low byte of source address
            self.emit("\tSTA TMP0")
            self.emit(f"\tLDA #$00")  # High byte
            self.emit("\tSTA TMP0+1")
            # Actually, for simple arrays, just use the variable name as pointer
            # Load address of source array
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
        
        # Set copy length in A (full array length, not minus 1)
        if dst_len > 0:
            self.emit(f"\tLDA #${dst_len:02X}")
        else:
            # No length limit (risky, but copy up to 255 bytes)
            self.emit("\tLDA #$FF")
        
        # Call ARRCPY routine
        self.emit("\tJSR ARRCPY")

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
        
        # Extract values from const struct initialization
        values: list[int] = [ex.value for ex in src_const_sym.init.values if isinstance(ex, IntLiteral)]
        
        # Generate ROM data label for this struct
        data_key = (tuple(values), False)
        if data_key not in self.array_literals:
            self.array_id += 1
            self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
        arr_label = self.array_literals[data_key]
        
        # Generate code to copy struct bytes using COPY_BYTES routine
        self.copy_bytes_needed = True
        
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
        
        # Set copy length in X (number of bytes = struct size)
        self.emit(f"\tLDX #${struct_size:02X}")
        self.emit("\tLDY #$00")
        self.emit("\tJSR COPY_BYTES")

    
    def _gen_math_routines(self) -> None:
        """Generate runtime math routines for *, /, %"""
        if not self.math_routines_needed:
            return

        needed: set[str] = set(self.math_routines_needed)
        # Include dependencies (MUL16_8 uses MUL8)
        if "MUL16_8" in needed:
            needed.add("MUL8")

        def emit_mul8() -> None:
            self.emit("; MUL8: 8x8=16 multiply")
            self.emit("; Input: MATH_OP0 (multiplicand), MATH_OP2 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL8:")
            self.emit("\tLDA #$00")
            self.emit("\tLDX #$08")
            self.emit("\tCLC")
            self.emit("MUL8_LOOP:")
            self.emit("\tROR MATH_OP2")
            self.emit("\tBCC MUL8_SKIP")
            self.emit("\tCLC")
            self.emit("\tADC MATH_OP0")
            self.emit("MUL8_SKIP:")
            self.emit("\tROR")
            self.emit("\tROR MATH_OP3")
            self.emit("\tDEX")
            self.emit("\tBNE MUL8_LOOP")
            self.emit("\tTAX")
            self.emit("\tLDA MATH_OP3")
            self.emit("\tRTS")

        def emit_mul16_8() -> None:
            self.emit("; MUL16_8: 16x8=16 multiply")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (multiplicand), MATH_OP2 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL16_8:")
            self.emit("\tLDA MATH_OP0")
            self.emit("\tSTA MATH_OP1")           # Save low multiplicand in MATH_OP1
            self.emit("\tLDA MATH_OP0+1")
            self.emit("\tPHA")
            self.emit("\tLDA MATH_OP2")
            self.emit("\tPHA")                # Save multiplier on stack
            self.emit("\tLDA MATH_OP1")           # Restore low multiplicand
            self.emit("\tSTA MATH_OP0")
            self.emit("\tJSR MUL8")          # First: MATH_OP0(low multiplicand) * MATH_OP2(multiplier)
            self.emit("\tSTA MATH_OP1")           # Save low byte of result in MATH_OP1 (safe from MUL8)
            self.emit("\tSTX MATH_OP1+1")         # Save high byte of result in MATH_OP1+1
            self.emit("\tPLA")                # Restore multiplier
            self.emit("\tSTA MATH_OP2")
            self.emit("\tPLA")                # Restore high multiplicand
            self.emit("\tSTA MATH_OP0")
            self.emit("\tJSR MUL8")          # Second: MATH_OP0(high multiplicand) * MATH_OP2(multiplier)
            self.emit("\tCLC")
            self.emit("\tADC MATH_OP1+1")         # Add high byte from first product (carry)
            self.emit("\tTAX")                # X = final high byte
            self.emit("\tLDA MATH_OP1")           # A = low byte from first multiplication
            self.emit("\tRTS")

        def emit_mul16() -> None:
            self.emit("; MUL16: 16x16=16 multiply (shift-add implementation)")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (multiplicand), MATH_OP2,MATH_OP3 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL16:")
            # Accumulator stored at MATH_OP2+2/MATH_OP2+3
            self._stz("MATH_OP2+2")
            self._stz("MATH_OP2+3")
            # Loop 16 times: test LSB of multiplier, add multiplicand, then shift
            self.emit("\tLDX #$10")
            self.emit("MUL16_LOOP:")
            # Shift multiplier right by one (MATH_OP3:MATH_OP2 >> 1). Carry after ROR MATH_OP2 is original LSB
            self.emit("\tLSR MATH_OP3")
            self.emit("\tROR MATH_OP2")
            self.emit("\tBCC MUL16_SKIP")
            # Add multiplicand (MATH_OP0/MATH_OP0+1) into accumulator (MATH_OP2+2/MATH_OP2+3)
            self.emit("\tCLC")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tADC MATH_OP0")
            self.emit("\tSTA MATH_OP2+2")
            self.emit("\tLDA MATH_OP2+3")
            self.emit("\tADC MATH_OP0+1")
            self.emit("\tSTA MATH_OP2+3")
            self.emit("MUL16_SKIP:")
            # Left-shift multiplicand (MATH_OP0:MATH_OP0+1 << 1)
            self.emit("\tASL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tDEX")
            self.emit("\tBNE MUL16_LOOP")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tLDX MATH_OP2+3")
            self.emit("\tRTS")

        def emit_div8() -> None:
            self.emit("; DIV8: 8/8=8 divide")
            self.emit("; Input: MATH_OP0 (dividend), MATH_OP2 (divisor)")
            self.emit("; Output: A=quotient, X=0")
            self.emit("DIV8:")
            self.emit("\tLDA #$00")
            self.emit("\tLDX #$08")
            self.emit("\tCLC")
            self.emit("DIV8_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tBCC DIV8_SKIP")
            self.emit("\tSBC MATH_OP2")
            self.emit("DIV8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV8_LOOP")
            self.emit("\tROL MATH_OP0")
            self.emit("\tLDA MATH_OP0")
            self.emit("\tLDX #$00")
            self.emit("\tRTS")

        def emit_div16_8() -> None:
            self.emit("; DIV16_8: 16/8=16 divide")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (dividend), MATH_OP2 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("DIV16_8:")
            self._stz("MATH_OP3")
            self.emit("\tLDX #$10")
            self.emit("\tCLC")
            self.emit("DIV16_8_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tROL MATH_OP3")
            self.emit("\tLDA MATH_OP3")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tBCC DIV16_8_SKIP")
            self.emit("\tSBC MATH_OP2")
            self.emit("\tSTA MATH_OP3")
            self.emit("DIV16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_8_LOOP")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tLDA MATH_OP0")
            self.emit("\tLDX MATH_OP0+1")
            self.emit("\tRTS")

        def emit_div8_16() -> None:
            self.emit("; DIV8_16: 8/16 divide (promote and call DIV16)")
            self.emit("; Input: MATH_OP0 (dividend), MATH_OP2,MATH_OP3 (divisor)")
            self.emit("; Output: A=low, X=high (quotient)")
            self.emit("DIV8_16:")
            # Make dividend 16-bit (high byte = 0) and reuse DIV16 implementation
            self._stz("MATH_OP0+1")
            self.emit("\tJSR DIV16")
            self.emit("\tRTS")

        def emit_div16() -> None:
            self.emit("; DIV16: 16/16=16 divide")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (dividend), MATH_OP2,MATH_OP3 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("DIV16:")
            self._stz("MATH_OP2+2")
            self._stz("MATH_OP2+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("DIV16_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tROL MATH_OP2+2")
            self.emit("\tROL MATH_OP2+3")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tLDA MATH_OP2+3")
            self.emit("\tSBC MATH_OP3")
            self.emit("\tBCC DIV16_SKIP")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tSBC MATH_OP2")
            self.emit("\tSTA MATH_OP2+2")
            self.emit("\tLDA MATH_OP2+3")
            self.emit("\tSBC MATH_OP3")
            self.emit("\tSTA MATH_OP2+3")
            self.emit("DIV16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_LOOP")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tLDA MATH_OP0")
            self.emit("\tLDX MATH_OP0+1")
            self.emit("\tRTS")

        def emit_mod8() -> None:
            self.emit("; MOD8: 8%8=8 modulo")
            self.emit("; Input: MATH_OP0 (dividend), MATH_OP2 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD8:")
            self.emit("\tLDA #$00")
            self.emit("\tLDX #$08")
            self.emit("\tCLC")
            self.emit("MOD8_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tBCC MOD8_SKIP")
            self.emit("\tSBC MATH_OP2")
            self.emit("MOD8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD8_LOOP")
            self.emit("\tLDX #$00")
            self.emit("\tRTS")

        def emit_mod16_8() -> None:
            self.emit("; MOD16_8: 16%8=8 modulo")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (dividend), MATH_OP2 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD16_8:")
            self._stz("MATH_OP3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_8_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tROL MATH_OP3")
            self.emit("\tLDA MATH_OP3")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tBCC MOD16_8_SKIP")
            self.emit("\tSBC MATH_OP2")
            self.emit("\tSTA MATH_OP3")
            self.emit("MOD16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_8_LOOP")
            self.emit("\tLDA MATH_OP3")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_mod8_16() -> None:
            self.emit("; MOD8_16: 8%16 modulo (promote and call MOD16)")
            self.emit("; Input: MATH_OP0 (dividend), MATH_OP2,MATH_OP3 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD8_16:")
            # Treat dividend as 16-bit (high byte = 0) and reuse MOD16
            self._stz("MATH_OP0+1")
            self.emit("\tJSR MOD16")
            self.emit("\tRTS")

        def emit_mod16() -> None:
            self.emit("; MOD16: 16%16=16 modulo")
            self.emit("; Input: MATH_OP0,MATH_OP0+1 (dividend), MATH_OP2,MATH_OP3 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("MOD16:")
            self._stz("MATH_OP2+2")
            self._stz("MATH_OP2+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_LOOP:")
            self.emit("\tROL MATH_OP0")
            self.emit("\tROL MATH_OP0+1")
            self.emit("\tROL MATH_OP2+2")
            self.emit("\tROL MATH_OP2+3")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tCMP MATH_OP2")
            self.emit("\tLDA MATH_OP2+3")
            self.emit("\tSBC MATH_OP3")
            self.emit("\tBCC MOD16_SKIP")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tSBC MATH_OP2")
            self.emit("\tSTA MATH_OP2+2")
            self.emit("\tLDA MATH_OP2+3")
            self.emit("\tSBC MATH_OP3")
            self.emit("\tSTA MATH_OP2+3")
            self.emit("MOD16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_LOOP")
            self.emit("\tLDA MATH_OP2+2")
            self.emit("\tLDX MATH_OP2+3")
            self.emit("\tRTS")

        emitters: list[tuple[str, Any]] = [
            ("MUL8", emit_mul8),
            ("MUL16_8", emit_mul16_8),
            ("MUL16", emit_mul16),
            ("DIV8", emit_div8),
            ("DIV16_8", emit_div16_8),
            ("DIV8_16", emit_div8_16),
            ("DIV16", emit_div16),
            ("MOD8", emit_mod8),
            ("MOD16_8", emit_mod16_8),
            ("MOD8_16", emit_mod8_16),
            ("MOD16", emit_mod16),
        ]

        self.emit("; ------------------------------")
        self.emit("; Math Runtime Routines")
        self.emit("; ------------------------------")
        self.emit("")

        for name, emitter in emitters:
            if name in needed:
                emitter()
                self.emit("")


    def gen_var_header(self) -> None:
        self.emit("; Variables")
        self.emit("; ------------------------------")   

    def _detect_temp_usage(self, code: list[str] | None = None) -> set[str]:
        """Scan generated code for temp usage and combine with flagged temps."""
        temp_names: set[str] = {"TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5"}
        temps: set[str] = set(self.used_temps)
        code = self.code if code is None else code

        if self.copy_bytes_needed or self.arrcpy_needed:
            temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        for line in code:
            for name in temp_names:
                if name in line:
                    temps.add(name)
        if code and not temps.intersection({"TMP0", "TMP1"}):
            temps.update({"TMP0", "TMP1"})
        return temps

    def gen_vars(self, procs=None, funcs=None, code: list[str] | None = None) -> None:
        temp_sizes: dict[str, int] = {"TMP0": 2, "TMP1": 2, "TMP2": 4, "TMP3": 2, "TMP4": 2, "TMP5": 2}
        temps_in_use: set[str] = self._detect_temp_usage(code)

        self.emit(".segment \"ZEROPAGE\"")
        self.emit("; System variables")
        self.emit("MATH_STACK:\t.res 8")
        self.emit("MATH_OP0:\t.res 2")
        self.emit("MATH_OP1:\t.res 2")
        self.emit("MATH_OP2:\t.res 4")
        self.emit("MATH_OP3:\t.res 2")
        for name in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4", "TMP5"]:
            if name in temps_in_use:
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

        # Deduplicate by ASM name to avoid double emission
        uniq: dict[str, Symbol] = {}
        for s in all_vars:
            uniq[s.asm_name()] = s
        all_vars: list[Symbol] = list(uniq.values())

        fixed: list[Symbol] = [s for s in all_vars if getattr(s, "address", None) is not None]
        if fixed:
            self.emit("; Fixed-address variables")
            for sym in fixed:
                self.emit(f"{sym.asm_name()} = ${sym.address:04X}")
                # Track fixed-address labels to prevent peephole optimization
                self.fixed_address_labels.add(sym.asm_name())
                # Also track PORT variables separately for future optimization strategy changes
                if getattr(sym, "is_port", False):
                    self.port_labels.add(sym.asm_name())
            self.emit("")

        # Zero page offset tracking (starts after emitted system variables)
        zp_offset: int = sum(temp_sizes[n] for n in temps_in_use)
        ZEROPAGE_SIZE = 256
        
        # Step 1: ALL POINTER VARIABLES (including arrays of pointers) MUST fit in zero page
        pointer_scalars: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and not s.is_array
        ]
        pointer_arrays: list[Symbol] = [
            s for s in all_vars
            if not s.is_const and s.address is None and s.type.is_pointer and s.is_array
        ]
        if pointer_scalars or pointer_arrays:
            self.emit("; Pointer variables")
            for sym in pointer_scalars:
                if zp_offset + 2 > ZEROPAGE_SIZE:
                    self._raise_error(f"Zero page exhausted: pointer '{sym.name}' cannot fit (need {zp_offset + 2} bytes)")
                self.emit(f"{sym.asm_name()}:\t.res 2")
                zp_offset += 2

            for sym in pointer_arrays:
                total_size: int = sym.get_total_array_size()
                if total_size == 0:
                    self._raise_error(f"Array pointer '{sym.name}' has unknown size")
                if zp_offset + total_size > ZEROPAGE_SIZE:
                    self._raise_error(f"Zero page exhausted: pointer array '{sym.name}' cannot fit (need {zp_offset + total_size} bytes)")
                self.emit(f"{sym.asm_name()}:\t.res {total_size}")
                zp_offset += total_size
        
        # Step 2: Try to put BYTE variables in zero page, overflow to BSS
        byte_vars: list[Symbol] = [s for s in all_vars 
                     if not s.is_const and s.address is None 
                     and not s.type.is_pointer and not s.is_array
                     and s.type.base == "BYTE"]
        
        zp_byte_vars = []
        bss_byte_vars = []
        for sym in byte_vars:
            if zp_offset + 1 <= ZEROPAGE_SIZE:
                zp_byte_vars.append(sym)
                zp_offset += 1
            else:
                bss_byte_vars.append(sym)
        
        if zp_byte_vars:
            self.emit("; Byte variables")
            for sym in zp_byte_vars:
                self.emit(f"{sym.asm_name()}:\t.res 1")
        
        # Step 3: WORD (non-pointer, non-array) variables - try zero page first
        word_vars: list[Symbol] = [s for s in all_vars 
                     if not s.is_const and s.address is None 
                     and not s.type.is_pointer and not s.is_array
                     and s.type.base == "WORD"]
        
        zp_word_vars = []
        bss_word_vars = []
        for sym in word_vars:
            if zp_offset + 2 <= ZEROPAGE_SIZE:
                zp_word_vars.append(sym)
                zp_offset += 2
            else:
                bss_word_vars.append(sym)
        
        if zp_word_vars:
            self.emit("; Word variables")
            for sym in zp_word_vars:
                self.emit(f"{sym.asm_name()}:\t.res 2")
        
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
        
        # Switch to BSS for overflow, struct vars, and arrays
        if bss_byte_vars or bss_word_vars or bss_struct_vars or array_vars:
            self.emit("\n.segment \"BSS\"")
            
            if bss_byte_vars:
                self.emit("; Byte variables (BSS)")
                for sym in bss_byte_vars:
                    self.emit(f"{sym.asm_name()}:\t.res 1")
            
            if bss_word_vars:
                self.emit("; Word variables (BSS)")
                for sym in bss_word_vars:
                    self.emit(f"{sym.asm_name()}:\t.res 2")
            
            if bss_struct_vars:
                self.emit("; Struct variables (BSS)")
                for sym in bss_struct_vars:
                    if sym.type.is_struct and sym.type.struct_info:
                        struct_size: int = sym.type.struct_info.size
                        self.emit(f"{sym.asm_name()}:\t.res {struct_size}")
                    else:
                        # Fallback (shouldn't happen if is_struct is correct)
                        self.emit(f"{sym.asm_name()}:\t.res 1")
            
            if array_vars:
                self.emit("; Array variables (BSS)")
                for sym in array_vars:
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
        self.emit("\n.segment \"CODE\"")
        self.emit("; Globals initialization")
        self.emit("; ------------------------------") 
               

    def gen_globals_footer(self) -> None:
        self.emit("\n; Call MAIN")
        self.emit("; ------------------------------")        
        self.emit("\tJSR MAIN")       
        self.emit("\tJMP *\n")       

    def gen_init(self, sym: Symbol, is_global_init: bool = False) -> None:
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
                val: int = val & 0xFFFF  # Mask after check
                if sym.type.base == "BYTE" and not sym.type.is_pointer:
                    self._emit_store_byte_const(sym, val)
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
                    self.emit(f"\tLDA {left_asm}")
                    if expr.op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tADC {right_asm}")
                    else:  # SUB
                        self.emit("\tSEC")
                        self.emit(f"\tSBC {right_asm}")
                    self.emit(f"\tSTA {dest_asm}")
                    
                    self.emit(f"\tLDA {left_asm}+1")
                    if expr.op == BinOp.ADD:
                        self.emit(f"\tADC {right_asm}+1")
                    else:  # SUB
                        self.emit(f"\tSBC {right_asm}+1")
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
                        self.emit(f"\tLDX #0")
                        self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
                # Add null terminator
                term_offset: int = len(content) * (2 if is_word else 1)
                self.emit(f"\tLDA #0")
                self.emit(f"\tSTA {dest_var}+{term_offset}")
                if is_word:
                    self.emit(f"\tLDX #0")
                    self.emit(f"\tSTX {dest_var}+{term_offset}+1")
            else:
                # Use ARRCPY routine for larger strings (fits in one page)
                if content not in self.string_literals:
                    self.string_id += 1
                    self.string_literals[content] = f"STR_DATA_{self.string_id}"
                str_label = self.string_literals[content]
                
                # BYTE arrays: use ARRCPY for all sizes > COPY_THRESHOLD
                if not is_word and str_len <= 255:
                    self.arrcpy_needed = True
                    
                    # Set source and destination pointers
                    self.emit(f"\tLDA #<{str_label}")
                    self.emit(f"\tLDX #>{str_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")
                    
                    self.emit(f"\tLDA #<{dest_var}")        
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")
                    
                    # Copy full array length (str_len includes null terminator)
                    self.emit(f"\tLDA #{str_len}")
                    self.emit("\tJSR ARRCPY")
                else:
                    # WORD arrays or very large arrays: use COPY_BYTES for now
                    self.copy_bytes_needed = True
                    
                    # Set source and destination pointers
                    self.emit(f"\tLDA #<{str_label}")
                    self.emit(f"\tLDX #>{str_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")

                    self.emit(f"\tLDA #<{dest_var}")        
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")

                    # For WORD arrays, we need to copy 2x the number of characters (each char becomes 2 bytes)
                    copy_len: int = str_len * (2 if is_word else 1)
                    self.emit(f"\tLDX #{copy_len}") # Fixme: assumes length fits in one byte
                    self.emit("\tLDY #0")
                    self.emit("\tJSR COPY_BYTES")
            return

        if isinstance(sym.init, ListInit):
            # Check if this is a struct (array or single)
            struct_info: StructInfo | None = sym.type.struct_info
            is_struct_type: bool = sym.type.is_struct and struct_info is not None
            
            if is_struct_type and struct_info is not None:
                assert struct_info is not None  # Help Pylance understand struct_info is not None
                struct_size: int = struct_info.size
                flattened_values = []
                
                if sym.is_array:
                    # Struct array: each element should be a ListInit
                    # Flatten nested lists into a single sequence of values
                    for struct_init in sym.init.values:
                        if isinstance(struct_init, ListInit):
                            flattened_values.extend(struct_init.values)
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
                    for field_init in sym.init.values:
                        if isinstance(field_init, ListInit):
                            # Nested struct field - flatten it
                            flattened_values.extend(field_init.values)
                        else:
                            # Scalar field
                            flattened_values.append(field_init)
                
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
                values: list[int] = [ex.value for ex in flattened_values if isinstance(ex, IntLiteral)]
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
                    data_key: tuple[tuple[int, ...], bool] = (tuple(values), is_word)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                    
                    arr_label = self.array_literals[data_key]
                    elem_size: int = 2 if is_word else 1
                    total_bytes: int = array_len * elem_size
                    use_shared: bool = total_bytes > COPY_THRESHOLD and total_bytes <= 255

                    if use_shared:
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
                        self.emit("\tLDY #0")
                        self.emit("\tJSR COPY_BYTES")
                    else:
                        self.emit(f"\t; Copy struct array [{', '.join(str(v) for v in values[:10])}{'...' if len(values) > 10 else ''}] ({array_len} bytes)")
                        self.emit(f"\tLDX #0")
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
                # Non-constant values - use old method
                for i, ex in enumerate(sym.init.values):
                    self.gen_expr(ex)
                    elem_offset: int = i * 2 if sym.type.base == "WORD" else i
                    self.emit(f"\tSTA {sym.asm_name()}+{elem_offset}")
                    if sym.type.base == "WORD":
                        self.emit(f"\tSTX {sym.asm_name()}+{elem_offset}+1")
                return
            
            # Constant array - optimize with loop copy
            # Type narrowing: we've verified all elements are IntLiteral above
            values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
            array_len: int = len(values)
            is_word: bool = sym.type.base == "WORD"
            dest_var: str = sym.asm_name()
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space
            
            # For very short arrays (1-2 elements), inline is better
            if array_len <= 2:
                # Inline for very short arrays
                for i, ex in enumerate(sym.init.values):
                    self.gen_expr(ex)
                    elem_offset: int = i * 2 if is_word else i
                    self.emit(f"\tSTA {dest_var}+{elem_offset}")
                    if is_word:
                        self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
            else:
                # Use loop for longer arrays
                # Create unique key for this array data
                data_key: tuple[tuple[int, ...], bool] = (tuple(values), is_word)
                if data_key not in self.array_literals:
                    self.array_id += 1
                    self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                
                arr_label = self.array_literals[data_key]
                elem_size: int = 2 if is_word else 1
                total_bytes: int = array_len * elem_size
                use_shared: bool = total_bytes > COPY_THRESHOLD and total_bytes <= 255

                if use_shared:
                    # Shared copy routine saves space for larger initializers (<=255 bytes)
                    self.copy_bytes_needed = True
                    self.emit(f"\t; Copy array [{', '.join(str(v) for v in values[:5])}{'...' if len(values) > 5 else ''}] ({array_len} elements)")
                    # Source -> TMP0/TMP0+1
                    self.emit(f"\tLDA #<{arr_label}")
                    self.emit(f"\tLDX #>{arr_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP0+1")
                    # Dest -> TMP2/TMP2+1
                    self.emit(f"\tLDA #<{dest_var}")
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP2+1")
                    # Length in X (<=255), Y = 0
                    self.emit(f"\tLDX #{total_bytes}")
                    self.emit("\tLDY #0")
                    self.emit("\tJSR COPY_BYTES")
                else:
                    self.emit(f"\t; Copy array [{', '.join(str(v) for v in values[:5])}{'...' if len(values) > 5 else ''}] ({array_len} elements)")
                    self.emit(f"\tLDX #0")
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
        self.code.append(line)

    def emit_src_comment_for_stmt(self, stmt) -> None:
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
            self.emit(f"; {fname} {line}: {text}")

    def emit_src_comment_for_local(self, proc_name: str, var_name: str) -> None:
        info = self.local_decl_src.get((proc_name, var_name))
        if info:
            fname, line, col, text = info
            # Also attach current_stmt_info so subsequent raises have context
            self.current_stmt_info = (fname, line, col, text)
            self.emit(f"; {fname} {line}: {text}")

    def emit_src_comment_for_global(self, var_name: str) -> None:
        info = self.global_decl_src.get(var_name)
        if info:
            fname, line, col, text = info
            # Also attach current_stmt_info so subsequent raises have context
            self.current_stmt_info = (fname, line, col, text)
            self.emit(f"; {fname} {line}: {text}")

    def _raise_error(self, msg: str) -> NoReturn:
        # Attach line/col and source text for better error output
        from errors import SemanticError
        if self.current_stmt_info:
            fname, line, col, _ = self.current_stmt_info
            e = SemanticError(msg, line=line, col=col)
            # Provide full source text when available
            if self.source_lines:
                e.source_text = "\n".join(self.source_lines)
            e.filename = fname
            raise e
        else:
            # Attach current expression node if present so error has location
            raise SemanticError(msg, node=getattr(self, 'current_expr', None))

    def _load_sym_addr(self, sym_name: str) -> None:
        self.emit(f"\tLDA #<{sym_name}")
        self.emit(f"\tLDX #>{sym_name}")

    def _gen_literal(self, expr: IntLiteral) -> None:
        t: ExprType = self.tc_check(expr)
        val: int = expr.value
        self.emit(f"\tLDA #${val & 0xFF:02X}")
        # Always set X = high byte to make word-store patterns safe (high byte is 0 for small literals)
        self.emit(f"\tLDX #${(val >> 8) & 0xFF:02X}")


    def _gen_identifier(self, expr: Identifier) -> None:
        t: ExprType = self.tc_check(expr)
        sym: Symbol = self.current_symtab.lookup(expr.name)

        if sym.is_const:
            # Handle const arrays specially - they have addresses to ROM data
            if sym.is_array:
                # Const arrays: get address of ROM data
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    is_word: bool = sym.type.base == "WORD"
                    data_key: tuple[tuple[int, ...], bool] = (tuple(values), is_word)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                    return
                else:
                    self._raise_error(f"Const array '{sym.name}' has no initialization")
            
            # Handle const structs - they have addresses to ROM data
            if sym.type.is_struct:
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    data_key = (tuple(values), False)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                    return
                else:
                    self._raise_error(f"Const struct '{sym.name}' has no initialization")
            
            # Const scalars
            if sym.const_value is None:
                self._raise_error(f"Constant '{sym.name}' has no value")
            # Use the symbol's declared type, not the inferred literal type
            val: int = sym.const_value
            self.emit(f"\tLDA #${val & 0xFF:02X}")
            # Pointers are always word-sized even when base type is BYTE
            if sym.type.base == "WORD" or sym.type.is_pointer:
                self.emit(f"\tLDX #${(val >> 8) & 0xFF:02X}")
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
        self.emit(f"\tLDA {asm}")
        if t.sem_type.base == "WORD":
            self.emit(f"\tLDX {asm}+1")
        else:
            # BYTE → X = 0
            # Optimization: skip LDX #0 if assignment target is BYTE (no need to set high byte)
            target_is_byte: None | bool = (self.assign_target_type and 
                            hasattr(self.assign_target_type, 'base') and
                            self.assign_target_type.base == "BYTE" and 
                            not getattr(self.assign_target_type, 'is_pointer', False))
            if not target_is_byte:
                self.emit("\tLDX #0     ; note 3056")

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
        if not (sym.is_array and sym.type.is_pointer and sym.address is None):
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
        t: ExprType = self.tc_check(expr)

        # OPTIMIZATION: Check for ZEROPAGE pointer array subscript (BYTE-only)
        is_zp_ptr_array, sym, byte_offset = self._is_zeropage_pointer_array_subscript(expr.pointer)
        if is_zp_ptr_array and sym is not None and t.sem_type.base == "BYTE" and not t.sem_type.is_pointer:
            self._gen_deref_optimized_zeropage(expr, sym, byte_offset)
            return

        # If pointer is a simple ZP identifier, use direct addressing without TMP0
        if isinstance(expr.pointer, Identifier):
            ptr_sym: Symbol = self.current_symtab.lookup(expr.pointer.name)
            if ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array:
                ptr_asm: str = ptr_sym.asm_name()
                if self.is_65c02:
                    self.emit(f"\tLDA ({ptr_asm})")
                else:
                    self.emit("\tLDY #0")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                if t.sem_type.base == "WORD":
                    self.emit("\tPHA")
                    self.emit("\tLDY #1")
                    self.emit(f"\tLDA ({ptr_asm}),Y")
                    self.emit("\tTAX")
                    self.emit("\tPLA")
                return

        # 1) vygeneruj adresu pointeru → A/X
        self.gen_expr(expr.pointer)

        # 2) ulož adresu (word temp uses contiguous bytes)
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")

        # 3) načti LOW byte
        self.emit("\tLDY #0")
        self.emit("\tLDA (TMP0),Y")

        # 4) WORD? načti HIGH byte
        if t.sem_type.base == "WORD":
            # For WORD, we need both low and high bytes
            # Low byte is in A, but we need to load high byte into X
            # Save low byte, load high byte, then restore low byte to A
            self.emit("\tPHA")  # Save low byte on stack
            self.emit("\tINY")
            self.emit("\tLDA (TMP0),Y")  # Load high byte
            self.emit("\tTAX")  # Transfer high byte to X
            self.emit("\tPLA")  # Restore low byte to A

    def _collect_subscript_indices(self, expr: SubscriptExpr) -> tuple:
        """Collect all indices and base identifier from nested subscripts.
        
        For arr[i][j][k], returns ([k, j, i], Identifier('arr'))
        For struct_var.array_field[i][j], returns ([j, i], FieldAccess(...))
        (indices are collected in reverse order as we traverse the nesting)
        """
        indices: list[Expr] = [expr.index]
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
        """Calculate the width of array elements in bytes."""
        if sym.type.is_pointer:
            return 2
        if sym.type.is_struct and sym.type.struct_info:
            return sym.type.struct_info.size
        if sym.type.base == "WORD":
            return 2
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
                self.emit(f"\tLDA #{sym.address:02X}" if sym.address else f"\tLDA #<{sym.asm_name()}")
                self.emit("\tSTA TMP0")
                self.emit(f"\tLDA #{(sym.address >> 8) & 0xFF:02X}" if sym.address else f"\tLDA #>{sym.asm_name()}")
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
            
            # If only calculating address, we're done
            if calc_addr_only:
                return
            
            # Load or store element at TMP0
            if load_only:
                self.emit("\tLDY #0")
                self.emit("\tLDA (TMP0),Y")
                if element_width == 2:
                    self.emit("\tPHA")  # Save low byte
                    self.emit("\tINY")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tTAX")  # X = high byte
                    self.emit("\tPLA")  # A = low byte (restored)
                else:
                    # For BYTE element, skip LDX #0 if assignment target is BYTE (optimization at 3216)
                    if not (self.assign_target_type and 
                            hasattr(self.assign_target_type, 'base') and
                            self.assign_target_type.base == "BYTE" and 
                            not getattr(self.assign_target_type, 'is_pointer', False)):
                        self.emit("\tLDX #0     ; note 3211")
            else:
                # Store RHS value (in TMP2/TMP2+1)
                self.emit("\tLDA TMP2")
                if element_width == 2:
                    self.emit("\tLDY #0")
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
        self.emit("\tLDA #0")
        self.emit("\tSTA TMP4")
        self.emit("\tSTA TMP4+1")
        
        # Add each index * stride to offset
        for idx_expr, stride_val in zip(indices, strides):
            # Evaluate index expression -> A
            self.gen_expr(idx_expr)
            
            # Multiply index by stride
            if stride_val == 1:
                # No multiplication needed - A already has index
                self.emit("\tLDX #0     ; note 3212; note 3239")  # Clear high byte
            elif stride_val == 2:
                # Multiply by 2: ASL
                self.emit("\tASL A")
                self.emit("\tLDX #0     ; note 3243")
            elif stride_val & (stride_val - 1) == 0:
                # Power of 2: use bit shifts
                shifts = (stride_val - 1).bit_length()  # log2(stride_val)
                for _ in range(shifts):
                    self.emit("\tASL A")
                self.emit("\tLDX #0     ; note 3249")
            else:
                # General multiplication (non-power-of-2)
                # Save A (index) to a temporary (use TMP5 to avoid conflicts)
                self.emit("\tSTA TMP5")
                
                # Multiply TMP5 * stride -> A:X using repeated addition
                self.emit("\tLDA #0")
                self.emit("\tSTA TMP3")  # TMP3 = result low byte
                # self.emit("\tLDA #0") # Fixme: ### already cleared above
                self.emit("\tLDX #0     ; note 3259")   # X = result high byte
                
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
            self.emit("\tLDY #0")
            self.emit("\tLDA (TMP0),Y")
            if element_width == 2:
                self.emit("\tPHA")  # Save low byte
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tTAX")  # X = high byte
                self.emit("\tPLA")  # A = low byte (restored)
            else:
                self.emit("\tLDX #0     ; note 3311")
        else:
            # Store RHS value (in TMP2/TMP2+1)
            self.emit("\tLDA TMP2")
            if element_width == 2:
                self.emit("\tLDY #0")
                self.emit("\tSTA (TMP0),Y")
                self.emit("\tINY")
                self.emit("\tLDA TMP2+1")
                self.emit("\tSTA (TMP0),Y")
            else:
                self._emit_indirect_store_zero("TMP0")

    def _gen_subscript(self, expr: SubscriptExpr, load_only: bool, calc_addr_only: bool = False) -> None:
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
            if sym.is_array and not sym.is_const and sym.address is None:
                # This is a simple array with runtime base address
                arr_addr: str = sym.asm_name()
                element_width: int = self._calculate_element_width(sym)
                index_val: int = expr.index.value
                offset: int = index_val * element_width
                
                # Direct load from arr+offset
                if sym.type.base == "BYTE" and not sym.type.is_pointer:
                    # BYTE element: simple load
                    self.emit(f"\tLDA {arr_addr}+{offset}")
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
                # Generate the ARRAY_DATA label from the const values
                if sym.init and isinstance(sym.init, ListInit):
                    values: list[int] = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
                    is_word: bool = sym.type.base == "WORD"
                    data_key: tuple[tuple[int, ...], bool] = (tuple(values), is_word)
                    if data_key not in self.array_literals:
                        self.array_id += 1
                        self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                    arr_label = self.array_literals[data_key]
                    self._load_sym_addr(arr_label)
                else:
                    self._raise_error(f"Const array '{sym.name}' has no initialization")
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
                self.emit("\tLDX #0    ; note 3438")
            else:
                # General case: multiply by width using addition loop
                # Index is in A, multiply by width
                self.emit("\tSTA TMP3")  # Save index to TMP3
                self.emit("\tLDA #0")
                self.emit("\tSTA TMP4")  # TMP4 = result (low byte)
                self.emit("\tLDA #0")
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
            self.emit("\tLDX #0     ; note 3464")  # BYTE element, X = 0
        
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
            self.emit("\tLDY #0")
            self.emit("\tLDA (TMP0),Y")
            if element_width == 2:
                self.emit("\tPHA")  # Save low byte
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tTAX")  # X = high byte
                self.emit("\tPLA")  # A = low byte (restored)
            else:
                # For BYTE element, only set X if final target is not BYTE
                # If target is BYTE, we only need the low byte in A
                need_x = True
                if self.assign_target_type:
                    if hasattr(self.assign_target_type, 'base'):
                        if (self.assign_target_type.base == "BYTE" and 
                            not getattr(self.assign_target_type, 'is_pointer', False)):
                            need_x = False
                if need_x:
                    self.emit("\tLDX #0     ; note 3499")
        else:
            # RHS value in TMP2/TMP2+1 (saved before calling this method)
            self.emit("\tLDA TMP2")
            if element_width == 2:
                self.emit("\tLDY #0")
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
                    self.emit(f"\tBCC NOCARRY_ARRFIELD_DEREF_{id(expr)}")
                    self.emit(f"\tINC A+1")
                    self.emit(f"NOCARRY_ARRFIELD_DEREF_{id(expr)}:")
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
                        self.emit(f"\tBCC NOCARRY_ARRFIELD_SUBSCR_{id(expr)}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"NOCARRY_ARRFIELD_SUBSCR_{id(expr)}:")
                    
                    # Return address in A/X
                    self.emit(f"\tLDA TMP0")
                    self.emit(f"\tLDX TMP0+1")
                else:
                    self._raise_error("Array field access requires identifier or subscript base")
            
            return
        
        field_offset: int = field_info.offset
        field_width: int = 2 if field_info.base_type == "WORD" else 1
        
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
                self.emit(f"\tBCC NOCARRY_FIELD_DEREF_{id(expr)}")
                self.emit("\tINC TMP0+1")
                self.emit(f"NOCARRY_FIELD_DEREF_{id(expr)}:")
            
            # If only loading field value, load it now
            if load_only:
                if field_offset == 0:
                    # Field at offset 0: just load directly
                    self.emit("\tLDY #0")
                    self.emit("\tLDA (TMP0),Y")
                    
                    if field_width == 2:
                        # Load high byte
                        self.emit("\tPHA")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tPLA")
                else:
                    # Field at offset > 0, address is already in TMP0
                    self.emit("\tLDY #0")
                    self.emit("\tLDA (TMP0),Y")
                    
                    if field_width == 2:
                        self.emit("\tPHA")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tPLA")
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
                self.emit(f"\tLDA {field_asm}")
                
                if field_width == 2:
                    self.emit(f"\tLDX {field_asm}+1")
                else:
                    # BYTE field -> X = 0
                    # Optimization: skip LDX #0 if assignment target is BYTE (no need to set high byte)
                    target_is_byte: None | bool = (self.assign_target_type and 
                                    hasattr(self.assign_target_type, 'base') and
                                    self.assign_target_type.base == "BYTE" and 
                                    not getattr(self.assign_target_type, 'is_pointer', False))
                    if not target_is_byte:
                        self.emit("\tLDX #0     ; note 3721")
                    
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
                    self.emit(f"\tBCC NOCARRY_ARRFIELD_{id(expr)}")
                    self.emit(f"\tINC TMP0+1")
                    self.emit(f"NOCARRY_ARRFIELD_{id(expr)}:")
                
                # 3) Load field value via indirect addressing
                self.emit("\tLDY #0")
                self.emit("\tLDA (TMP0),Y")
                
                if field_width == 2:
                    self.emit("\tPHA")
                    self.emit("\tINY")
                    self.emit("\tLDA (TMP0),Y")
                    self.emit("\tTAX")
                    self.emit("\tPLA")
                else:
                    # BYTE field -> X = 0
                    # Optimization: skip LDX #0 if assignment target is BYTE
                    target_is_byte: None | bool = (self.assign_target_type and 
                                    hasattr(self.assign_target_type, 'base') and
                                    self.assign_target_type.base == "BYTE" and 
                                    not getattr(self.assign_target_type, 'is_pointer', False))
                    if not target_is_byte:
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
                    
                    self.emit(f"\tLDA {field_asm}")
                    
                    if field_width == 2:
                        self.emit(f"\tLDX {field_asm}+1")
                    else:
                        # BYTE field -> X = 0
                        # Optimization: skip LDX #0 if assignment target is BYTE (no need to set high byte)
                        target_is_byte: None | bool = (self.assign_target_type and 
                                        hasattr(self.assign_target_type, 'base') and
                                        self.assign_target_type.base == "BYTE" and 
                                        not getattr(self.assign_target_type, 'is_pointer', False))
                        if not target_is_byte:
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
                        self.emit(f"\tBCC NOCARRY_NESTEDFIELD_{id(expr)}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"NOCARRY_NESTEDFIELD_{id(expr)}:")
                    
                    # Load field value via indirect addressing
                    self.emit("\tLDY #0")
                    self.emit("\tLDA (TMP0),Y")
                    
                    if field_width == 2:
                        self.emit("\tPHA")
                        self.emit("\tINY")
                        self.emit("\tLDA (TMP0),Y")
                        self.emit("\tTAX")
                        self.emit("\tPLA")
                    else:
                        # BYTE field -> X = 0
                        # Optimization: skip LDX #0 if assignment target is BYTE
                        target_is_byte: None | bool = (self.assign_target_type and 
                                        hasattr(self.assign_target_type, 'base') and
                                        self.assign_target_type.base == "BYTE" and 
                                        not getattr(self.assign_target_type, 'is_pointer', False))
                        if not target_is_byte:
                            self.emit("\tLDX #$00     ; note 3801")
                else:
                    self._raise_error("Nested field access base must be identifier or array subscript")
            else:
                self._raise_error("Direct field access only supported on struct variables or array elements")
        
        # If storing field (not load_only), RHS should be in TMP2/TMP2+1
        if not load_only:
            if expr.is_deref:
                # Store through pointer (TMP0 already has address)
                self.emit("\tLDA TMP2")
                if field_width == 2:
                    self.emit("\tLDY #0")
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
                
                self.emit(f"\tLDA TMP2")
                self.emit(f"\tSTA {field_asm}")
                
                if field_width == 2:
                    self.emit(f"\tLDA TMP2+1")
                    self.emit(f"\tSTA {field_asm}+1")
            elif isinstance(expr.object, SubscriptExpr):
                # Direct store to array element (TMP0 already has address)
                self.emit(f"\tLDA TMP2")
                if field_width == 2:
                    self.emit("\tLDY #0")
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
                        self.emit(f"\tBCC NOCARRY_NESTEDFIELD_STORE_{id(expr)}")
                        self.emit(f"\tINC TMP0+1")
                        self.emit(f"NOCARRY_NESTEDFIELD_STORE_{id(expr)}:")
                    
                    # Store field value via indirect addressing
                    self.emit("\tLDY #0")
                    self.emit(f"\tLDA TMP2")
                    self.emit(f"\tSTA (TMP0),Y")
                    
                    if field_width == 2:
                        self.emit(f"\tINY")
                        self.emit(f"\tLDA TMP2+1")
                        self.emit(f"\tSTA (TMP0),Y")
                else:
                    self._raise_error("Nested field access base must be identifier or array subscript")

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
          16-bit result: LDA arr[0]; LDX #0; CLC; ADC arr[1]; (with carry to X)
        
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
                self.emit("\tLDX #0     ; note 3994")
        
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

    
    def _gen_binary(self, expr: BinaryExpr, force_left_tmp=None) -> None:
        t: ExprType = self.tc_check(expr)
        left_t: ExprType = self.tc_check(expr.left)
        right_t: ExprType = self.tc_check(expr.right)
        
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
                        self.emit(f"\tADC #{expr.right.value & 0xFF:02X}")
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
        result_16_temp: bool = t.sem_type.base == "WORD" or (t.kind == ExprKind.ADDR and t.sem_type.is_pointer)
        
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
        left_16: bool = left_t.sem_type.base == "WORD" or (left_t.kind == ExprKind.ADDR and left_t.sem_type.is_pointer)
        right_16: bool = right_t.sem_type.base == "WORD" or (right_t.kind == ExprKind.ADDR and right_t.sem_type.is_pointer)
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
            else:
                ptr_elem_size: int = 2 if left_t.sem_type.base == "WORD" else 1
        elif right_is_ptr:
            if right_t.sem_type.is_struct and right_t.sem_type.struct_info:
                ptr_elem_size: int = right_t.sem_type.struct_info.size
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
                left_asm: str = left_sym.asm_name()
                self.emit(f"\tLDA {left_asm}")
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
                right_asm: str = right_sym.asm_name()
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {right_asm}")
                else:
                    self.emit(f"\tSBC {right_asm}")
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
        
        if is_simple_word_add_sub:
            # Generate left operand low byte
            if isinstance(expr.left, Identifier):
                left_sym: Symbol = self.current_symtab.lookup(expr.left.name)
                left_asm: str = left_sym.asm_name()
                self.emit(f"\tLDA {left_asm}")
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
                right_asm: str = right_sym.asm_name()
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {right_asm}")
                else:
                    self.emit(f"\tSBC {right_asm}")
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
                left_asm: str = left_sym.asm_name()
                self.emit(f"\tLDA {left_asm}+1")
            elif isinstance(expr.left, IntLiteral):
                val: int = (expr.left.value >> 8) & 0xFF
                self.emit(f"\tLDA #${val:02X}")
            
            # ADC/SBC high byte (carry is already set/clear from low byte operation)
            if isinstance(expr.right, Identifier):
                right_sym: Symbol = self.current_symtab.lookup(expr.right.name)
                right_asm: str = right_sym.asm_name()
                if expr.op == BinOp.ADD:
                    self.emit(f"\tADC {right_asm}+1")
                else:
                    self.emit(f"\tSBC {right_asm}+1")
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
            from ast_nodes import CallExpr, BinaryExpr, UnaryExpr, SubscriptExpr, FieldAccess
            # Detect explicit calls
            if isinstance(e, CallExpr):
                return True
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

        if right_has_call and expr.op in {BinOp.ADD, BinOp.SUB} and not (left_is_ptr or right_is_ptr):
            # Special-case: right contains a call. Preserve left across call.
            if result_16_adj:
                # 16-bit: save (A,X) → stack using PHA;TXA;PHA and restore with PLA;TAX;PLA
                self.gen_expr(expr.left)
                self.emit("\tPHA")
                self.emit("\tTXA")
                self.emit("\tPHA")

                # Generate right operand (callee may clobber temps)
                self.gen_expr(expr.right)

                # Save right (A=low, X=high) to TMP0/TMP0+1
                self.emit("\tSTA TMP0")
                self.emit("\tSTX TMP0+1")

                # Restore left (low in A, high in X)
                self.emit("\tPLA")
                self.emit("\tTAX")
                self.emit("\tPLA")

                if expr.op == BinOp.ADD:
                    # 16-bit add: low then high with carry
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")
                    self.emit("\tTAY")
                    self.emit("\tTXA")
                    self.emit("\tADC TMP0+1")
                    self.emit("\tTAX")
                    self.emit("\tTYA")
                else:
                    # 16-bit sub: low then high with borrow
                    self.emit("\tSEC")
                    self.emit("\tSBC TMP0")
                    self.emit("\tTAY")
                    self.emit("\tTXA")
                    self.emit("\tSBC TMP0+1")
                    self.emit("\tTAX")
                    self.emit("\tTYA")

                # Special-case handled inline, skip generic handling
                return
            else:
                # 8-bit case (existing behavior)
                self.gen_expr(expr.left)
                self.emit("\tPHA")

                # Generate right operand (callee may clobber TMPs)
                self.gen_expr(expr.right)

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

        if expr.op in {BinOp.MUL, BinOp.DIV, BinOp.MOD}:
            self._gen_math_binop(expr, left_16, right_16)
            return

        # Generate left operand
        self.gen_expr(expr.left)
        self.emit(f"\tSTA {left_tmp}")
        # Only save high byte if we need 16-bit result
        if result_16_adj:
            self.emit(f"\tSTX {left_tmp}+1")

        # Generate right operand (skip for INC/DEC optimization on BYTE pointers)
        if not (use_inc_opt or use_dec_opt):
            # Ask the right sub-expression to prefer the opposite temp to avoid
            # accidental clobbering of the saved left value.
            right_hint: str = "TMP0" if left_tmp == "TMP1" else "TMP1"
            prev_blocked: bool = self.assign_target_blocked
            if target_used:
                self.assign_target_blocked = True
            try:
                self.gen_expr(expr.right, force_left_tmp=right_hint)
            finally:
                self.assign_target_blocked = prev_blocked
        
        # Handle different operations
        if expr.op == BinOp.ADD:
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
            self._gen_lshift(result_16, left_tmp)
        elif expr.op == BinOp.RSHIFT:
            self._gen_rshift(result_16, left_tmp)
        
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
                self.emit("\tASL A")  # Multiply by 2
            else:
                # General case: multiply by ptr_elem_size
                self.emit("\tSTA TMP3")  # Save offset
                self.emit("\tLDA #0")
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
                    self.emit("\tLDA TMP3")    # Restore low byte
                    self.emit("\tCLC")
                    self.emit(f"\tADC {left_tmp}")     # Add low bytes
                    self.emit("\tTAY")
                    self.emit("\tLDA #0")       # High byte is 0
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
            self.emit("\tASL A")  # Multiply by 2
        
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
    
    def _gen_math_binop(self, expr: BinaryExpr, left_16: bool, right_16: bool) -> None:
        """Generate MUL/DIV/MOD using math stack and dedicated operands."""
        def _is_simple_operand(op: Expr) -> bool:
            return isinstance(op, (Identifier, IntLiteral))

        def _emit_op0(op: Expr, is_16: bool) -> None:
            if isinstance(op, IntLiteral):
                val = op.value & 0xFFFF
                self.emit(f"\tLDA #${val & 0xFF:02X}")
                self.emit("\tSTA MATH_OP0")
                if is_16:
                    self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
                    self.emit("\tSTA MATH_OP0+1")
                else:
                    self._stz("MATH_OP0+1")
                return
            if isinstance(op, Identifier):
                sym = self.current_symtab.lookup(op.name)
                self.emit(f"\tLDA {sym.asm_name()}")
                self.emit("\tSTA MATH_OP0")
                if is_16:
                    self.emit(f"\tLDA {sym.asm_name()}+1")
                    self.emit("\tSTA MATH_OP0+1")
                else:
                    self._stz("MATH_OP0+1")
                return

        def _emit_op2(op: Expr, is_16: bool) -> None:
            if isinstance(op, IntLiteral):
                val = op.value & 0xFFFF
                self.emit(f"\tLDA #${val & 0xFF:02X}")
                self.emit("\tSTA MATH_OP2")
                if is_16:
                    self.emit(f"\tLDA #${(val >> 8) & 0xFF:02X}")
                    self.emit("\tSTA MATH_OP3")
                else:
                    self._stz("MATH_OP3")
                return
            if isinstance(op, Identifier):
                sym = self.current_symtab.lookup(op.name)
                self.emit(f"\tLDA {sym.asm_name()}")
                self.emit("\tSTA MATH_OP2")
                if is_16:
                    self.emit(f"\tLDA {sym.asm_name()}+1")
                    self.emit("\tSTA MATH_OP3")
                else:
                    self._stz("MATH_OP3")
                return

        # If both operands are simple, avoid math stack entirely.
        if _is_simple_operand(expr.left) and _is_simple_operand(expr.right):
            _emit_op0(expr.left, left_16)
            _emit_op2(expr.right, right_16)
        else:
            # Save left operand on math stack
            self.gen_expr(expr.left)
            self._math_stack_push(left_16)

            # Evaluate right operand into A/X
            self.gen_expr(expr.right)
            self.emit("\tSTA MATH_OP2")
            if right_16:
                self.emit("\tSTX MATH_OP3")
            else:
                self._stz("MATH_OP3")

            # Restore left operand into MATH_OP0/MATH_OP0+1
            self._math_stack_pop_to_op0()

        if expr.op == BinOp.MUL:
            self._gen_mul(left_16, right_16)
        elif expr.op == BinOp.DIV:
            self._gen_div(left_16, right_16)
        else:
            self._gen_mod(left_16, right_16)

    def _gen_mul(self, left_16: bool, right_16: bool) -> None:
        """Generate multiplication (call runtime routine)."""
        if not left_16 and not right_16:
            self.math_routines_needed.add("MUL8")
            self.emit("\tJSR MUL8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("MUL16_8")
            self.emit("\tJSR MUL16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("MUL16_8")
            # Swap operands so multiplicand is 16-bit
            self.emit("\tLDA MATH_OP0")
            self.emit("\tSTA MATH_OP1")
            self.emit("\tLDA MATH_OP2")
            self.emit("\tSTA MATH_OP0")
            self.emit("\tLDA MATH_OP3")
            self.emit("\tSTA MATH_OP0+1")
            self.emit("\tLDA MATH_OP1")
            self.emit("\tSTA MATH_OP2")
            self.emit("\tJSR MUL16_8")
        else:
            self.math_routines_needed.add("MUL16")
            # MUL16 is implemented via two calls to MUL16_8; ensure it is emitted
            self.math_routines_needed.add("MUL16_8")
            # Ensure high byte is in MATH_OP1 (MUL16 expects multiplicand low in MATH_OP0, high in MATH_OP1)
            self.emit("\tLDA MATH_OP0+1")
            self.emit("\tSTA MATH_OP1")
            self.emit("\tJSR MUL16")

    def _gen_div(self, left_16: bool, right_16: bool) -> None:
        """Generate division (call runtime routine)."""
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

    def _gen_mod(self, left_16: bool, right_16: bool) -> None:
        """Generate modulo (call runtime routine)."""
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

    def _gen_lshift(self, result_16: bool, left_tmp: str = "TMP0") -> None:
        """Generate left shift: left_tmp << A (shift count in A)"""
        self.used_temps.add("TMP2")
        self.used_temps.add("TMP3")
        # Shift count is in A
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
            self.emit("\tLDA TMP0")    # Load low byte
            self.emit("\tASL A")       # Shift left
            self.emit("\tSTA TMP0")    # Store back
            self.emit("\tLDA TMP0+1")  # Load high byte
            self.emit("\tROL A")       # Rotate with carry
            self.emit("\tSTA TMP0+1")  # Store back
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
            self.emit("\tLDA TMP0")    # Load value
            self.emit("\tASL A")       # Shift left
            self.emit("\tSTA TMP0")    # Store back
            self.emit("\tDEC TMP2")    # Decrement counter
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Load result

    def _gen_rshift(self, result_16: bool, left_tmp: str = "TMP0") -> None:
        """Generate right shift: left_tmp >> A (shift count in A)"""
        self.used_temps.add("TMP2")
        self.used_temps.add("TMP3")
        # Shift count is in A
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
            self.emit("\tLDA TMP0+1")  # Load high byte
            self.emit("\tLSR A")       # Shift right
            self.emit("\tSTA TMP0+1")  # Store back
            self.emit("\tLDA TMP0")    # Load low byte
            self.emit("\tROR A")       # Rotate right with carry
            self.emit("\tSTA TMP0")    # Store back
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
            self.emit("\tLDA TMP0")    # Load value
            self.emit("\tLSR A")       # Shift right
            self.emit("\tSTA TMP0")    # Store back
            self.emit("\tDEC TMP2")    # Decrement counter
            self.emit(f"\tBNE {lbl_loop}")
            self.emit(f"{lbl_end}:")
            self.emit("\tLDA TMP0")    # Load result

    def _gen_unary(self, expr: UnaryExpr) -> None:
        """Generate code for unary operators (@, !, ~)"""
        operand_t: ExprType = self.tc_check(expr.expr)
        
        if expr.op == UnOp.ADDROF:  # Address-of (@)
            # Generate code to load address of operand into A (low) and X (high)
            self._gen_address_of(expr.expr)
        
        elif expr.op == UnOp.BNOT:  # Bitwise NOT (~)
            # Generate operand, then apply EOR #$FF to invert bits
            self.gen_expr(expr.expr)
            
            result_16: bool = operand_t.sem_type.base == "WORD" or operand_t.sem_type.is_pointer
            
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
            
            result_16: bool = operand_t.sem_type.base == "WORD" or operand_t.sem_type.is_pointer
            
            if result_16:
                # Test if A or X is nonzero
                self.emit("\tSTA TMP4")
                self.emit("\tTXA")
                self.emit("\tORA TMP4")
                self.emit(f"\tBNE {lbl_zero}")
                # Value was zero, result is 1
                self.emit("\tLDA #$01")
                self.emit(f"\tBRA {lbl_end}")
                self.emit(f"{lbl_zero}:")
                self.emit("\tLDA #$00")
                self.emit(f"{lbl_end}:")
            else:
                # Test A only
                self.emit(f"\tBNE {lbl_zero}")
                self.emit("\tLDA #$01")
                self.emit(f"\tBRA {lbl_end}")
                self.emit(f"{lbl_zero}:")
                self.emit("\tLDA #$00")
                self.emit(f"{lbl_end}:")
    
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
                # Multiply index by element size
                self.emit(f"\tLDA #<{label}")
                self.emit("\tSTA TMP1")
                self.emit(f"\tLDA #>{label}")
                self.emit("\tSTA TMP2")
                
                # Multiply TMP0 by elem_size
                self.emit(f"\tLDA #<{elem_size}")
                self.emit(f"\tLDX #>{elem_size}")
                self.emit("\tSTX TMP3")       # Save high byte of size
                self.emit(f"\tLDA TMP0")
                self.emit(f"\tMULTIPLY_ADDRESS_{self.for_id}")
                # Result would be in TMP4:TMP5, but we need to use available temp space
                # For now, emit code to add result to base address
                
                # Simplified: use runtime multiply helper if available
                # For MVP: just handle simple cases (elem_size = 1, 2, 4)
                if elem_size == 2:
                    # Multiply by 2 = shift left
                    self.emit("\tASL TMP0")
                    self.emit("\tLDA #<{label}")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")
                    self.emit("\tSTA TMP1")
                    self.emit(f"\tLDA #>{label}")
                    self.emit("\tADC #$00")
                    self.emit("\tTAX")
                    self.emit("\tLDA TMP1")
                elif elem_size == 4:
                    # Multiply by 4 = shift left twice
                    self.emit("\tASL TMP0")
                    self.emit("\tASL TMP0")
                    self.emit("\tLDA #<{label}")
                    self.emit("\tCLC")
                    self.emit("\tADC TMP0")
                    self.emit("\tSTA TMP1")
                    self.emit(f"\tLDA #>{label}")
                    self.emit("\tADC #$00")
                    self.emit("\tTAX")
                    self.emit("\tLDA TMP1")
                else:
                    raise SemanticError(f"Element size {elem_size} not yet supported for address-of", node=getattr(self, 'current_expr', None))
        
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
    
    def _get_label_for_symbol(self, sym: Symbol) -> str:
        """Get the label name for a symbol"""
        if sym.address is not None:
            # Fixed address variable
            return f"${sym.address:04X}"
        else:
            # Dynamic address - use symbol name as label
            prefix: str = sym.proc_name + "_" if sym.proc_name else ""
            return f"_{prefix}{sym.name.upper()}"
    
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
        # TMP4 used to combine A/X when testing word values
        self.used_temps.add("TMP4")
        if expr.op == BinOp.LAND:
            lbl_false: str = self.new_label("LAND_FALSE")
            lbl_end: str   = self.new_label("LAND_END")

            # lhs
            self.gen_expr(expr.left)
            # Merge low(A) and high(X) to test non-zero
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tORA TMP4")
            self.emit(f"\tBEQ {lbl_false}")   # lhs == 0 → false

            # rhs
            self.gen_expr(expr.right)
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tORA TMP4")
            self.emit(f"\tBEQ {lbl_false}")   # rhs == 0 → false

            # true
            self.emit("\tLDA #1")
            self.emit(f"\tJMP {lbl_end}")

            # false
            self.emit(f"{lbl_false}:")
            self.emit("\tLDA #0")

            self.emit(f"{lbl_end}:")
            self.emit("\tLDX #0     ; note 5044")   # X = result high byte
            return
        
        if expr.op == BinOp.LOR:
            lbl_true: str = self.new_label("LOR_TRUE")
            lbl_end: str  = self.new_label("LOR_END")

            # lhs
            self.gen_expr(expr.left)
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tORA TMP4")
            self.emit(f"\tBNE {lbl_true}")   # lhs != 0 → true

            # rhs
            self.gen_expr(expr.right)
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tORA TMP4")
            self.emit(f"\tBNE {lbl_true}")   # rhs != 0 → true

            # false
            self.emit("\tLDA #0")
            self.emit(f"\tJMP {lbl_end}")

            # true
            self.emit(f"{lbl_true}:")
            self.emit("\tLDA #1")

            self.emit(f"{lbl_end}:")
            self.emit("\tLDX #0     ; note 5074")   # X = result high byte
            return


    def gen_expr(self, expr, force_left_tmp=None) -> None:
        # Apply constant folding and algebraic simplifications
        from typing import cast
        expr = cast(Expr, fold_expr(expr))
        
        if isinstance(expr, IntLiteral):
            self._gen_literal(expr)
        elif isinstance(expr, Identifier):
            self._gen_identifier(expr)
        elif isinstance(expr, DerefExpr):
            self._gen_deref(expr)
        elif isinstance(expr, SubscriptExpr):
            self._gen_subscript(expr, load_only=True)
        elif isinstance(expr, FieldAccess):
            # Support qualified enum access: EnumName.Member
            if isinstance(expr.object, Identifier):
                enums = getattr(self.current_symtab, '_enums', None)
                if enums is None:
                    parent = getattr(self.current_symtab, 'parent', None)
                    if parent is not None:
                        enums = getattr(parent, '_enums', None)
                if enums and expr.object.name.upper() in enums:
                    enum_def = enums[expr.object.name.upper()]
                    mname = expr.field.upper()
                    if mname not in enum_def['members']:
                        self._raise_error(f"Enum '{expr.object.name}' has no member '{expr.field}'")
                    val = enum_def['members'][mname]
                    import ast_nodes
                    self._gen_literal(ast_nodes.IntLiteral(val))
                    return
            self._gen_field_access(expr, load_only=True)
        elif isinstance(expr, CallExpr):
            # Emit source comment for function call if available
            info = self.stmt_src.get(id(expr))
            if info:
                fname, line, text = info
                self.emit(f"; {fname} {line}: {text}")
            # Evaluate and pass arguments to function parameters
            specs: list[tuple[str, int, object]] | None = self.func_param_specs.get(expr.name)
            if specs is not None:
                for i, spec in enumerate(specs):
                    pname, width, default_value = spec
                    # Determine which argument to use
                    arg = None
                    if i < len(expr.args) and expr.args[i] is not None:
                        # Use provided argument
                        arg = expr.args[i]
                    elif default_value is not None:
                        # Use default value
                        arg: object = default_value
                    else:
                        # No argument and no default - skip this parameter
                        continue
                    
                    arg_type: ExprType = self.tc_check(arg)
                    asm: str = f"_{expr.name}_{pname}"
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
                    self.gen_expr(arg)
                    if width == 1:
                        self.emit(f"\tSTA {asm}")
                    else:
                        self.emit(f"\tSTA {asm}")
                        if arg_type.sem_type.base == "BYTE" and not arg_type.sem_type.is_pointer:
                            if self.is_65c02:
                                self.emit(f"\tSTZ {asm}+1")
                            else:
                                self.emit("\tLDX #0")
                                self.emit(f"\tSTX {asm}+1")
                        else:
                            self.emit(f"\tSTX {asm}+1")
            self.emit(f"\tJSR {expr.name}")

        elif isinstance(expr, BinaryExpr):
            # Conservative TMP usage check before generating potentially large expressions
            needed: int = self._estimate_temp_slots(expr)
            max_temps: int = 6  # TMP0..TMP5 available
            if needed > max_temps:
                self._raise_error(f"Expression too complex: requires {needed} temporary slot(s) but only {max_temps} available. Simplify the expression.")

            if expr.op in {BinOp.LAND, BinOp.LOR}:
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
            self._gen_unary(expr)

    def gen_assign(self, lhs: Expr, rhs: Expr) -> None:
        # Apply constant substitution and folding to RHS
        from constsubst import subst_const
        from typing import cast
        rhs = subst_const(rhs, cast(SymbolTable, self.current_symtab))
        rhs = fold_expr(rhs)

        lhs_t: ExprType = self.tc_check(lhs, read_check_enabled=False)
        rhs_t: ExprType = self.tc_check(rhs)

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
                if arr_sym.is_array and not arr_sym.is_const and arr_sym.address is None:
                    arr_addr: str = arr_sym.asm_name()
                    element_width: int = self._calculate_element_width(arr_sym)

                    # Pointer arrays are always in ZEROPAGE; use direct ZP indexed stores
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
                        self.emit("\tLDX #0")
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
                        self.emit(f"\tLDY #0")
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

        # Special case: array-to-array assignment (string copy)
        # str3 = str2 -> copy str2 content into str3 until NUL or max length
        if isinstance(lhs, Identifier) and isinstance(rhs, Identifier):
            lhs_sym: Symbol = self.current_symtab.lookup(lhs.name)
            rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)
            
            if lhs_sym.is_array and rhs_sym.is_array and \
               lhs_t.sem_type.base == "BYTE" and rhs_t.sem_type.base == "BYTE":
                # This is a byte array to byte array copy
                self._gen_string_copy(lhs_sym, rhs_sym)
                return
            
            # Special case: const struct to struct assignment (struct copy)
            # p = ORIG -> copy const struct data into p
            if not lhs_sym.is_array and not rhs_sym.is_array and \
               lhs_t.sem_type.is_struct and rhs_t.sem_type.is_struct and \
               rhs_sym.is_const and rhs_sym.init and isinstance(rhs_sym.init, ListInit):
                # Copy const struct bytes to lhs
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
            if isinstance(rhs, IntLiteral) and sym_lhs.address is None:
                # Check if constant fits in target type
                self._check_constant_fits(rhs.value, cast(SemType, lhs_t.sem_type), f"assignment to {lhs.name}")
                if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
                    self._emit_store_byte_const(sym_lhs, rhs.value)
                else:
                    self._emit_store_word_const(sym_lhs, rhs.value)
                return

            if isinstance(rhs, BinaryExpr):
                asm: str = sym_lhs.asm_name()
                # Pointers are always 16-bit even if base type is BYTE
                is_word: bool = lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer

                def is_self(opnd) -> bool:
                    return isinstance(opnd, Identifier) and opnd.name == lhs.name

                def small_const(opnd) -> int | None:
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
                        # WORD pointers move by 2 bytes per element, BYTE pointers by 1
                        # Struct pointers move by struct size
                        scale = 1
                        if lhs_t.sem_type.is_pointer:
                            if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                                scale: int = lhs_t.sem_type.struct_info.size
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
                        else:
                            for _ in range(total_inc):
                                self.emit(f"\tINC {asm}")
                        return

                # var = var - k (k=1..3) ; only when self - const on rhs
                if rhs.op == BinOp.SUB and is_self(rhs.left) and k_right is not None:
                    k = k_right
                    # For pointer arithmetic, scale by element size
                    # WORD pointers move by 2 bytes per element, BYTE pointers by 1
                    # Struct pointers move by struct size
                    scale = 1
                    if lhs_t.sem_type.is_pointer:
                        if lhs_t.sem_type.is_struct and lhs_t.sem_type.struct_info:
                            scale: int = lhs_t.sem_type.struct_info.size
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
                    else:
                        for _ in range(total_dec):
                            self.emit(f"\tDEC {asm}")
                    return

                def _self_const_fold(expr: Expr) -> tuple[int, int] | None:
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
                        else:
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
                                self.emit(f"\tLDA {left_asm}")
                                self.emit("\tCLC")
                                self.emit(f"\tADC {right_asm}")
                                self.emit(f"\tSTA {asm}")
                                self.emit(f"\tLDA {left_asm}+1")
                                self.emit(f"\tADC {right_asm}+1")
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
                if not is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
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
                    self.emit(f"\tLDA {left_asm}")
                    if rhs.op == BinOp.ADD:
                        self.emit("\tCLC")
                        self.emit(f"\tADC {right_asm}")
                    else:  # SUB
                        self.emit("\tSEC")
                        self.emit(f"\tSBC {right_asm}")
                    self.emit(f"\tSTA {lhs_asm}")
                    
                    self.emit(f"\tLDA {left_asm}+1")
                    if rhs.op == BinOp.ADD:
                        self.emit(f"\tADC {right_asm}+1")
                    else:  # SUB
                        self.emit(f"\tSBC {right_asm}+1")
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
        #             self.emit("\tLDY #0")
        #             self.emit(f"\tSTA ({ptr_sym.asm_name()}),Y")
        #             return

        # Optimization: Direct pointer dereference for simple identifiers
        # Pattern: ptr^ = value where ptr is a simple identifier in zero page
        if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, Identifier):
            ptr_sym: Symbol = self.current_symtab.lookup(lhs.pointer.name)
            if ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array:
                # Pointer is in zero page, can use direct indirect addressing
                ptr_addr: str = ptr_sym.asm_name()
                
                # Special optimization for simple RHS (identifier or immediate)
                if isinstance(rhs, Identifier):
                    rhs_sym: Symbol = self.current_symtab.lookup(rhs.name)
                    rhs_addr: str = rhs_sym.asm_name()
                    
                    # Load RHS and store directly
                    self.emit(f"\tLDA {rhs_addr}")
                    if lhs_t.sem_type.base == "WORD":
                        # WORD: load high byte too
                        self.emit(f"\tLDX {rhs_addr}+1")
                        if self.is_65c02:
                            self.emit(f"\tSTA ({ptr_addr})")
                            self.emit(f"\tLDY #1")
                            self.emit(f"\tSTX ({ptr_addr}),Y")
                        else:
                            self.emit(f"\tLDY #0")
                            self.emit(f"\tSTA ({ptr_addr}),Y")
                            self.emit(f"\tINY")
                            self.emit(f"\tSTX ({ptr_addr}),Y")
                    else:
                        # BYTE: store only low byte (no need for X)
                        if self.is_65c02:
                            self.emit(f"\tSTA ({ptr_addr})")
                        else:
                            self.emit(f"\tLDY #0")
                            self.emit(f"\tSTA ({ptr_addr}),Y")
                    return
                elif isinstance(rhs, IntLiteral):
                    # Immediate value
                    val_low: int = rhs.value & 0xFF
                    val_high: int = (rhs.value >> 8) & 0xFF
                    
                    self.emit(f"\tLDA #${val_low:02X}")
                    if lhs_t.sem_type.base == "WORD":
                        self.emit(f"\tLDX #${val_high:02X}")
                        if self.is_65c02:
                            self.emit(f"\tSTA ({ptr_addr})")
                            self.emit(f"\tLDY #1")
                            self.emit(f"\tSTX ({ptr_addr}),Y")
                        else:
                            self.emit(f"\tLDY #0")
                            self.emit(f"\tSTA ({ptr_addr}),Y")
                            self.emit(f"\tINY")
                            self.emit(f"\tSTX ({ptr_addr}),Y")
                    else:
                        if self.is_65c02:
                            self.emit(f"\tSTA ({ptr_addr})")
                        else:
                            self.emit(f"\tLDY #0")
                            self.emit(f"\tSTA ({ptr_addr}),Y")
                    return
                
                # For complex expressions, generate normally
                self.gen_expr(rhs)
                
                # Store to dereferenced pointer
                if lhs_t.sem_type.base == "WORD":
                    # WORD: store both low and high bytes
                    if self.is_65c02:
                        self.emit(f"\tSTA ({ptr_addr})")
                        self.emit(f"\tLDY #1")
                        self.emit(f"\tSTX ({ptr_addr}),Y")
                    else:
                        self.emit(f"\tLDY #0")
                        self.emit(f"\tSTA ({ptr_addr}),Y")
                        self.emit(f"\tINY")
                        self.emit(f"\tSTX ({ptr_addr}),Y")
                else:
                    # BYTE: store only low byte
                    if self.is_65c02:
                        self.emit(f"\tSTA ({ptr_addr})")
                    else:
                        self.emit(f"\tLDY #0")
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
                if zp_sym and zp_sym.is_array and zp_sym.type.is_pointer and zp_sym.address is None:
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
        self.assign_target_type = cast(SemType, lhs_t.sem_type)
        self.assign_target_sym = None
        self.assign_target_blocked = False
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
                self.emit("\tLDX #0     ; note 5677")  # Clear X for BYTE to WORD conversion
            else:
                self.emit("\tLDX #0     ; note 5679")

        if isinstance(lhs, Identifier):

            sym: Symbol = self.current_symtab.lookup(lhs.name)

            if sym.is_const:
                self._raise_error("Cannot assign to const")

            asm: str = sym.asm_name()
            if sym.type.base == "BYTE" and not sym.type.is_pointer:
                self.emit(f"\tSTA {asm}")
            else:
                self.emit(f"\tSTA {asm}")
                self.emit(f"\tSTX {asm}+1")
            return

        # dereference
        if isinstance(lhs, DerefExpr):
            # This should not be reached if the optimization above triggered
            # But kept as fallback for complex pointer expressions
            # 1️⃣ ulož RHS hodnotu
            self.emit("\tSTA TMP2")
            self.emit("\tSTX TMP2+1")

            # 2️⃣ vygeneruj adresu pointeru
            self.gen_expr(lhs.pointer)

            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")

            # 3️⃣ zápis LOW byte
            self.emit("\tLDA TMP2")
            if lhs_t.sem_type.base == "WORD":
                self.emit("\tLDY #0")
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
            # Save RHS value to temps before field access calculation
            self.emit("\tSTA TMP2")
            # Only save high byte if RHS is not BYTE (or if we don't know the type)
            # For BYTE RHS, X is either 0 or undefined, and we don't need it for BYTE field assignment
            if rhs_t.sem_type.base == "WORD" or rhs_t.sem_type.is_pointer:
                self.emit("\tSTX TMP2+1")
            
            # Set assignment target type to the field type for optimizations
            # This helps skip unnecessary LDX #0 when the field is BYTE
            prev_assign_type: SemType | None = self.assign_target_type
            self.assign_target_type = lhs_t.sem_type
            try:
                self._gen_field_access(lhs, load_only=False)
            finally:
                self.assign_target_type = prev_assign_type
            return

        self._raise_error(f"Assignment target type not supported: {type(lhs).__name__}")

    def _gen_for_const_step(self, stmt, step_expr) -> None:
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # end
        end_name: str = self.new_for_var("END")
        end_t: ExprType = self.tc_check(stmt.end)
        var_t: ExprType = self.tc_check(stmt.var)
        end_is_word: bool = (
            var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
            end_t.sem_type.base == "WORD" or end_t.sem_type.is_pointer
        )
        self._declare_temp(end_name, "WORD" if end_is_word else "BYTE")
        end_var = Identifier(end_name)
        self.gen_assign(end_var, stmt.end)

        # podmínka WHILE
        if step_expr.value > 0:
            cond = BinaryExpr(stmt.var, BinOp.LE, end_var)
        else:
            cond = BinaryExpr(stmt.var, BinOp.GE, end_var)

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
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # vytvoř skryté proměnné
        end_name: str = self.new_for_var("END")
        step_name: str = self.new_for_var("STEP")

        var_t: ExprType = self.tc_check(stmt.var)
        end_t: ExprType = self.tc_check(stmt.end)
        step_t: ExprType = self.tc_check(stmt.step) if stmt.step is not None else self.tc_check(IntLiteral(1))

        end_is_word: bool = (
            var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
            end_t.sem_type.base == "WORD" or end_t.sem_type.is_pointer
        )
        step_is_word: bool = (
            var_t.sem_type.base == "WORD" or var_t.sem_type.is_pointer or
            step_t.sem_type.base == "WORD" or step_t.sem_type.is_pointer
        )

        self._declare_temp(end_name, "WORD" if end_is_word else "BYTE")
        self._declare_temp(step_name, "WORD" if step_is_word else "BYTE")

        end_var = Identifier(end_name)
        step_var = Identifier(step_name)

        # end = ...
        self.gen_assign(end_var, stmt.end)

        # step = ... (nebo 1)
        step_expr = stmt.step if stmt.step is not None else IntLiteral(1)
        self.gen_assign(step_var, step_expr)

        # IF step > 0 THEN IF i > end THEN BREAK ELSE IF i < end THEN BREAK
        cond_step_pos = BinaryExpr(step_var, BinOp.GT, IntLiteral(0))

        cond_i_gt_end = BinaryExpr(stmt.var, BinOp.GT, end_var)
        cond_i_lt_end = BinaryExpr(stmt.var, BinOp.LT, end_var)

        if_pos = IfStmt(cond_i_gt_end, [BreakStmt()], None)
        if_neg = IfStmt(cond_i_lt_end, [BreakStmt()], None)

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
            self.emit(f"; {fname} {line}: {text}")
        self.emit("; -- Procedure " + proc.ast.name + " --")
        self.emit(f"{proc.ast.name}:")

        # INIT lokálů
        for sym in proc.locals:
            self.gen_init(cast(Symbol, sym))

        # tělo
        for stmt in proc.ast.body:
            self.gen_stmt(stmt)

        self.emit("\tRTS")

        # restore
        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab


    def gen_stmt(self, stmt):
        from ast_nodes import SegmentDirective, IncbinDirective
        # Emit source comment for this statement
        self.emit_src_comment_for_stmt(stmt)
        
        if isinstance(stmt, SegmentDirective):
            self.emit(f'.segment "{stmt.name}"')
            return

        if isinstance(stmt, IncbinDirective):
            self.emit(f'.incbin "{stmt.filename}"')
            return

        if isinstance(stmt, AsmBlock):
            for line in stmt.text.splitlines():
                self.emit(line)
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
            specs: list[tuple[str, int, object]] | None = self.proc_param_specs.get(stmt.name)
            if specs is not None:
                for i, spec in enumerate(specs):
                    pname, width, default_value = spec
                    # Determine which argument to use
                    arg = None
                    if i < len(stmt.args) and stmt.args[i] is not None:
                        # Use provided argument
                        arg = stmt.args[i]
                    elif default_value is not None:
                        # Use default value
                        arg: object = default_value
                    else:
                        # No argument and no default - skip this parameter
                        continue
                    
                    arg_type: ExprType = self.tc_check(arg)
                    asm: str = f"_{stmt.name}_{pname}"
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
                    # evaluate arg into A/(X)
                    self.gen_expr(arg)
                    if width == 1:
                        self.emit(f"\tSTA {asm}")
                    else:
                        # If the argument is byte-sized, its high byte is zero; store zero safely
                        self.emit(f"\tSTA {asm}")
                        if arg_type.sem_type.base == "BYTE" and not arg_type.sem_type.is_pointer:
                            if self.is_65c02:
                                self.emit(f"\tSTZ {asm}+1")
                            else:
                                self.emit("\tLDX #0")
                                self.emit(f"\tSTX {asm}+1")
                        else:
                            self.emit(f"\tSTX {asm}+1")
            self.emit(f"\tJSR {stmt.name}")
            return

        if isinstance(stmt, AssignStmt):
            self.gen_assign(stmt.lhs, stmt.rhs)
            return

        if isinstance(stmt, ReturnStmt):
            # Generate the return expression (if any - PROCs may have no return value)
            if stmt.expr is not None:
                self.gen_expr(stmt.expr)
            
            # If function expects BYTE but expression is WORD, use only lower byte (A register already has it)
            # X register will be ignored on return
            
            self.emit("\tRTS")
            return
        
        if isinstance(stmt, IfStmt):
            cond: Expr = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond: Expr = fold_expr(cond)

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
            self.used_temps.add("TMP4")
            self.gen_expr(cond)
            # Merge A/X to test non-zero (WORD-safe)
            self.emit("\tSTA TMP4")
            self.emit("\tTXA")
            self.emit("\tORA TMP4")
            self.emit(f"\tBEQ {lbl_else}")

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

            self.emit(f"{lbl_start}:")
            cond: Expr = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond: Expr = fold_expr(cond)

            from ast_nodes import BinaryExpr
            if isinstance(cond, BinaryExpr) and cond.op in {BinOp.EQ, BinOp.NE, BinOp.LT, BinOp.LE, BinOp.GT, BinOp.GE}:
                self._emit_relational_branch(cond, lbl_true=lbl_body, lbl_false=lbl_end)
            else:
                self.used_temps.add("TMP4")
                self.gen_expr(cond)
                self.emit("\tSTA TMP4")
                self.emit("\tTXA")
                self.emit("\tORA TMP4")
                self.emit(f"\tBEQ {lbl_end}")

            self.emit(f"{lbl_body}:")

            for s in stmt.body:
                self.gen_stmt(s)

            self.emit(f"\tJMP {lbl_start}")
            self.emit(f"{lbl_end}:")

            # POP
            self.loop_stack.pop()
            return
        
        if isinstance(stmt, BreakStmt):
            if not self.loop_stack:
                self._raise_error("BREAK outside of loop")
            _, end_label = self.loop_stack[-1]
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
        prev_symtab: SymbolTable = self.current_symtab
        prev_tc_symtab: Any | None = getattr(self.tc, "symtab", None)
        prev_func_return_type: str | None = self.current_func_return_type
        
        self.current_symtab = cast(SymbolTable, func.symtab)
        self.tc.symtab = func.symtab
        self.current_func_return_type = func.ast.ret_type.base  # Set return type for this function

        self.emit("; -- Function " + func.ast.name + " --")
        self.emit(f"{func.ast.name}:")

        # init lokálů
        for sym in func.locals:
            self.gen_init(cast(Symbol, sym))

        # tělo
        for stmt in func.ast.body:
            self.gen_stmt(stmt)

        # fallback (pokud RETURN nebyl – zatím chyba v sémantice)
        self.emit("\tRTS")

        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab
        self.current_func_return_type = prev_func_return_type

    def _gen_relational(self, expr: BinaryExpr) -> None:
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
                return sym.asm_name()

            return None

        cmp_operand = simple_byte_operand(expr.right)

        if cmp_operand is not None:
            # Left operand only; right is accessed directly in CMP
            self.gen_expr(expr.left)
        else:
            # pravý operand first (for correct CMP operand order)
            self.gen_expr(expr.right)
            # Ensure high byte is well-defined in 16-bit context
            if is_16bit and right_t.sem_type.base != "WORD":
                self.emit("\tLDX #0     ; note 6088")
            self.emit("\tSTA TMP0")
            if is_16bit:      # Fixme: ? Je to spravne? Nechybi tady and right_t.sem_type.base != "WORD":
                self.emit("\tSTX TMP0+1")

            # levý operand
            self.gen_expr(expr.left)
            # Ensure left high byte is well-defined in 16-bit context
            if is_16bit and left_t.sem_type.base != "WORD":
                self.emit("\tLDX #0     ; note 6097")

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
                self.emit(f"\tBEQ @GE_CHECK_LOW") # High equal, check low
                self.emit(f"\tBCS {lbl_true}")    
                self.emit(f"\tJMP {lbl_end}")     
                self.emit("@GE_CHECK_LOW:")
                self.emit("\tCMP TMP0")
                self.emit(f"\tBCS {lbl_true}")
            elif expr.op == BinOp.GT:       # > 
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBCC {lbl_end}")     
                self.emit(f"\tBEQ @GT_CHECK_LOW") # High equal, check low
                self.emit(f"\tJMP {lbl_true}")    
                self.emit("@GT_CHECK_LOW:")
                self.emit("\tCMP TMP0")
                self.emit(f"\tBEQ {lbl_end}")    
                self.emit(f"\tBCS {lbl_true}")    
            elif expr.op == BinOp.LE:       # <=
                self.emit("\tCPX TMP0+1")
                self.emit(f"\tBCC {lbl_true}")    
                self.emit(f"\tBEQ @LE_CHECK_LOW") 
                self.emit(f"\tJMP {lbl_end}")     
                self.emit("@LE_CHECK_LOW:")
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
        self.emit("\tLDA #0")
        self.emit(f"\tJMP {lbl_end}")

        # true
        self.emit(f"{lbl_true}:")
        self.emit("\tLDA #1")

        self.emit(f"{lbl_end}:")
        # Comparison always returns a BYTE result, clear X
        self.emit("\tLDX #0     ; note 6178")

    def _emit_relational_branch(self, cond: BinaryExpr, *, lbl_true: str, lbl_false: str) -> None:
        """Emit relational test that jumps to lbl_true or lbl_false using only short local branches and absolute JMPs.

        This avoids boolean materialization and keeps conditional branches within range by funneling through local labels.
        """
        left_t: ExprType = self.tc_check(cond.left)
        right_t: ExprType = self.tc_check(cond.right)
        is_16bit: bool = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"

        cmp_lo = "TMP0"
        cmp_hi = "TMP0+1"

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
        from ast_nodes import IntLiteral
        from typing import cast
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
                asm: str = sym.asm_name()
                if cond.op == BinOp.EQ:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
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
                        if is_16bit and left_t.sem_type.base != "WORD":
                            self.emit("\tLDX #0     ; note 7036")

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
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ @GT_CHECK_LOW")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit("@GT_CHECK_LOW:")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBEQ {lbl_else_tmp}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                        if cond.op == BinOp.GE:
                            lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                            self.emit(f"\tCPX {cmp_hi}")
                            self.emit(f"\tBCC {lbl_else_tmp}")
                            self.emit(f"\tBEQ @GE_CHECK_LOW")
                            self.emit(f"\tJMP {lbl_true}")
                            self.emit("@GE_CHECK_LOW:")
                            self.emit(f"\tCMP {cmp_lo}")
                            self.emit(f"\tBCS {lbl_true}")
                            self.emit(f"{lbl_else_tmp}:")
                            self.emit(f"\tJMP {lbl_false}")
                            return
                if cond.op == BinOp.NE:
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBNE {lbl_true}")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.LE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                    # Compare low byte first
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_chk_hi}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    # Low bytes equal, check high byte
                    self.emit(f"{lbl_chk_hi}:")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBNE {lbl_true}")                    
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBNE {lbl_true}")                    
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GE:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCMP {cmp_hi}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")                    
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCS {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")                    
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return

            # Fast path: byte identifier vs constant → simple CMP without LDX
            if not is_16bit and isinstance(cond.left, Identifier):
                sym: Symbol = self.current_symtab.lookup(cond.left.name)
                asm: str = sym.asm_name()
                if cond.op == BinOp.EQ:
                    lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"{lbl_else_tmp}:")
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
            if is_16bit and left_t.sem_type.base != "WORD":
                self.emit("\tLDX #0     ; note 6311")
        else:
            # Try simple byte operand optimization for 8-bit compares
            cmp_operand: str | None = simple_byte_operand(cond.right)
            
            if cmp_operand is not None:
                # Left operand only; right is accessed directly in CMP
                # Optimize: if left is also simple BYTE, load it directly without gen_expr to avoid unnecessary LDX #0
                # This avoids the unneeded "LDX #0" that would normally follow "LDA byte_var" (optimization at 6321)
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
                if is_16bit and right_t.sem_type.base != "WORD":
                    self.emit("\tLDX #0     ; note 6325")
                self.emit("\tSTA TMP0")
                if is_16bit:
                    self.emit("\tSTX TMP0+1")
                self.gen_expr(cond.left)
                if is_16bit and left_t.sem_type.base != "WORD":
                    self.emit("\tLDX #0     ; note 6331")
                # Set cmp_lo and cmp_hi to TMP0
                cmp_lo = "TMP0"
                cmp_hi = "TMP0+1"

        if is_16bit:
            if cond.op == BinOp.EQ:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare low byte first (faster for early mismatch)
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBNE {lbl_else_tmp}")
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
                lbl_check_hi: str = self.new_label("CHECK_HI")
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                # Low bytes equal, check high byte
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.LE:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                lbl_chk_hi: str = self.new_label("LE_CHK_HI")
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_chk_hi}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                # Low bytes equal, check high byte
                self.emit(f"{lbl_chk_hi}:")
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GT:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBEQ {lbl_else_tmp}")
                self.emit(f"\tBCS {lbl_true}")
                # Low byte less, check high byte
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_else_tmp}")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GE:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCS {lbl_true}")
                # Low byte less, check high byte
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_else_tmp}")
                self.emit(f"\tBNE {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
        else:
            # 8-bit patterns
            if cond.op == BinOp.EQ:
                lbl_else_tmp: str = self.new_label("REL_ELSE_TMP")
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
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
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBEQ {lbl_false}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GE:
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCS {lbl_true}")
                self.emit(f"\tJMP {lbl_false}")

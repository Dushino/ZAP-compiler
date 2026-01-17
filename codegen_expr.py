
from typing import cast
from constfold import fold_expr
from constsubst import subst_const
from symbols import Symbol, SymbolTable, SemType
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
    Expr, ExprInit, ListInit, StringInit, CallExpr,
    CallStmt, AssignStmt,
    IfStmt, ReturnStmt, WhileStmt, ForStmt,
    AsmBlock
)
from sema_expr import ExprTypeChecker
from sema_types import ExprKind, ExprType
from sema_proc import AnalyzedProc
from sema_func import AnalyzedFunc

from errors import SemanticError


class CodeGen:
    label_id = 0
    loop_stack = []

    def __init__(self, symtab: SymbolTable, type_checker: ExprTypeChecker, *, is_65c02: bool = True, used_globals: set[str] | None = None, debug_info: dict | None = None, command_line: str | None = None, proc_param_specs: dict[str, list[tuple[str, int]]] | None = None, func_param_specs: dict[str, list[tuple[str, int]]] | None = None, pruned_procs: list[str] | None = None):
        # global symbol table (globals)
        self.global_symtab: SymbolTable = symtab
        # currently active table (can be scoped for PROC/FUNC)
        self.current_symtab: SymbolTable = symtab
        self.tc = type_checker   
        self.code: list[str] = []
        self.for_id = 0
        self.string_literals = {}  # Maps string content to label name
        self.string_id = 0
        self.array_literals = {}   # Maps array data tuple to label name
        self.array_id = 0
        self.copy_bytes_needed = False
        self.math_routines_needed: set[str] = set()
        self.is_65c02 = is_65c02
        self.used_globals = used_globals or set()
        self.used_temps: set[str] = set()
        self.command_line = command_line
        # Parameter specs: mapping name -> list of (param_name, width_bytes)
        self.proc_param_specs: dict[str, list[tuple[str, int]]] = proc_param_specs or {}
        self.func_param_specs: dict[str, list[tuple[str, int]]] = func_param_specs or {}
        self.pruned_procs = pruned_procs or []
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

    def tc_check(self, expr):
        # Wrapper to attach source location to type-checker errors
        try:
            return self.tc.check(expr)
        except SemanticError as e:
            # If error lacks position, attach current statement info
            if getattr(e, 'line', None) is None and self.current_stmt_info:
                self._raise_error(e.message)
            raise

    def new_label(self, prefix):
        self.label_id += 1
        return f"{prefix}_{self.label_id}"

    def new_for_var(self, base):
        self.for_id += 1
        return f"__FOR_{base}_{self.for_id}"

    def _stz(self, operand: str):
        if self.is_65c02:
            self.emit(f"\tSTZ {operand}")
        else:
            self.emit("\tLDA #0")
            self.emit(f"\tSTA {operand}")

    def _emit_store_byte_const(self, sym: Symbol, value: int):
        value &= 0xFF
        asm = sym.asm_name()
        if value == 0:
            self._stz(asm)
        else:
            self.emit(f"\tLDA #${value:02X}")
            self.emit(f"\tSTA {asm}")

    def _emit_store_word_const(self, sym: Symbol, value: int):
        value &= 0xFFFF
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        asm = sym.asm_name()
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

    def _emit_inc_word(self, asm: str):
        lbl = self.new_label("INC_WORD")
        self.emit(f"\tINC {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tINC {asm}+1")
        self.emit(f"{lbl}:")

    def _emit_dec_word(self, asm: str):
        lbl = self.new_label("DEC_WORD")
        self.emit(f"\tLDA {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tDEC {asm}+1")
        self.emit(f"{lbl}:")
        self.emit(f"\tDEC {asm}")

    def _lda_const(self, line: str) -> int | None:
        """Return immediate value for LDA #imm or None if not a match."""
        stripped = line.strip().upper()
        if not stripped.startswith("LDA #"):
            return None
        imm = stripped[5:]  # after 'LDA #' (includes possible $)
        try:
            if imm.startswith("$"):
                return int(imm[1:], 16)
            return int(imm, 10)
        except ValueError:
            return None

    def _is_sta(self, line: str) -> bool:
        return line.strip().upper().startswith("STA ")

    def _inc_operand(self, line: str) -> str | None:
        stripped = line.strip().upper()
        if stripped.startswith("INC "):
            return stripped[4:].strip()
        return None

    def _dec_operand(self, line: str) -> str | None:
        stripped = line.strip().upper()
        if stripped.startswith("DEC "):
            return stripped[4:].strip()
        return None

    def _is_fixed_address(self, operand: str) -> bool:
        """Check if operand references a fixed-address (hardware) variable.
        
        Fixed-address variables must never be optimized away as reads/writes
        may have side effects (clearing flags, triggering hardware, etc.).
        """
        # Extract label from operand (handle indexed modes like "LABEL,X" or "LABEL,Y" or "LABEL+1")
        label = operand.split(',')[0].strip()  # Remove ,X or ,Y
        label = label.split('+')[0].strip()    # Remove +1
        label = label.split('-')[0].strip()    # Remove -1 (rare but possible)
        return label in self.fixed_address_labels

    def _sets_nz_flags(self, line: str) -> bool:
        """Return True if instruction overwrites N/Z so earlier flags cannot be observed."""
        stripped = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        opcode = stripped.split()[0]
        nz_ops = {
            "ADC", "AND", "ASL", "BIT", "CMP", "CPX", "CPY", "DEC", "DEX", "DEY",
            "EOR", "INC", "INX", "INY", "LDA", "LDX", "LDY", "LSR", "ORA", "PLA",
            "PLX", "PLY", "ROL", "ROR", "SBC", "TAX", "TAY", "TSX", "TXA", "TYA",
        }
        return opcode in nz_ops

    def _clobbers_a(self, line: str) -> bool:
        """Return True if instruction changes accumulator contents."""
        stripped = line.strip().upper()
        if not stripped or stripped.endswith(":") or stripped.startswith(";"):
            return False
        parts = stripped.split()
        if not parts:
            return False
        op = parts[0]
        # Ops that always write A
        if op in {"LDA", "PLA", "ADC", "SBC", "ORA", "AND", "EOR"}:
            return True
        # Accumulator shifts/rotates
        if op in {"ASL", "LSR", "ROL", "ROR"}:
            # memory form has an operand; accumulator form often has none or "A"
            return len(parts) == 1 or parts[1] == "A"
        return False

    def peephole_optimize(self):
        """Apply lightweight peepholes to emitted code for both 6502 and 65c02."""
        # Disable peephole optimization if code uses PHA/PLA (stack-based temp preservation)
        # PHA/PLA sequences are too complex for safe optimization
        has_pha_pla = any("PHA" in line.upper() or "PLA" in line.upper() for line in self.code)
        if has_pha_pla:
            # Return code unoptimized - PHA/PLA sections are too risky to optimize
            return
        
        optimized: list[str] = []
        skip_indices = set()  # Track which indices to skip
        
        i = 0
        while i < len(self.code):
            # Check if this instruction should be skipped (marked as redundant)
            if i in skip_indices:
                i += 1
                continue

            # Always preserve labels verbatim
            if self.code[i].strip().endswith(":"):
                optimized.append(self.code[i])
                i += 1
                continue
            
            # Remove duplicate consecutive stores to same location
            #   STA addr ; STA addr  → STA addr
            #   STX TMP1 ; STX TMP1  → STX TMP1
            # BUT: Never optimize stores/loads involving TMP0-TMP4 (used for pointer arithmetic)
            # NEVER optimize stores to fixed-address (hardware) variables
            if i + 1 < len(self.code):
                cur = self.code[i].strip()
                nxt = self.code[i + 1].strip()
                curU = cur.upper()
                nxtU = nxt.upper()
                
                # Check for duplicate stores (same instruction and operand)
                if curU.startswith(("STA ", "STX ", "STY ")):
                    if curU == nxtU:
                        # Extract operand to check if it's a fixed address
                        cur_parts = curU.split(maxsplit=1)
                        if len(cur_parts) == 2:
                            cur_operand = cur_parts[1].strip()
                            # Skip optimization for fixed-address variables AND temp registers
                            if not self._is_fixed_address(cur_operand) and not any(tmp in cur_operand for tmp in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4"]):
                                # Duplicate store - skip the second one
                                optimized.append(self.code[i])
                                i += 2
                                continue
                
            # Elide redundant reloads:
            #   STA addr ; LDA addr  → STA addr
            #   STX addr ; LDX addr  → STX addr
            #   STY addr ; LDY addr  → STY addr
            if i + 1 < len(self.code):
                cur = self.code[i].strip()
                nxt = self.code[i + 1].strip()
                curU = cur.upper()
                nxtU = nxt.upper()
                # Drop consecutive LDA/LDX/LDY when the next meaningful instruction overwrites the same register
                # NEVER optimize loads from fixed-address (hardware) variables - reads may have side effects
                if curU.startswith(("LDA ", "LDX ", "LDY ")):
                    # Extract operand and check if it's a fixed address
                    cur_parts = curU.split(maxsplit=1)
                    cur_operand = cur_parts[1].strip() if len(cur_parts) == 2 else ""
                    
                    # Skip optimization for fixed-address variables
                    if self._is_fixed_address(cur_operand):
                        optimized.append(self.code[i])
                        i += 1
                        continue
                    
                    redundant_load = False
                    redundant_at = -1
                    j = i + 1
                    jsr_seen = False
                    reg_used = False
                    # Determine which register we're checking
                    checking_a = curU.startswith("LDA ")
                    checking_x = curU.startswith("LDX ")
                    checking_y = curU.startswith("LDY ")
                    
                    while j < len(self.code) and j < i + 20:  # Limit lookahead
                        look = self.code[j].strip()
                        lookU = look.upper()
                        if not look or lookU.endswith(":") or lookU.startswith(";"):
                            j += 1
                            continue
                        # Stop at barriers
                        if lookU.startswith(("JSR ", "RTS", "BRK")) or lookU in ("RTS", "BRK"):
                            jsr_seen = True
                            break
                        # Stop at branches (register might be tested)
                        if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BPL ", "BMI ", "BVC ", "BVS ")):
                            break
                        # Check if register is used/modified (excluding stores which preserve the value)
                        if checking_a and any(op in lookU for op in ["PHA", "ADC ", "SBC ", "ORA ", "AND ", "EOR ", "CMP ", "TAX", "TAY"]):
                            reg_used = True
                        if checking_x and any(op in lookU for op in ["INX", "DEX", "CPX ", "TXA", "TXS"]):
                            reg_used = True
                        if checking_y and any(op in lookU for op in ["INY", "DEY", "CPY ", "TYA"]):
                            reg_used = True
                        # Check if same register is reloaded with SAME operand
                        if (checking_a and lookU.startswith("LDA ")) or \
                           (checking_x and lookU.startswith("LDX ")) or \
                           (checking_y and lookU.startswith("LDY ")):
                            look_parts = lookU.split(maxsplit=1)
                            look_operand = look_parts[1].strip() if len(look_parts) == 2 else ""
                            if look_operand == cur_operand:  # Only redundant if operands match
                                # But don't mark as redundant if it's a fixed-address variable
                                if not self._is_fixed_address(look_operand):
                                    redundant_load = True
                                    redundant_at = j
                            break  # Stop at any load of the same register, redundant or not
                        # Continue scanning if register not modified yet
                        if reg_used:
                            break
                        j += 1
                    
                    if redundant_load and not jsr_seen:
                        # Keep first load, mark redundant load for skipping
                        # Intermediate instructions (including comments/labels) will be processed in subsequent iterations
                        skip_indices.add(redundant_at)
                        optimized.append(self.code[i])
                        i += 1
                        continue

                # Drop repeated LDA #imm when nothing in between clobbers A or N/Z flags
                if curU.startswith("LDA #"):
                    cur_val = self._lda_const(cur)
                    if cur_val is not None:
                        j = i + 1
                        seen_clobber = False
                        while j < len(self.code) and j < i + 20:
                            look_raw = self.code[j]
                            look = look_raw.strip()
                            lookU = look.upper()
                            if not look or look.endswith(":") or look.startswith(";"):
                                j += 1
                                continue
                            # Stop on control flow changes
                            if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                break
                            # Stop on branches (flags are observed)
                            if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ")):
                                break
                            # If anything sets flags or touches A, abort
                            if self._sets_nz_flags(look):
                                seen_clobber = True
                                break
                            if lookU.startswith("LDA #"):
                                look_val = self._lda_const(look_raw)
                                if look_val is not None and look_val == cur_val and not seen_clobber:
                                    skip_indices.add(j)
                                break
                            j += 1
                
                # Drop repeated LDX #imm when nothing in between clobbers X or N/Z flags
                if curU.startswith("LDX #"):
                    cur_val = self._lda_const(cur)  # Reuse immediate extraction logic
                    if cur_val is not None:
                        j = i + 1
                        seen_clobber = False
                        while j < len(self.code) and j < i + 20:
                            look_raw = self.code[j]
                            look = look_raw.strip()
                            lookU = look.upper()
                            if not look or look.endswith(":") or look.startswith(";"):
                                j += 1
                                continue
                            if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                break
                            if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ")):
                                break
                            # Check if X or N/Z clobbered
                            if self._sets_nz_flags(look) or any(lookU.startswith(op) or lookU == op for op in ["LDX ", "TAX", "INX", "DEX", "PLX"]):
                                seen_clobber = True
                                break
                            if lookU.startswith("LDX #"):
                                look_val = self._lda_const(look_raw)
                                if look_val is not None and look_val == cur_val and not seen_clobber:
                                    skip_indices.add(j)
                                break
                            j += 1
                
                # Drop repeated LDY #imm when nothing in between clobbers Y or N/Z flags
                if curU.startswith("LDY #"):
                    cur_val = self._lda_const(cur)  # Reuse immediate extraction logic
                    if cur_val is not None:
                        j = i + 1
                        seen_clobber = False
                        while j < len(self.code) and j < i + 20:
                            look_raw = self.code[j]
                            look = look_raw.strip()
                            lookU = look.upper()
                            if not look or look.endswith(":") or look.startswith(";"):
                                j += 1
                                continue
                            if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                break
                            if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ")):
                                break
                            # Check if Y or N/Z clobbered
                            if self._sets_nz_flags(look) or any(lookU.startswith(op) or lookU == op for op in ["LDY ", "TAY", "INY", "DEY", "PLY"]):
                                seen_clobber = True
                                break
                            if lookU.startswith("LDY #"):
                                look_val = self._lda_const(look_raw)
                                if look_val is not None and look_val == cur_val and not seen_clobber:
                                    skip_indices.add(j)
                                break
                            j += 1
                
                # Check if current instruction is a load (LDA/LDX/LDY) that will be stored to fixed-address or temps
                # If so, never optimize away the load. Look ahead up to 5 instructions to find the store.
                if curU.startswith(("LDA ", "LDX ", "LDY ")):
                    # Determine which register and corresponding store instruction
                    if curU.startswith("LDA "):
                        store_prefix = "STA "
                    elif curU.startswith("LDX "):
                        store_prefix = "STX "
                    else:  # LDY
                        store_prefix = "STY "
                    
                    # Look ahead to see if this register is stored to a fixed-address variable or temporary
                    protect_load = False
                    for lookahead_i in range(i + 1, min(i + 6, len(self.code))):
                        lookahead = self.code[lookahead_i].strip().upper()
                        # Skip comments and labels
                        if not lookahead or lookahead.endswith(":") or lookahead.startswith(";"):
                            continue
                        # Check if this is a store of the loaded register to fixed-address or temp register
                        if lookahead.startswith(store_prefix):
                            lookahead_parts = lookahead.split(maxsplit=1)
                            if len(lookahead_parts) == 2:
                                lookahead_operand = lookahead_parts[1].strip()
                                # Protect the load if storing to fixed-address OR temp registers (used for indirect addressing)
                                if self._is_fixed_address(lookahead_operand) or lookahead_operand in ("TMP0", "TMP0+1", "TMP1", "TMP1+1", "TMP2", "TMP2+1", "TMP3", "TMP3+1", "TMP4", "TMP4+1"):
                                    # Protect the load - it's needed for the store
                                    protect_load = True
                                    break
                        # Stop if we encounter an instruction that modifies the register
                        if curU.startswith("LDA ") and (lookahead.startswith("LDA ") or lookahead.startswith("PLA")):
                            break
                        if curU.startswith("LDX ") and (lookahead.startswith("LDX ") or lookahead.startswith("PLX") or lookahead.startswith("TAX")):
                            break
                        if curU.startswith("LDY ") and (lookahead.startswith("LDY ") or lookahead.startswith("PLY") or lookahead.startswith("TAY")):
                            break
                    
                    if protect_load:
                        optimized.append(self.code[i])
                        i += 1
                        continue
                
                # Simple consecutive LDA overwrite (preserve the later load)
                # UNLESS the second LDA is followed by a store to a fixed-address variable
                if curU.startswith("LDA ") and nxtU.startswith("LDA "):
                    # Check if instruction after second LDA is a store to fixed-address
                    skip_opt = False
                    if i + 2 < len(self.code):
                        third = self.code[i + 2].strip().upper()
                        if third.startswith("STA "):
                            third_operand = third[4:].strip()
                            if self._is_fixed_address(third_operand):
                                skip_opt = True
                    if not skip_opt:
                        i += 1
                        continue
                store_load_pairs = [("STA", "LDA"), ("STX", "LDX"), ("STY", "LDY")]
                matched = False
                for st, ld in store_load_pairs:
                    if curU.startswith(st + " ") and nxtU.startswith(ld + " "):
                        op1 = curU[len(st) + 1:].strip()
                        op2 = nxtU[len(ld) + 1:].strip()
                        if op1 == op2:
                            # Skip optimization for fixed-address variables
                            if not self._is_fixed_address(op1):
                                optimized.append(self.code[i])
                                i += 2
                                matched = True
                                break
                if matched:
                    continue
                
                # Remove redundant consecutive stores (STA/STX/STY) to same location when no JSR between
                # NEVER optimize stores to fixed-address (hardware) variables
                if curU.startswith(("STA ", "STX ", "STY ")):
                    cur_parts = curU.split(maxsplit=1)
                    if len(cur_parts) == 2:
                        cur_operand = cur_parts[1].strip()
                        # Skip optimization for fixed-address variables
                        if self._is_fixed_address(cur_operand):
                            optimized.append(self.code[i])
                            i += 1
                            continue
                        
                        # Check if storing to a fixed-address variable (contains @)
                        # For now, we'll only optimize if operand doesn't look like it has @ address
                        # Fixed-address vars won't appear here since they're declared in source
                        redundant_store = False
                        j = i + 1
                        jsr_seen = False
                        redundant_at = -1
                        while j < len(self.code):
                            look = self.code[j].strip()
                            lookU = look.upper()
                            if not look or lookU.endswith(":") or lookU.startswith(";"):
                                j += 1
                                continue
                            if lookU.startswith("JSR "):
                                jsr_seen = True
                                break
                            # Check for same store instruction
                            if lookU.startswith(cur_parts[0] + " "):
                                look_parts = lookU.split(maxsplit=1)
                                if len(look_parts) == 2 and look_parts[1].strip() == cur_operand:
                                    redundant_store = True
                                    redundant_at = j
                                    break
                            # Stop if we hit any instruction that might affect the stored value
                            break
                        if redundant_store and not jsr_seen:
                            # Keep first store, mark redundant store for skipping
                            # Intermediate instructions (including comments/labels) will be processed in subsequent iterations
                            skip_indices.add(redundant_at)
                            optimized.append(self.code[i])
                            i += 1
                            continue

                # Elide spaced redundant STA when A is unchanged between
                if curU.startswith("STA "):
                    cur_parts = cur.split(maxsplit=1)
                    if len(cur_parts) == 2:
                        cur_operand = cur_parts[1].strip()
                        cur_operand_upper = cur_operand.upper()
                        # Skip temps and fixed addresses and indirect operands
                        if not self._is_fixed_address(cur_operand) and "TMP" not in cur_operand_upper and "(" not in cur_operand_upper:
                            j = i + 1
                            while j < len(self.code) and j < i + 20:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                # Barriers: calls/returns/long jumps
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Stop if A is clobbered before we find the next store
                                if self._clobbers_a(look):
                                    break
                                if lookU.startswith("STA "):
                                    look_parts = look.split(maxsplit=1)
                                    if len(look_parts) == 2 and look_parts[1].strip().upper() == cur_operand_upper:
                                        skip_indices.add(j)
                                        break
                                j += 1
                
                # Elide spaced redundant STX when X is unchanged between
                if curU.startswith("STX "):
                    cur_parts = cur.split(maxsplit=1)
                    if len(cur_parts) == 2:
                        cur_operand = cur_parts[1].strip()
                        cur_operand_upper = cur_operand.upper()
                        if not self._is_fixed_address(cur_operand) and "TMP" not in cur_operand_upper and "(" not in cur_operand_upper:
                            j = i + 1
                            while j < len(self.code) and j < i + 20:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Stop if X is clobbered (LDX, TAX, INX, DEX, PLX)
                                if any(lookU.startswith(op) or lookU == op for op in ["LDX ", "TAX", "INX", "DEX", "PLX"]):
                                    break
                                if lookU.startswith("STX "):
                                    look_parts = look.split(maxsplit=1)
                                    if len(look_parts) == 2 and look_parts[1].strip().upper() == cur_operand_upper:
                                        skip_indices.add(j)
                                        break
                                j += 1
                
                # Elide spaced redundant STY when Y is unchanged between
                if curU.startswith("STY "):
                    cur_parts = cur.split(maxsplit=1)
                    if len(cur_parts) == 2:
                        cur_operand = cur_parts[1].strip()
                        cur_operand_upper = cur_operand.upper()
                        if not self._is_fixed_address(cur_operand) and "TMP" not in cur_operand_upper and "(" not in cur_operand_upper:
                            j = i + 1
                            while j < len(self.code) and j < i + 20:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Stop if Y is clobbered (LDY, TAY, INY, DEY, PLY)
                                if any(lookU.startswith(op) or lookU == op for op in ["LDY ", "TAY", "INY", "DEY", "PLY"]):
                                    break
                                if lookU.startswith("STY "):
                                    look_parts = look.split(maxsplit=1)
                                    if len(look_parts) == 2 and look_parts[1].strip().upper() == cur_operand_upper:
                                        skip_indices.add(j)
                                        break
                                j += 1

            # Remove orphaned register loads (LDA/LDX/LDY) when register is never used
            # Scan forward until RTS/JMP/JSR or until register is used/overwritten
            if i + 1 < len(self.code):
                cur = self.code[i].strip().upper()
                
                # Check if current instruction is a register load
                loads_a = cur.startswith("LDA ")
                loads_x = cur.startswith("LDX ")
                loads_y = cur.startswith("LDY ")
                
                if loads_a or loads_x or loads_y:
                    # Determine which register and what constitutes "use"
                    if loads_a:
                        # A is used by: STA, PHA, arithmetic (ADC, SBC, AND, OR, EOR, CMP), TAX, TAY
                        use_patterns = ["STA ", "PHA", "ADC ", "SBC ", "AND ", "EOR ", "ORA ", "CMP ", "TAX", "TAY"]
                        reload_patterns = ["LDA ", "PLA"]
                        # A is affected by indexed addressing modes
                        index_check = lambda s: ",X" in s or ",Y" in s
                    elif loads_x:
                        # X is used by: STX, INX, DEX, CPX, TXA, TXS, and indexed addressing
                        use_patterns = ["STX ", "INX", "DEX", "CPX ", "TXA", "TXS"]
                        reload_patterns = ["LDX ", "TAX", "PLX"]
                        index_check = lambda s: ",X" in s
                    else:  # loads_y
                        # Y is used by: STY, INY, DEY, CPY, TYA, and indexed addressing
                        use_patterns = ["STY ", "INY", "DEY", "CPY ", "TYA"]
                        reload_patterns = ["LDY ", "TAY", "PLY"]
                        index_check = lambda s: ",Y" in s
                    
                    # Initialize register_used
                    register_used = False
                    
                    # Quick check: if next non-comment/non-label instruction is a branch,
                    # the load is used to set flags for the branch condition
                    for k in range(i + 1, min(i + 2, len(self.code))):
                        peek = self.code[k].strip().upper()
                        if not peek or peek.endswith(":") or peek.startswith(";"):
                            continue
                        # If next instruction is a branch, the load sets the flags for it
                        if peek.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BPL ", "BMI ", "BVC ", "BVS ")):
                            register_used = True
                            break
                        # Stop at first meaningful instruction
                        break
                    
                    if register_used:
                        optimized.append(self.code[i])
                        i += 1
                        continue
                    
                    # Quick check: if next non-comment/non-label instruction is a store with indirect addressing, keep the load
                    for k in range(i + 1, min(i + 5, len(self.code))):
                        peek = self.code[k].strip().upper()
                        if not peek or peek.endswith(":") or peek.startswith(";"):
                            continue
                        # If next meaningful instruction is indirect store, preserve the load
                        if loads_a and peek.startswith("STA (") and ")" in peek:
                            register_used = True
                            break
                        if loads_x and peek.startswith("STX (") and ")" in peek:
                            register_used = True
                            break
                        if loads_y and peek.startswith("STY (") and ")" in peek:
                            register_used = True
                            break
                        # Stop at first meaningful instruction
                        break
                    
                    if register_used:
                        optimized.append(self.code[i])
                        i += 1
                        continue
                    
                    # Scan forward to see if register is used before being overwritten
                    for j in range(i + 1, len(self.code)):
                        check = self.code[j].strip().upper()
                        
                        # Skip labels and comments
                        if not check or check.endswith(":") or check.startswith(";"):
                            continue
                        
                        # Stop at control flow boundaries (register state becomes uncertain)
                        if check.startswith("JSR ") or check.startswith("JMP ") or check == "RTS" or check == "RTI":
                            break
                        
                        # Check if register is used
                        if any(check.startswith(pattern) or pattern in check for pattern in use_patterns):
                            register_used = True
                            break
                        
                        # Check for indexed addressing modes (e.g., "LDA ADDR,X")
                        if index_check(check):
                            register_used = True
                            break
                        
                        # Check if register is reloaded (makes current load orphaned)
                        if any(check.startswith(pattern) for pattern in reload_patterns):
                            # Register overwritten without being used - current load is orphaned
                            break
                    
                    # If register is never used, skip the load instruction
                    if not register_used:
                        i += 1
                        continue

            # Drop dead stores that are overwritten before any read (small window)
            cur_strip = self.code[i].strip()
            cur_upper = cur_strip.upper()
            if cur_upper.startswith("STA ") or cur_upper.startswith("STZ "):
                parts = cur_strip.split(maxsplit=1)
                if len(parts) == 2:
                    operand = parts[1].strip()
                    operand_upper = operand.upper()
                    
                    # NEVER optimize away stores to indirect addresses - they always have side effects
                    if "(" in operand and ")" in operand:
                        optimized.append(self.code[i])
                        i += 1
                        continue
                    
                    overwritten = False
                    used = False
                    j = i + 1
                    while j < len(self.code) and j < i + 20:
                        nxt = self.code[j].strip()
                        nxt_upper = nxt.upper()
                        # skip blanks / labels
                        if not nxt or nxt_upper.endswith(":"):
                            j += 1
                            continue
                        # stop at call/return
                        if nxt_upper.startswith("JSR ") or nxt_upper == "RTS" or nxt_upper.startswith("BRK"):
                            break
                        nxt_parts = nxt.split(maxsplit=1)
                        opcode = nxt_parts[0].upper()
                        opnd = nxt_parts[1].strip().upper() if len(nxt_parts) == 2 else ""
                        # detect overwrite
                        if opcode in {"STA", "STZ", "STX", "STY"} and opnd == operand_upper:
                            overwritten = True
                            break
                        # detect read
                        if opcode in {"LDA", "LDX", "LDY", "ORA", "AND", "EOR", "ADC", "SBC", "CMP", "BIT"} and opnd == operand_upper:
                            used = True
                            break
                        j += 1
                    # Only remove dead store if preceded by simple load (LDA/LDX/LDY immediate)
                    # Don't remove if it's the result of computation (checked via previous instruction)
                    if overwritten and not used:
                        # Check if this is result of computation (previous instruction modifies accumulator)
                        if i > 0:
                            prev = self.code[i - 1].strip().upper()
                            # If previous instruction is arithmetic/logic, keep the store (don't remove)
                            if any(prev.startswith(op) for op in ["ADC", "SBC", "ORA", "AND", "EOR", "ASL", "LSR", "ROL", "ROR"]):
                                # This store is result of computation; keep it to maintain code structure
                                pass
                            else:
                                # Simple assignment, safe to remove
                                i += 1
                                continue
                        else:
                            i += 1
                            continue

            # Drop dead LDA loads if A is clobbered before any read (small window)
            cur_strip = self.code[i].strip()
            cur_upper = cur_strip.upper()
            if cur_upper.startswith("LDA "):
                # Skip if implied/accumulator forms (none expected here)
                overwritten = False
                used = False
                j = i + 1
                while j < len(self.code) and j < i + 20:
                    nxt = self.code[j].strip()
                    nxt_upper = nxt.upper()
                    if not nxt or nxt_upper.endswith(":"):
                        j += 1
                        continue
                    if nxt_upper.startswith("JSR ") or nxt_upper == "RTS" or nxt_upper.startswith("BRK"):
                        break
                    nxt_parts = nxt.split()
                    if not nxt_parts:
                        j += 1
                        continue
                    opcode = nxt_parts[0].upper()
                    # Detect A overwrite
                    if opcode in {"LDA", "PLA"}:
                        overwritten = True
                        break
                    # Detect A read
                    if opcode in {"STA", "PHA", "ADC", "SBC", "ORA", "AND", "EOR", "CMP", "BIT", "TAX", "TAY"}:
                        used = True
                        break
                    j += 1
                if overwritten and not used:
                    i += 1
                    continue

            # Replace illegal 'OP X' with safe sequence using TMP4
            line_upper = self.code[i].strip().upper()
            if line_upper.endswith(" X"):
                parts = line_upper.split()
                if len(parts) == 2 and parts[1] == "X":
                    op = parts[0]
                    if op in {"ORA", "AND", "EOR", "ADC", "SBC", "CMP"}:
                        optimized.append("\tSTX TMP4")
                        optimized.append(f"\t{op} TMP4")
                        i += 1
                        continue

            # Drop unused LDX/LDY if the register is not read before a call/return or reload
            line_upper = self.code[i].strip().upper()
            if line_upper.startswith("LDX ") or line_upper.startswith("LDY "):
                is_x = line_upper.startswith("LDX ")
                used = False
                j = i + 1
                while j < len(self.code):
                    nxt = self.code[j].strip().upper()
                    # Ignore empty lines / labels
                    if not nxt or nxt.endswith(":"):
                        j += 1
                        continue
                    # Barriers: call/return/stop or reload of same register
                    if nxt.startswith("JSR ") or nxt == "JSR" or nxt == "RTS" or nxt.startswith("BRK"):
                        break
                    if (is_x and (" X" in nxt or ",X" in nxt or nxt.startswith("STX ") or nxt.startswith("TX") or nxt.startswith("INX") or nxt.startswith("DEX") or nxt.startswith("LDX "))):
                        used = True
                        break
                    if (not is_x and (" Y" in nxt or ",Y" in nxt or nxt.startswith("STY ") or nxt.startswith("TY") or nxt.startswith("INY") or nxt.startswith("DEY") or nxt.startswith("LDY "))):
                        used = True
                        break
                    j += 1
                if not used:
                    i += 1
                    continue

            if i + 1 < len(self.code):
                # 65c02: LDA #0 / STA addr → STZ addr
                if self.is_65c02:
                    c0 = self._lda_const(self.code[i])
                    if c0 == 0 and self._is_sta(self.code[i + 1]):
                        sta_parts = self.code[i + 1].strip().split(maxsplit=1)
                        if len(sta_parts) == 2:
                            optimized.append(f"\tSTZ {sta_parts[1]}")
                            i += 2
                            continue
                    
                    # 65c02: LDX #0 followed by STX → replace all STX with STZ until X is modified
                    # Pattern: LDX #0 ... STX addr1 ... STX addr2 ... (until LDX/DEX/INX/TXA/etc)
                    cur = self.code[i].strip().upper()
                    if cur == "LDX #0":
                        # Scan forward to find all STX instructions before X is modified/reloaded
                        stx_positions = []
                        j = i + 1
                        while j < len(self.code):
                            check = self.code[j].strip().upper()
                            if check.startswith("STX "):
                                # Found STX - mark for conversion to STZ
                                stx_positions.append(j)
                            elif check.startswith("LDX ") or check.startswith("DEX") or check.startswith("INX") or check.startswith("TXA"):
                                # X is modified - stop scanning
                                break
                            elif check.endswith(" X") or "TAX" in check:
                                # X is used or modified - stop scanning
                                break
                            j += 1
                            if j > i + 10:  # Limit lookahead
                                break
                        
                        # If we found STX instructions, replace them with STZ and remove LDX #0
                        if stx_positions:
                            # Skip LDX #0
                            skip_count = 1
                            for pos in range(i + 1, stx_positions[-1] + 1):
                                line = self.code[pos].strip()
                                line_upper = line.upper()
                                if pos in stx_positions:
                                    # Replace STX with STZ
                                    parts = line.split(maxsplit=1)
                                    if len(parts) == 2:
                                        optimized.append(f"\tSTZ {parts[1]}")
                                else:
                                    # Keep other instructions
                                    optimized.append(self.code[pos])
                            i = stx_positions[-1] + 1
                            continue
                    
                    # Similar pattern for LDY #0
                    if cur == "LDY #0":
                        sty_positions = []
                        j = i + 1
                        while j < len(self.code):
                            check = self.code[j].strip().upper()
                            if check.startswith("STY "):
                                sty_positions.append(j)
                            elif check.startswith("LDY ") or check.startswith("DEY") or check.startswith("INY") or check.startswith("TYA"):
                                break
                            elif check.endswith(" Y") or "TAY" in check:
                                break
                            j += 1
                            if j > i + 10:
                                break
                        
                        if sty_positions:
                            skip_count = 1
                            for pos in range(i + 1, sty_positions[-1] + 1):
                                line = self.code[pos].strip()
                                if pos in sty_positions:
                                    parts = line.split(maxsplit=1)
                                    if len(parts) == 2:
                                        optimized.append(f"\tSTZ {parts[1]}")
                                else:
                                    optimized.append(self.code[pos])
                            i = sty_positions[-1] + 1
                            continue

                inc_op = self._inc_operand(self.code[i])
                dec_op = self._dec_operand(self.code[i + 1])
                if inc_op is not None and dec_op is not None and inc_op == dec_op:
                    i += 2
                    continue

                dec_op = self._dec_operand(self.code[i])
                inc_op = self._inc_operand(self.code[i + 1])
                if dec_op is not None and inc_op is not None and dec_op == inc_op:
                    i += 2
                    continue

                # Drop no-op ADC/SBC #0 immediately after CLC/SEC when flags are safely overwritten
                if curU in ("CLC", "SEC") and nxtU.startswith(("ADC #", "SBC #")):
                    # Require literal zero (decimal or $00)
                    imm_str = nxtU.split("#", 1)[1].strip() if "#" in nxtU else ""
                    is_zero = imm_str in {"0", "$0", "$00"}
                    if is_zero:
                        k = i + 2
                        safe = False
                        while k < len(self.code) and k < i + 20:
                            look = self.code[k].strip()
                            lookU = look.upper()
                            if not look or look.endswith(":") or look.startswith(";"):
                                k += 1
                                continue
                            # Unsafe if a branch appears before flags are recomputed
                            if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ")):
                                break
                            # Safe once an arithmetic op that sets NZVC appears
                            if lookU.startswith(("ADC ", "SBC ")):
                                safe = True
                                break
                            # Stop scanning at control-flow boundaries
                            if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                break
                            k += 1
                        if safe:
                            optimized.append(self.code[i])
                            i += 2
                            continue

                # Tail call optimization: JSR followed by RTS → JMP
                cur = self.code[i].strip().upper()
                nxt = self.code[i + 1].strip().upper()
                if cur.startswith("JSR ") and nxt == "RTS":
                    # Replace JSR with JMP and skip RTS
                    target = self.code[i].strip().split(maxsplit=1)
                    if len(target) == 2:
                        optimized.append(f"\tJMP {target[1]}")
                        i += 2
                        continue

                # Drop branches that target the very next instruction (ignoring blank/comment lines)
                branch_mnems = ("BEQ", "BNE", "BCC", "BCS", "BMI", "BPL", "BVC", "BVS")
                cur_raw = self.code[i].strip()
                cur_upper = cur_raw.upper()
                if any(cur_upper.startswith(m + " ") for m in branch_mnems):
                    parts = cur_raw.split(maxsplit=1)
                    if len(parts) == 2:
                        target_label = parts[1].strip()
                        j = i + 1
                        while j < len(self.code):
                            look_raw = self.code[j]
                            look = look_raw.strip()
                            if not look or look.startswith(";"):
                                j += 1
                                continue
                            if look.endswith(":") and look[:-1].strip() == target_label:
                                # Next meaningful line is the target label → drop branch and process label next
                                i = j
                                break
                            # Found a different instruction/label first → keep branch
                            j = -1
                            break
                        if j == i:
                            continue

                # Drop TXA…TAX and TYA…TAY round-trips when flags are not observed
                cur_upper = cur
                if cur_upper in ("TXA", "TYA"):
                    j = i + 1
                    between_non_exec: list[str] = []
                    while j < len(self.code):
                        cand_raw = self.code[j]
                        cand_strip = cand_raw.strip()
                        cand_upper = cand_strip.upper()
                        if not cand_strip or cand_strip.endswith(":") or cand_strip.startswith(";"):
                            between_non_exec.append(self.code[j])
                            j += 1
                            continue
                        break
                    if j < len(self.code):
                        if (cur_upper == "TXA" and cand_upper == "TAX") or (cur_upper == "TYA" and cand_upper == "TAY"):
                            k = j + 1
                            while k < len(self.code):
                                after_raw = self.code[k].strip()
                                after_upper = after_raw.upper()
                                if not after_raw or after_raw.endswith(":") or after_raw.startswith(";"):
                                    k += 1
                                    continue
                                break
                            safe_to_drop = False
                            if k >= len(self.code):
                                safe_to_drop = True
                            else:
                                after_upper = self.code[k].strip().upper()
                                if not after_upper.startswith(("BEQ ", "BNE ", "BMI ", "BPL ", "PHP")):
                                    safe_to_drop = self._sets_nz_flags(after_upper)
                            if safe_to_drop:
                                optimized.extend(between_non_exec)
                                i = j + 1
                                continue
                
                # Collapse LDA zp + CMP #0 when followed by BEQ/BNE (Z flag comparison)
                # LDA sets Z flag; CMP #0 is redundant before BEQ/BNE
                if curU.startswith("LDA ") and not curU.startswith("LDA #"):
                    # Look ahead for CMP #0 with no Z-flag clobber in between
                    j = i + 1
                    cmp_index = -1
                    z_clobbered = False
                    while j < len(self.code) and j < i + 10:
                        look_raw = self.code[j]
                        look = look_raw.strip()
                        lookU = look.upper()
                        if not look or look.endswith(":") or look.startswith(";"):
                            j += 1
                            continue
                        # Stop at branch (uncertain control flow)
                        if lookU.startswith(("BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ")):
                            break
                        # Stop at calls/returns
                        if lookU.startswith(("JSR ", "JMP ")) or lookU in ("RTS", "RTI"):
                            break
                        # Detect CMP #0 (decimal 0 or $00)
                        if lookU.startswith("CMP #"):
                            imm_str = lookU.split("#", 1)[1].strip()
                            if imm_str in {"0", "$0", "$00"}:
                                if not z_clobbered:
                                    cmp_index = j
                            break
                        # Check if Z is clobbered
                        if self._sets_nz_flags(look):
                            z_clobbered = True
                            break
                        j += 1
                    
                    # If CMP #0 found and next instruction is BEQ/BNE, drop the CMP
                    if cmp_index != -1:
                        k = cmp_index + 1
                        while k < len(self.code):
                            next_raw = self.code[k]
                            next_inst = next_raw.strip().upper()
                            if not next_inst or next_inst.startswith(";"):
                                k += 1
                                continue
                            if next_inst.endswith(":"):
                                k += 1
                                continue
                            # Next meaningful instruction is a Z-flag branch
                            if next_inst.startswith(("BEQ ", "BNE ")):
                                skip_indices.add(cmp_index)
                            break
                
                # Short-circuit STA addr + LDA addr: drop LDA when A value not clobbered in between
                # Pattern: STA addr followed by LDA addr (same operand) with no A-clobber between
                if curU.startswith("STA "):
                    sta_parts = cur.split(maxsplit=1)
                    if len(sta_parts) == 2:
                        sta_operand = sta_parts[1].strip()
                        sta_operand_upper = sta_operand.upper()
                        # Skip if storing to fixed-address or temps (side effects)
                        if not self._is_fixed_address(sta_operand) and "TMP" not in sta_operand_upper and "(" not in sta_operand_upper:
                            j = i + 1
                            a_clobbered = False
                            lda_index = -1
                            while j < len(self.code) and j < i + 10:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                # Stop at control flow barriers
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Detect LDA addr (same operand as STA)
                                if lookU.startswith("LDA "):
                                    lda_parts = lookU.split(maxsplit=1)
                                    if len(lda_parts) == 2 and lda_parts[1].strip() == sta_operand_upper:
                                        # Found matching LDA after STA
                                        if not a_clobbered:
                                            lda_index = j
                                    break
                                # Check if A is clobbered
                                if self._clobbers_a(look):
                                    a_clobbered = True
                                    break
                                j += 1
                            
                            # If matching LDA found with A unchanged, drop the LDA
                            if lda_index != -1:
                                skip_indices.add(lda_index)
                
                # Short-circuit STX addr + LDX addr: drop LDX when X value not clobbered in between
                if curU.startswith("STX "):
                    stx_parts = cur.split(maxsplit=1)
                    if len(stx_parts) == 2:
                        stx_operand = stx_parts[1].strip()
                        stx_operand_upper = stx_operand.upper()
                        if not self._is_fixed_address(stx_operand) and "TMP" not in stx_operand_upper and "(" not in stx_operand_upper:
                            j = i + 1
                            x_clobbered = False
                            ldx_index = -1
                            while j < len(self.code) and j < i + 10:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Detect LDX addr (same operand as STX)
                                if lookU.startswith("LDX "):
                                    ldx_parts = lookU.split(maxsplit=1)
                                    if len(ldx_parts) == 2 and ldx_parts[1].strip() == stx_operand_upper:
                                        if not x_clobbered:
                                            ldx_index = j
                                    break
                                # Check if X is clobbered (LDX, TAX, INX, DEX, PLX)
                                if any(lookU.startswith(op) or lookU == op for op in ["LDX ", "TAX", "INX", "DEX", "PLX"]):
                                    x_clobbered = True
                                    break
                                j += 1
                            
                            if ldx_index != -1:
                                skip_indices.add(ldx_index)
                
                # Short-circuit STY addr + LDY addr: drop LDY when Y value not clobbered in between
                if curU.startswith("STY "):
                    sty_parts = cur.split(maxsplit=1)
                    if len(sty_parts) == 2:
                        sty_operand = sty_parts[1].strip()
                        sty_operand_upper = sty_operand.upper()
                        if not self._is_fixed_address(sty_operand) and "TMP" not in sty_operand_upper and "(" not in sty_operand_upper:
                            j = i + 1
                            y_clobbered = False
                            ldy_index = -1
                            while j < len(self.code) and j < i + 10:
                                look_raw = self.code[j]
                                look = look_raw.strip()
                                lookU = look.upper()
                                if not look or look.endswith(":") or look.startswith(";"):
                                    j += 1
                                    continue
                                if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                                    break
                                # Detect LDY addr (same operand as STY)
                                if lookU.startswith("LDY "):
                                    ldy_parts = lookU.split(maxsplit=1)
                                    if len(ldy_parts) == 2 and ldy_parts[1].strip() == sty_operand_upper:
                                        if not y_clobbered:
                                            ldy_index = j
                                    break
                                # Check if Y is clobbered (LDY, TAY, INY, DEY, PLY)
                                if any(lookU.startswith(op) or lookU == op for op in ["LDY ", "TAY", "INY", "DEY", "PLY"]):
                                    y_clobbered = True
                                    break
                                j += 1
                            
                            if ldy_index != -1:
                                skip_indices.add(ldy_index)
                
                # Drop useless INC/DEC of temps when overwritten before any read
                # Pattern: INC TMPx / DEC TMPx followed by STA TMPx before TMPx is read
                cur_strip = self.code[i].strip()
                cur_upper = cur_strip.upper()
                inc_op = self._inc_operand(cur_upper)
                dec_op = self._dec_operand(cur_upper)
                if (inc_op or dec_op) and "TMP" in (inc_op or dec_op).upper():
                    temp_name = (inc_op or dec_op).upper()
                    j = i + 1
                    is_useless = False
                    while j < len(self.code) and j < i + 20:
                        look = self.code[j].strip()
                        lookU = look.upper()
                        if not look or look.endswith(":") or look.startswith(";"):
                            j += 1
                            continue
                        # Stop at control flow boundaries
                        if lookU.startswith(("JSR ", "JMP ", "BRK")) or lookU in ("RTS", "RTI"):
                            break
                        # Check if temp is read (LDA TMPx, CMP TMPx, ADC TMPx, etc.)
                        if any(op in lookU for op in ["LDA ", "LDX ", "LDY ", "CMP ", "CPX ", "CPY ", "ORA ", "AND ", "EOR ", "ADC ", "SBC ", "BIT "]):
                            if temp_name in lookU:
                                # Temp is read; INC/DEC is not useless
                                break
                        # Check if temp is written (STA TMPx, STX TMPx, etc.) without prior read
                        if any(op in lookU for op in ["STA ", "STX ", "STY ", "STZ "]):
                            if temp_name in lookU:
                                # Temp overwritten before any read; INC/DEC is useless
                                is_useless = True
                                break
                        j += 1
                    
                    # If INC/DEC is useless (overwritten before read), skip it
                    if is_useless:
                        i += 1
                        continue
                
                # Optimize 16-bit INC/DEC by small constants
                # Pattern: INC zp / INC zp+1 repeated k times (k ≤ 3)
                #   or: DEC zp / DEC zp+1 repeated k times
                # Can consolidate into: CLC/ADC #k or repetitions of INC/DEC (already optimized above)
                # Also: INC zp / INC zp+1 when A holds low-byte and X holds high-byte
                #   → CLC / ADC #k when adding small constants
                if cur_upper.startswith(("INC ", "DEC ")):
                    op_type = cur_upper.split()[0]  # "INC" or "DEC"
                    operand = cur_upper.split(maxsplit=1)[1] if " " in cur_upper else ""
                    
                    # Look ahead for matching operations on zp and zp+1
                    j = i + 1
                    inc_dec_count = 1
                    has_16bit_pattern = False
                    
                    # Scan for pattern: INC zp / INC zp+1 (or DEC)
                    while j < len(self.code) and j < i + 10 and inc_dec_count <= 3:
                        look = self.code[j].strip()
                        lookU = look.upper()
                        
                        if not look or look.endswith(":") or look.startswith(";"):
                            j += 1
                            continue
                        
                        if lookU.startswith(op_type + " "):
                            next_operand = lookU.split(maxsplit=1)[1] if " " in lookU else ""
                            # Check if this is part of 16-bit sequence
                            if next_operand == operand:
                                # Same operand, could be repetition (for small k, just repeat INC)
                                inc_dec_count += 1
                                j += 1
                                continue
                            # Check for adjacent zp operand (e.g., INC $80 / INC $81)
                            if operand and next_operand:
                                # Try to parse as hex addresses
                                try:
                                    curr_addr = int(operand, 16) if operand.startswith("$") else None
                                    next_addr = int(next_operand, 16) if next_operand.startswith("$") else None
                                    if curr_addr is not None and next_addr is not None and next_addr == curr_addr + 1:
                                        # Found 16-bit pattern: INC $80 / INC $81
                                        has_16bit_pattern = True
                                        inc_dec_count += 1
                                        j += 1
                                        continue
                                except (ValueError, TypeError):
                                    pass
                        
                        # Stop at control flow or other instruction types
                        if lookU.startswith(("JMP ", "JSR ", "BEQ ", "BNE ", "BCC ", "BCS ", "BMI ", "BPL ", "BVC ", "BVS ", "BRK")) or lookU in ("RTS", "RTI"):
                            break
                        
                        # Stop at any non-INC/DEC instruction (except labels/comments)
                        if not lookU.startswith(op_type + " "):
                            break
                        
                        j += 1
                    
                    # Consolidate if we found 16-bit pattern with count ≤ 3
                    if has_16bit_pattern and inc_dec_count <= 3:
                        # For now, keep the original sequence (already optimal)
                        # In the future, could emit: CLC / ADC #k if A and X constraints are met
                        pass
                
                # Optimize TAY ... TYA STA addr → STA addr ... (when A is modified between but not used)
                # Pattern: TAY, (instructions that modify A), TYA, STA addr
                # Can be replaced with: STA addr, (instructions without TYA)
                if cur == "TAY":
                    # Look ahead for TYA followed by STA
                    j = i + 1
                    found_tya_sta = False
                    tya_index = -1
                    while j < len(self.code) and j < i + 10:  # Limit lookahead
                        look = self.code[j].strip().upper()
                        if not look or look.endswith(":") or look.startswith(";"):
                            j += 1
                            continue
                        if look == "TYA":
                            # Check if next instruction is STA
                            k = j + 1
                            while k < len(self.code):
                                next_look = self.code[k].strip().upper()
                                if not next_look or next_look.endswith(":") or next_look.startswith(";"):
                                    k += 1
                                    continue
                                if next_look.startswith("STA "):
                                    found_tya_sta = True
                                    tya_index = j
                                break
                            break
                        # Stop if Y is used or modified (other than TYA)
                        if any(op in look for op in ["INY", "DEY", "CPY ", "STY ", ",Y", " Y"]):
                            break
                        j += 1
                    
                    if found_tya_sta:
                        # Find the STA instruction after TYA
                        sta_index = tya_index + 1
                        while sta_index < len(self.code):
                            if not self.code[sta_index].strip() or self.code[sta_index].strip().endswith(":") or self.code[sta_index].strip().startswith(";"):
                                sta_index += 1
                                continue
                            break
                        
                        # Emit STA first (store original A)
                        optimized.append(self.code[sta_index])
                        # Skip TAY, emit intermediate instructions, skip TYA, skip STA
                        i += 1  # Skip TAY
                        while i < tya_index:
                            optimized.append(self.code[i])
                            i += 1
                        i = sta_index + 1  # Skip TYA and STA
                        continue
                
                # Optimize TAX ; STX addr → STA addr (when X is not needed)
                if cur == "TAX" and nxt.startswith("STX "):
                    # Check if X is used between TAX and STX (it shouldn't be - they're consecutive)
                    # and check if X is needed after the STX (before being overwritten)
                    # For safety, we'll only optimize if the next instruction after STX is:
                    # - JSR (which will likely overwrite X)
                    # - LDX (which overwrites X)
                    # - or another instruction that doesn't read X
                    stx_operand = nxt[4:].strip()  # Get operand from "STX addr"
                    safe_to_optimize = False
                    
                    # Check what comes after STX
                    if i + 2 < len(self.code):
                        k = i + 2
                        while k < len(self.code):
                            next_inst = self.code[k].strip().upper()
                            if not next_inst or next_inst.endswith(":") or next_inst.startswith(";"):
                                k += 1
                                continue
                            # Safe if X is immediately overwritten or not used
                            if next_inst.startswith(("JSR ", "LDX ", "TAX", "TSX", "PLA", "TYA")) or next_inst == "RTS":
                                safe_to_optimize = True
                            break
                    else:
                        # End of code, safe to optimize
                        safe_to_optimize = True
                    
                    if safe_to_optimize:
                        # Replace TAX; STX addr with STA addr
                        optimized.append(f"\tSTA {stx_operand}")
                        i += 2
                        continue

            if i + 3 < len(self.code):
                c0 = self._lda_const(self.code[i])
                c1 = self._lda_const(self.code[i + 2])
                if c0 is not None and c0 == c1 and self._is_sta(self.code[i + 1]) and self._is_sta(self.code[i + 3]):
                    optimized.append(self.code[i])
                    optimized.append(self.code[i + 1])
                    optimized.append(self.code[i + 3])
                    i += 4
                    continue

            optimized.append(self.code[i])
            i += 1

        self.code = optimized

        # Second pass: remove loads immediately overwritten by a subsequent load (skip blanks/labels)
        # NEVER optimize loads from fixed-address (hardware) variables
        cleaned: list[str] = []
        i = 0
        while i < len(self.code):
            if i + 1 < len(self.code):
                cur = self.code[i]
                curU = cur.strip().upper()
                if curU.startswith(("LDA ", "LDX ", "LDY ")):
                    # Check if this is a fixed-address load
                    cur_parts = curU.split(maxsplit=1)
                    cur_operand = cur_parts[1].strip() if len(cur_parts) == 2 else ""
                    if self._is_fixed_address(cur_operand):
                        # Never optimize fixed-address loads
                        cleaned.append(cur)
                        i += 1
                        continue
                    
                    k = i + 1
                    pending_non_exec: list[str] = []
                    while k < len(self.code):
                        nxt_raw = self.code[k]
                        nxt = nxt_raw.strip()
                        nxtU = nxt.upper()
                        # Skip blanks, labels, and comments (lines starting with ';')
                        if not nxt or nxt.endswith(":") or nxt.startswith(";"):
                            pending_non_exec.append(self.code[k])
                            k += 1
                            continue
                        if (curU.startswith("LDA ") and nxtU.startswith("LDA ")) or \
                           (curU.startswith("LDX ") and nxtU.startswith("LDX ")) or \
                           (curU.startswith("LDY ") and nxtU.startswith("LDY ")):
                            # Keep first load, drop subsequent redundant load, preserve comments/labels between
                            cleaned.append(cur)
                            cleaned.extend(pending_non_exec)
                            i = k + 1  # Skip the redundant load
                            break
                        else:
                            break
                    else:
                        cleaned.append(cur)
                        i += 1
                        continue
                    # If we skipped redundant load, restart loop
                    if i == k + 1:
                        continue
                cleaned.append(cur)
                i += 1
            else:
                cleaned.append(self.code[i])
                i += 1
        self.code = cleaned

    def legalize_illegal_ops(self):
        """Ensure emitted code is assemblable even without peephole optimizations.

        Currently replaces illegal 'OP X' sequences with a safe temp-based variant.
        """
        legalized: list[str] = []
        i = 0
        while i < len(self.code):
            line_upper = self.code[i].strip().upper()
            if line_upper.endswith(" X"):
                parts = line_upper.split()
                if len(parts) == 2 and parts[1] == "X":
                    op = parts[0]
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
        saved = self.code
        self.code = []
        self.gen_vars(procs, funcs, code=saved)
        vars_block = self.code
        self.code = saved
        return vars_block

    def _declare_temp(self, name: str):
        sym = Symbol(
            name=name,
            type=SemType("WORD", False),
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
        target = getattr(self.current_symtab, "local", None)
        if target is None:
            target = self.current_symtab
        # attach procedure name if available for proper ASM naming
        proc_name = getattr(target, "_proc_name", "")
        if proc_name:
            sym.proc_name = proc_name
        target._symbols[sym.name] = sym
        return sym


    def gen_file_header(self):
        self.emit("; Generated by Zap Compiler")
        cmd = self.command_line if self.command_line else "(command line not provided)"
        self.emit(f"; Command: {cmd}")
        if self.pruned_procs:
            removed = ", ".join(sorted(self.pruned_procs))
            self.emit(f"; Optimized out unused procedures (definitions and calls removed): {removed}")
        self.emit("; ------------------------------\n")
        #self.emit(".include \"macros.inc\"")
        #self.emit(".include \"variables.inc\"\n")

    def gen_file_footer(self):
        # Ensure runtime helpers and data live in CODE segment
        self.emit("\n.segment \"CODE\"")
        self._gen_copy_bytes_routine()
        self._gen_string_data()
        self._gen_math_routines()
        self.emit("__END:")
        self.emit(".export __END")
        self.emit("\n; End of file")

    def _gen_copy_bytes_routine(self):
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
    
    def _gen_string_data(self):
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
    
    def _gen_math_routines(self):
        """Generate runtime math routines for *, /, %"""
        if not self.math_routines_needed:
            return

        needed = set(self.math_routines_needed)
        # Include dependencies (MUL16_8 uses MUL8)
        if "MUL16_8" in needed:
            needed.add("MUL8")

        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        def emit_mul8():
            self.emit("; MUL8: 8x8=16 multiply")
            self.emit("; Input: TMP0 (multiplicand), TMP2 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL8:")
            self.emit("\tLDA #0")
            self.emit("\tLDX #8")
            self.emit("\tCLC")
            self.emit("MUL8_LOOP:")
            self.emit("\tROR TMP2")
            self.emit("\tBCC MUL8_SKIP")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("MUL8_SKIP:")
            self.emit("\tROR")
            self.emit("\tROR TMP3")
            self.emit("\tDEX")
            self.emit("\tBNE MUL8_LOOP")
            self.emit("\tTAX")
            self.emit("\tLDA TMP3")
            self.emit("\tRTS")

        def emit_mul16_8():
            self.emit("; MUL16_8: 16x8=16 multiply")
            self.emit("; Input: TMP0,TMP1 (multiplicand), TMP2 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL16_8:")
            self.emit("\tLDA TMP0")
            self.emit("\tSTA TMP3")
            self.emit("\tLDA TMP1")
            self.emit("\tPHA")
            self.emit("\tLDA TMP2")
            self.emit("\tSTA TMP0")
            self.emit("\tLDA TMP3")
            self.emit("\tSTA TMP2")
            self.emit("\tJSR MUL8")
            self.emit("\tSTA TMP3")
            self.emit("\tSTX TMP0")
            self.emit("\tPLA")
            self.emit("\tSTA TMP2")
            self.emit("\tJSR MUL8")
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tTAX")
            self.emit("\tLDA TMP3")
            self.emit("\tRTS")

        def emit_mul16():
            self.emit("; MUL16: 16x16=16 multiply")
            self.emit("; Input: TMP0,TMP1 (multiplicand), TMP2,TMP3 (multiplier)")
            self.emit("; Output: A=low, X=high")
            self.emit("MUL16:")
            self._stz("TMP2+2")  # Use TMP2+2 as temp storage
            self.emit("\tLDX #16")
            self.emit("MUL16_LOOP:")
            self.emit("\tLSR TMP3")
            self.emit("\tROR TMP2")
            self.emit("\tBCC MUL16_SKIP")
            self.emit("\tCLC")
            self.emit("\tLDA TMP2+2")
            self.emit("\tADC TMP0")
            self.emit("\tSTA TMP2+2")
            self.emit("\tLDA TMP2+3")
            self.emit("\tADC TMP1")
            self.emit("\tSTA TMP2+3")
            self.emit("MUL16_SKIP:")
            self.emit("\tROR TMP2+3")
            self.emit("\tROR TMP2+2")
            self.emit("\tDEX")
            self.emit("\tBNE MUL16_LOOP")
            self.emit("\tLDA TMP2+2")
            self.emit("\tLDX TMP2+3")
            self.emit("\tRTS")

        def emit_div8():
            self.emit("; DIV8: 8/8=8 divide")
            self.emit("; Input: TMP0 (dividend), TMP2 (divisor)")
            self.emit("; Output: A=quotient, X=0")
            self.emit("DIV8:")
            self.emit("\tLDA #0")
            self.emit("\tLDX #8")
            self.emit("\tCLC")
            self.emit("DIV8_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL")
            self.emit("\tCMP TMP2")
            self.emit("\tBCC DIV8_SKIP")
            self.emit("\tSBC TMP2")
            self.emit("DIV8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV8_LOOP")
            self.emit("\tROL TMP0")
            self.emit("\tLDA TMP0")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_div16_8():
            self.emit("; DIV16_8: 16/8=16 divide")
            self.emit("; Input: TMP0,TMP1 (dividend), TMP2 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("DIV16_8:")
            self._stz("TMP3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("DIV16_8_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP3")
            self.emit("\tLDA TMP3")
            self.emit("\tCMP TMP2")
            self.emit("\tBCC DIV16_8_SKIP")
            self.emit("\tSBC TMP2")
            self.emit("\tSTA TMP3")
            self.emit("DIV16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_8_LOOP")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tLDA TMP0")
            self.emit("\tLDX TMP1")
            self.emit("\tRTS")

        def emit_div8_16():
            self.emit("; DIV8_16: 8/16=8 divide")
            self.emit("; Input: TMP0 (dividend), TMP2,TMP3 (divisor)")
            self.emit("; Output: A=quotient (0 or 1), X=0")
            self.emit("DIV8_16:")
            self.emit("\tLDA TMP0")
            self.emit("\tCMP TMP2")
            self.emit("\tLDA #0")
            self.emit("\tSBC TMP3")
            self.emit("\tBCC DIV8_16_ZERO")
            self.emit("\tLDA #1")
            self.emit("\tLDX #0")
            self.emit("\tRTS")
            self.emit("DIV8_16_ZERO:")
            self.emit("\tLDA #0")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_div16():
            self.emit("; DIV16: 16/16=16 divide")
            self.emit("; Input: TMP0,TMP1 (dividend), TMP2,TMP3 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("DIV16:")
            self._stz("TMP2+2")
            self._stz("TMP2+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("DIV16_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2+2")
            self.emit("\tROL TMP2+3")
            self.emit("\tLDA TMP2+2")
            self.emit("\tCMP TMP2")
            self.emit("\tLDA TMP2+3")
            self.emit("\tSBC TMP3")
            self.emit("\tBCC DIV16_SKIP")
            self.emit("\tLDA TMP2+2")
            self.emit("\tSBC TMP2")
            self.emit("\tSTA TMP2+2")
            self.emit("\tLDA TMP2+3")
            self.emit("\tSBC TMP3")
            self.emit("\tSTA TMP2+3")
            self.emit("DIV16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE DIV16_LOOP")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tLDA TMP0")
            self.emit("\tLDX TMP1")
            self.emit("\tRTS")

        def emit_mod8():
            self.emit("; MOD8: 8%8=8 modulo")
            self.emit("; Input: TMP0 (dividend), TMP2 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD8:")
            self.emit("\tLDA #0")
            self.emit("\tLDX #8")
            self.emit("\tCLC")
            self.emit("MOD8_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL")
            self.emit("\tCMP TMP2")
            self.emit("\tBCC MOD8_SKIP")
            self.emit("\tSBC TMP2")
            self.emit("MOD8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD8_LOOP")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_mod16_8():
            self.emit("; MOD16_8: 16%8=8 modulo")
            self.emit("; Input: TMP0,TMP1 (dividend), TMP2 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD16_8:")
            self._stz("TMP3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_8_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP3")
            self.emit("\tLDA TMP3")
            self.emit("\tCMP TMP2")
            self.emit("\tBCC MOD16_8_SKIP")
            self.emit("\tSBC TMP2")
            self.emit("\tSTA TMP3")
            self.emit("MOD16_8_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_8_LOOP")
            self.emit("\tLDA TMP3")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_mod8_16():
            self.emit("; MOD8_16: 8%16=8 modulo")
            self.emit("; Input: TMP0 (dividend), TMP2,TMP3 (divisor)")
            self.emit("; Output: A=remainder, X=0")
            self.emit("MOD8_16:")
            self.emit("\tLDA TMP0")
            self.emit("\tCMP TMP2")
            self.emit("\tLDA #0")
            self.emit("\tSBC TMP3")
            self.emit("\tBCC MOD8_16_RET")
            self.emit("\tLDA TMP0")
            self.emit("\tSBC TMP2")
            self.emit("\tLDX #0")
            self.emit("\tRTS")
            self.emit("MOD8_16_RET:")
            self.emit("\tLDA TMP0")
            self.emit("\tLDX #0")
            self.emit("\tRTS")

        def emit_mod16():
            self.emit("; MOD16: 16%16=16 modulo")
            self.emit("; Input: TMP0,TMP1 (dividend), TMP2,TMP3 (divisor)")
            self.emit("; Output: A=low, X=high")
            self.emit("MOD16:")
            self._stz("TMP2+2")
            self._stz("TMP2+3")
            self.emit("\tLDX #16")
            self.emit("\tCLC")
            self.emit("MOD16_LOOP:")
            self.emit("\tROL TMP0")
            self.emit("\tROL TMP1")
            self.emit("\tROL TMP2+2")
            self.emit("\tROL TMP2+3")
            self.emit("\tLDA TMP2+2")
            self.emit("\tCMP TMP2")
            self.emit("\tLDA TMP2+3")
            self.emit("\tSBC TMP3")
            self.emit("\tBCC MOD16_SKIP")
            self.emit("\tLDA TMP2+2")
            self.emit("\tSBC TMP2")
            self.emit("\tSTA TMP2+2")
            self.emit("\tLDA TMP2+3")
            self.emit("\tSBC TMP3")
            self.emit("\tSTA TMP2+3")
            self.emit("MOD16_SKIP:")
            self.emit("\tDEX")
            self.emit("\tBNE MOD16_LOOP")
            self.emit("\tLDA TMP2+2")
            self.emit("\tLDX TMP2+3")
            self.emit("\tRTS")

        emitters = [
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


    def gen_var_header(self):
        self.emit("; Variables")
        self.emit("; ------------------------------")   

    def _detect_temp_usage(self, code: list[str] | None = None) -> set[str]:
        """Scan generated code for temp usage and combine with flagged temps."""
        temp_names = {"TMP0", "TMP1", "TMP2", "TMP3", "TMP4"}
        temps = set(self.used_temps)
        code = self.code if code is None else code

        if self.copy_bytes_needed or self.math_routines_needed:
            temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        for line in code:
            for name in temp_names:
                if name in line:
                    temps.add(name)
        if code and not temps.intersection({"TMP0", "TMP1"}):
            temps.update({"TMP0", "TMP1"})
        return temps

    def gen_vars(self, procs=None, funcs=None, code: list[str] | None = None):
        temp_sizes = {"TMP0": 2, "TMP1": 2, "TMP2": 4, "TMP3": 2, "TMP4": 1}
        temps_in_use = self._detect_temp_usage(code)

        self.emit(".segment \"ZEROPAGE\"")
        self.emit("; System variables")
        for name in ["TMP0", "TMP1", "TMP2", "TMP3", "TMP4"]:
            if name in temps_in_use:
                size = temp_sizes[name]
                self.emit(f"{name}:\t.res {size}")
        self.emit("")

        # Collect all variables (globals + locals from procs and funcs)
        all_vars = list(self.global_symtab)
        if procs:
            for proc in procs:
                # include analyzed locals
                all_vars.extend(proc.locals)
                # include any temps declared during codegen in the scoped local table
                local_tbl = getattr(proc.symtab, "local", None)
                if local_tbl is not None:
                    all_vars.extend(list(local_tbl))
        if funcs:
            for func in funcs:
                all_vars.extend(func.locals)

        # Deduplicate by ASM name to avoid double emission
        uniq: dict[str, Symbol] = {}
        for s in all_vars:
            uniq[s.asm_name()] = s
        all_vars = list(uniq.values())

        fixed = [s for s in all_vars if getattr(s, "address", None) is not None]
        if fixed:
            self.emit("; Fixed-address variables")
            for sym in fixed:
                self.emit(f"{sym.asm_name()} = ${sym.address:04X}")
                # Track fixed-address labels to prevent peephole optimization
                self.fixed_address_labels.add(sym.asm_name())
            self.emit("")

        # Zero page offset tracking (starts after emitted system variables)
        zp_offset = sum(temp_sizes[n] for n in temps_in_use)
        ZEROPAGE_SIZE = 256
        
        # Step 1: ALL POINTERS MUST fit in zero page - fail if they don't
        pointers = [s for s in all_vars if not s.is_const and s.address is None and s.type.is_pointer]
        if pointers:
            self.emit("; Pointer variables")
            for sym in pointers:
                if zp_offset + 2 > ZEROPAGE_SIZE:
                    self._raise_error(f"Zero page exhausted: pointer '{sym.name}' cannot fit (need {zp_offset + 2} bytes)")
                self.emit(f"{sym.asm_name()}:\t.res 2")
                zp_offset += 2
        
        # Step 2: Try to put BYTE variables in zero page, overflow to BSS
        byte_vars = [s for s in all_vars 
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
        word_vars = [s for s in all_vars 
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
        
        # Step 4: ALL ARRAYS must go to BSS segment (always)
        array_vars = [s for s in all_vars if not s.is_const and s.address is None and s.is_array]
        
        # Switch to BSS for overflow and arrays
        if bss_byte_vars or bss_word_vars or array_vars:
            self.emit("\n.segment \"BSS\"")
            
            if bss_byte_vars:
                self.emit("; Byte variables (BSS)")
                for sym in bss_byte_vars:
                    self.emit(f"{sym.asm_name()}:\t.res 1")
            
            if bss_word_vars:
                self.emit("; Word variables (BSS)")
                for sym in bss_word_vars:
                    self.emit(f"{sym.asm_name()}:\t.res 2")
            
            if array_vars:
                self.emit("; Array variables (BSS)")
                for sym in array_vars:
                    size = sym.array_len if sym.array_len else 1
                    # Multiply by element size: WORD arrays need 2 bytes per element
                    element_size = 2 if sym.type.base == "WORD" else 1
                    total_size = size * element_size
                    self.emit(f"{sym.asm_name()}:\t.res {total_size}")

    def gen_globals_header(self):
        self.emit("\n.segment \"CODE\"")
        self.emit("; Globals initialization")
        self.emit("; ------------------------------") 
        self.emit("__START:")
        self.emit(".export __START")
               

    def gen_globals_footer(self):
        self.emit("\n; Call MAIN")
        self.emit("; ------------------------------")        
        self.emit("\tJSR MAIN")       
        self.emit("\tJMP *\n")       

    def gen_init(self, sym: Symbol):
        # Skip unused globals (locals handled elsewhere)
        # Exception: always initialize fixed-address variables (hardware ports) and variables with initializers
        if sym.proc_name == "" and sym.name not in self.used_globals and sym.address is None and sym.init is None:
            return
        if sym.is_const:
            return
        if sym.init is None:
            return

        # Emit source comment for variable initializers
        if sym.proc_name:
            self.emit_src_comment_for_local(sym.proc_name, sym.name)
        else:
            self.emit_src_comment_for_global(sym.name)

        if isinstance(sym.init, ExprInit):
            # Immediate initializer
            if isinstance(sym.init.expr, IntLiteral):
                val = sym.init.expr.value & 0xFFFF
                if sym.type.base == "BYTE" and not sym.type.is_pointer:
                    self._emit_store_byte_const(sym, val)
                else:  # WORD or pointer → store both bytes
                    self._emit_store_word_const(sym, val)
                return

            # Fallback: general expression (non-const)
            self.gen_expr(sym.init.expr)
            if sym.type.base == "BYTE" and not sym.type.is_pointer:
                self.emit(f"\tSTA {sym.asm_name()}")
            else:
                self.emit(f"\tSTA {sym.asm_name()}")
                self.emit(f"\tSTX {sym.asm_name()}+1")
            return

        if isinstance(sym.init, StringInit):
            content = sym.init.value
            str_len = len(content) + 1  # Include null terminator
            dest_var = sym.asm_name()
            is_word = sym.type.base == "WORD"
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space
            
            # Optimized string copy using loop
            # For very short strings (1-2 chars), inline is better
            if str_len <= 3:
                # Inline for very short strings (no string data needed)
                for i, ch in enumerate(content.encode('ascii')):
                    elem_offset = i * 2 if is_word else i
                    self.emit(f"\tLDA #${ch:02X}")
                    self.emit(f"\tSTA {dest_var}+{elem_offset}")
                    if is_word:
                        self.emit(f"\tLDX #0")
                        self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
                # Add null terminator
                term_offset = len(content) * (2 if is_word else 1)
                self.emit(f"\tLDA #0")
                self.emit(f"\tSTA {dest_var}+{term_offset}")
                if is_word:
                    self.emit(f"\tLDX #0")
                    self.emit(f"\tSTX {dest_var}+{term_offset}+1")
            elif str_len > COPY_THRESHOLD and str_len <= 255:
                # Use shared copy routine for larger strings (fits in one page)
                if content not in self.string_literals:
                    self.string_id += 1
                    self.string_literals[content] = f"STR_DATA_{self.string_id}"
                str_label = self.string_literals[content]
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
                copy_len = str_len * (2 if is_word else 1)
                self.emit(f"\tLDX #{copy_len}")
                self.emit("\tLDY #0")
                self.emit("\tJSR COPY_BYTES")
            else:
                # Use loop for longer strings - get or create label
                if content not in self.string_literals:
                    self.string_id += 1
                    self.string_literals[content] = f"STR_DATA_{self.string_id}"
                
                str_label = self.string_literals[content]
                self.emit(f"\t; Copy string \"{content[:20]}{'...' if len(content) > 20 else ''}\" ({str_len} bytes)")
                
                if is_word:
                    # For WORD arrays, each character needs to be loaded into a WORD (2 bytes)
                    self.emit(f"\tLDX #0")
                    copy_loop = self.new_label("STR_COPY")
                    self.emit(f"{copy_loop}:")
                    self.emit(f"\tLDA {str_label},X")  # Load low byte (char)
                    self.emit(f"\tSTA {dest_var},X")   # Store to even offset
                    self.emit(f"\tBEQ {copy_loop}_DONE")  # Stop at null terminator
                    self.emit(f"\tLDA #0")             # High byte is 0
                    self.emit(f"\tSTA {dest_var}+1,X")
                    self.emit(f"\tINX")
                    self.emit(f"\tINX")                # Increment by 2 for WORD
                    self.emit(f"\tCPX #{str_len * 2}")
                    self.emit(f"\tBNE {copy_loop}")
                    self.emit(f"{copy_loop}_DONE:")
                else:
                    self.emit(f"\tLDX #0")
                    copy_loop = self.new_label("STR_COPY")
                    self.emit(f"{copy_loop}:")
                    self.emit(f"\tLDA {str_label},X")
                    self.emit(f"\tSTA {dest_var},X")
                    self.emit(f"\tBEQ {copy_loop}_DONE")  # Stop at null terminator
                    self.emit(f"\tINX")
                    self.emit(f"\tCPX #{str_len}")
                    self.emit(f"\tBNE {copy_loop}")
                    self.emit(f"{copy_loop}_DONE:")
            return

        if isinstance(sym.init, ListInit):
            # Check if all values are constant integers
            is_const_array = all(isinstance(ex, IntLiteral) for ex in sym.init.values)
            
            if not is_const_array:
                # Non-constant values - use old method
                for i, ex in enumerate(sym.init.values):
                    self.gen_expr(ex)
                    elem_offset = i * 2 if sym.type.base == "WORD" else i
                    self.emit(f"\tSTA {sym.asm_name()}+{elem_offset}")
                    if sym.type.base == "WORD":
                        self.emit(f"\tSTX {sym.asm_name()}+{elem_offset}+1")
                return
            
            # Constant array - optimize with loop copy
            # Type narrowing: we've verified all elements are IntLiteral above
            values = [ex.value for ex in sym.init.values if isinstance(ex, IntLiteral)]
            array_len = len(values)
            is_word = sym.type.base == "WORD"
            dest_var = sym.asm_name()
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space
            
            # For very short arrays (1-2 elements), inline is better
            if array_len <= 2:
                # Inline for very short arrays
                for i, ex in enumerate(sym.init.values):
                    self.gen_expr(ex)
                    elem_offset = i * 2 if is_word else i
                    self.emit(f"\tSTA {dest_var}+{elem_offset}")
                    if is_word:
                        self.emit(f"\tSTX {dest_var}+{elem_offset}+1")
            else:
                # Use loop for longer arrays
                # Create unique key for this array data
                data_key = (tuple(values), is_word)
                if data_key not in self.array_literals:
                    self.array_id += 1
                    self.array_literals[data_key] = f"ARRAY_DATA_{self.array_id}"
                
                arr_label = self.array_literals[data_key]
                elem_size = 2 if is_word else 1
                total_bytes = array_len * elem_size
                use_shared = total_bytes > COPY_THRESHOLD and total_bytes <= 255

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
                    copy_loop = self.new_label("ARR_COPY")
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

        raise NotImplementedError("Complex init")


    def emit(self, line: str):
        self.code.append(line)

    def emit_src_comment_for_stmt(self, stmt):
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

    def emit_src_comment_for_local(self, proc_name: str, var_name: str):
        info = self.local_decl_src.get((proc_name, var_name))
        if info:
            fname, line, col, text = info
            self.emit(f"; {fname} {line}: {text}")

    def emit_src_comment_for_global(self, var_name: str):
        info = self.global_decl_src.get(var_name)
        if info:
            fname, line, col, text = info
            self.emit(f"; {fname} {line}: {text}")

    def _raise_error(self, msg: str):
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
            raise SemanticError(msg)

    def _load_sym_addr(self, sym_name: str):
        self.emit(f"\tLDA #<{sym_name}")
        self.emit(f"\tLDX #>{sym_name}")

    def _gen_literal(self, expr: IntLiteral):
        t = self.tc_check(expr)
        val = expr.value
        self.emit(f"\tLDA #{val & 0xFF}")
        # self.emit(f'; {t}')
        if t.sem_type.base == "WORD":
            self.emit(f"\tLDX #{(val >> 8) & 0xFF}")


    def _gen_identifier(self, expr: Identifier):
        t = self.tc_check(expr)
        sym = self.current_symtab.lookup(expr.name)

        if sym.is_const:
            if sym.const_value is None:
                self._raise_error(f"Constant '{sym.name}' has no value")
            # Use the symbol's declared type, not the inferred literal type
            val = sym.const_value
            self.emit(f"\tLDA #{val & 0xFF}")
            # Pointers are always word-sized even when base type is BYTE
            if sym.type.base == "WORD" or sym.type.is_pointer:
                self.emit(f"\tLDX #{(val >> 8) & 0xFF}")
            return

        # ADDR (pointer nebo pole)
        if t.kind == ExprKind.ADDR:
            if sym.type.is_pointer and not sym.is_array:
                # Load pointer value stored in the variable (A=low, X=high)
                asm = sym.asm_name()
                self.emit(f"\tLDA {asm}")
                self.emit(f"\tLDX {asm}+1")
            else:
                # Arrays decay to their address
                self._load_sym_addr(sym.asm_name())
            return

        # VALUE
        asm = sym.asm_name()
        self.emit(f"\tLDA {asm}")
        if t.sem_type.base == "WORD":
            self.emit(f"\tLDX {asm}+1")
        else:
            # BYTE → X = 0
            self.emit("\tLDX #0")

    def _gen_deref(self, expr: DerefExpr):
        t = self.tc_check(expr)

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

    def _gen_subscript(self, expr: SubscriptExpr, load_only: bool):
        # only support array identifiers
        if not isinstance(expr.array, Identifier):
            self._raise_error("Subscript array must be identifier")

        sym = self.current_symtab.lookup(expr.array.name)
        width = 2 if sym.type.base == "WORD" else 1

        # base address -> TMP0/TMP0+1
        self._load_sym_addr(sym.asm_name())
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")

        # index
        self.gen_expr(expr.index)
        
        # For WORD arrays, multiply index by 2 FIRST before adding to base
        if width == 2:
            # multiply index by 2 (simple shift left: ASL shifts A left, sets C if overflow)
            self.emit("\tASL A")
            # If carry was set from the shift, we need to propagate it
            carry_lbl = self.new_label("NOCARRY_SUBSCRIPT")
            self.emit(f"\tBCC {carry_lbl}")
            # Carry set - we'll add 1 to high byte during the add
            self.emit(f"{carry_lbl}:")
        
        # Now add (multiplied) index to base address
        self.emit("\tCLC")
        self.emit("\tADC TMP0")
        self.emit("\tSTA TMP0")
        
        # Handle carry into high byte
        carry_lbl2 = self.new_label("CARRY")
        self.emit(f"\tBCC {carry_lbl2}")
        self.emit("\tINC TMP0+1")
        self.emit(f"{carry_lbl2}:")

        if load_only:
            self.emit("\tLDY #0")
            self.emit("\tLDA (TMP0),Y")
            if width == 2:
                self.emit("\tINY")
                self.emit("\tLDA (TMP0),Y")
                self.emit("\tTAX")
            else:
                self.emit("\tLDX #0")
        else:
            # RHS value in TMP2/TMP2+1 (saved before calling this method)
            self.emit("\tLDY #0")
            self.emit("\tLDA TMP2")
            self.emit("\tSTA (TMP0),Y")
            if width == 2:
                self.emit("\tINY")
                self.emit("\tLDA TMP2+1")
                self.emit("\tSTA (TMP0),Y")

    def _gen_binary(self, expr: BinaryExpr):
        t = self.tc_check(expr)
        left_t = self.tc_check(expr.left)
        right_t = self.tc_check(expr.right)
        
        # Determine operand sizes
        left_16 = left_t.sem_type.base == "WORD"
        right_16 = right_t.sem_type.base == "WORD"
        result_16 = t.sem_type.base == "WORD"
        
        # Detect pointer arithmetic: determine if this is pointer +/- value
        left_is_ptr = left_t.kind == ExprKind.ADDR
        right_is_ptr = right_t.kind == ExprKind.ADDR
        
        # For pointer arithmetic, we need the element size of the pointer
        ptr_elem_size = 1  # default
        if left_is_ptr:
            ptr_elem_size = 2 if left_t.sem_type.base == "WORD" else 1
        elif right_is_ptr:
            ptr_elem_size = 2 if right_t.sem_type.base == "WORD" else 1

        # Check for constant 1 optimization BEFORE generating code
        right_is_const_1 = isinstance(expr.right, IntLiteral) and expr.right.value == 1
        use_inc_opt = (expr.op == BinOp.ADD and right_is_const_1 and left_is_ptr and ptr_elem_size == 1 and not result_16)
        use_dec_opt = (expr.op == BinOp.SUB and right_is_const_1 and left_is_ptr and ptr_elem_size == 1)

        # Generate left operand
        self.gen_expr(expr.left)
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")

        # Generate right operand (skip for INC/DEC optimization on BYTE pointers)
        if not (use_inc_opt or use_dec_opt):
            self.gen_expr(expr.right)
        
        # Handle different operations
        if expr.op == BinOp.ADD:
            self._gen_add(result_16, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, use_inc_opt)
        elif expr.op == BinOp.SUB:
            self._gen_sub(result_16, ptr_elem_size if (left_is_ptr or right_is_ptr) else 1, use_dec_opt)
        elif expr.op == BinOp.MUL:
            self._gen_mul(left_16, right_16, result_16)
        elif expr.op == BinOp.DIV:
            self._gen_div(left_16, right_16, result_16)
        elif expr.op == BinOp.MOD:
            self._gen_mod(left_16, right_16, result_16)
    
    def _gen_add(self, is_16bit: bool, ptr_elem_size: int = 1, use_inc: bool = False):
        """Generate addition (inline)
        ptr_elem_size: if doing pointer arithmetic, the size of elements (1 for BYTE, 2 for WORD)
        use_inc: if True and ptr_elem_size == 1, use INC TMP0 for adding 1 (optimization)
        """
        if ptr_elem_size == 2:
            # Pointer to WORD: scale offset by 2
            # A (offset) needs to be multiplied by 2 before adding
            self.emit("\tASL A")  # Multiply by 2
            # If carry was set, we'll handle it below
        
        if is_16bit:
            # 16-bit: (A,X) + (TMP0,TMP1) → (A,X)
            if use_inc and ptr_elem_size == 1:
                # Optimization: use INC for adding 1 to 16-bit pointer
                self.emit("\tINC TMP0")
                self.emit("\tBNE +")
                self.emit("\tINC TMP0+1")
                self.emit("+")
                self.emit("\tLDA TMP0")
                self.emit("\tLDX TMP0+1")
            else:
                self.emit("\tCLC")
                self.emit("\tADC TMP0")
                self.emit("\tTAY")
                self.emit("\tTXA")
                self.emit("\tADC TMP1")
                self.emit("\tTAX")
                self.emit("\tTYA")
        else:
            # 8-bit: A + TMP0 → A
            if use_inc and ptr_elem_size == 1:
                # Optimization: use INC for adding 1
                self.emit("\tINC TMP0")
                self.emit("\tLDA TMP0")
            else:
                self.emit("\tCLC")
                self.emit("\tADC TMP0")
    
    def _gen_sub(self, is_16bit: bool, ptr_elem_size: int = 1, use_dec: bool = False):
        """Generate subtraction (inline): TMP0 - A
        ptr_elem_size: if doing pointer arithmetic, the size of elements (1 for BYTE, 2 for WORD)
        use_dec: if True and ptr_elem_size == 1, use DEC TMP0 for subtracting 1 (optimization)
        """
        if ptr_elem_size == 2:
            # Pointer to WORD: scale offset by 2
            # A (offset) needs to be multiplied by 2 before subtracting
            self.emit("\tASL A")  # Multiply by 2
        
        if is_16bit:
            # 16-bit: (TMP0,TMP1) - (A,X) → (A,X)
            if use_dec and ptr_elem_size == 1:
                # Optimization: use DEC for subtracting 1 from 16-bit pointer
                self.emit("\tDEC TMP0")
                self.emit("\tBNE +")
                self.emit("\tDEC TMP0+1")
                self.emit("+")
                self.emit("\tLDA TMP0")
                self.emit("\tLDX TMP0+1")
            else:
                self.emit("\tSTA TMP2")
                self.emit("\tSTX TMP2+1")
                self.emit("\tSEC")
                self.emit("\tLDA TMP0")
                self.emit("\tSBC TMP2")
                self.emit("\tTAY")
                self.emit("\tLDA TMP1")
                self.emit("\tSBC TMP3")
                self.emit("\tTAX")
                self.emit("\tTYA")
        else:
            # 8-bit: TMP0 - A → A
            if use_dec and ptr_elem_size == 1:
                # Optimization: use DEC for subtracting 1
                self.emit("\tDEC TMP0")
                self.emit("\tLDA TMP0")
            else:
                self.emit("\tSTA TMP2")
                self.emit("\tSEC")
                self.emit("\tLDA TMP0")
                self.emit("\tSBC TMP2")
    
    def _gen_mul(self, left_16: bool, right_16: bool, result_16: bool):
        """Generate multiplication (call runtime routine)"""
        if not left_16 and not right_16:
            self.math_routines_needed.add("MUL8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("MUL16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("MUL16_8")
        else:
            self.math_routines_needed.add("MUL16")
        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})
        # TMP0,TMP1 = left operand (already stored)
        # A,X = right operand (in registers)
        # Store right operand
        self.emit("\tSTA TMP2")
        self.emit("\tSTX TMP3")
        
        if not left_16 and not right_16:
            # 8x8 = 8 or 16
            self.emit("\tJSR MUL8")
        elif left_16 and not right_16:
            # 16x8 = 16
            self.emit("\tJSR MUL16_8")
        elif not left_16 and right_16:
            # 8x16 = 16 (swap operands)
            self.emit("\tLDA TMP2")
            self.emit("\tLDX TMP3")
            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP1")
            self.emit("\tJSR MUL16_8")
        else:
            # 16x16 = 16
            self.emit("\tJSR MUL16")
    
    def _gen_div(self, left_16: bool, right_16: bool, result_16: bool):
        """Generate division (call runtime routine)"""
        if not left_16 and not right_16:
            self.math_routines_needed.add("DIV8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("DIV16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("DIV8_16")
        else:
            self.math_routines_needed.add("DIV16")
        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})
        # TMP0,TMP1 = dividend
        # A,X = divisor
        self.emit("\tSTA TMP2")
        self.emit("\tSTX TMP3")
        
        if not left_16 and not right_16:
            # 8/8 = 8
            self.emit("\tJSR DIV8")
        elif left_16 and not right_16:
            # 16/8 = 16
            self.emit("\tJSR DIV16_8")
        elif not left_16 and right_16:
            # 8/16 = 8 (result is always 0 or 1)
            self.emit("\tJSR DIV8_16")
        else:
            # 16/16 = 16
            self.emit("\tJSR DIV16")
    
    def _gen_mod(self, left_16: bool, right_16: bool, result_16: bool):
        """Generate modulo (call runtime routine)"""
        if not left_16 and not right_16:
            self.math_routines_needed.add("MOD8")
        elif left_16 and not right_16:
            self.math_routines_needed.add("MOD16_8")
        elif not left_16 and right_16:
            self.math_routines_needed.add("MOD8_16")
        else:
            self.math_routines_needed.add("MOD16")
        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})
        # TMP0,TMP1 = dividend
        # A,X = divisor
        self.emit("\tSTA TMP2")
        self.emit("\tSTX TMP3")
        
        if not left_16 and not right_16:
            # 8%8 = 8
            self.emit("\tJSR MOD8")
        elif left_16 and not right_16:
            # 16%8 = 8
            self.emit("\tJSR MOD16_8")
        elif not left_16 and right_16:
            # 8%16 = 8
            self.emit("\tJSR MOD8_16")
        else:
            # 16%16 = 16
            self.emit("\tJSR MOD16")

    def _gen_logical(self, expr: BinaryExpr):
        # TMP4 used to combine A/X when testing word values
        self.used_temps.add("TMP4")
        if expr.op == BinOp.LAND:
            lbl_false = self.new_label("LAND_FALSE")
            lbl_end   = self.new_label("LAND_END")

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
            self.emit("\tLDX #0")
            return
        
        if expr.op == BinOp.LOR:
            lbl_true = self.new_label("LOR_TRUE")
            lbl_end  = self.new_label("LOR_END")

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
            self.emit("\tLDX #0")
            return


    def gen_expr(self, expr):
        # Apply constant folding and algebraic simplifications
        expr = fold_expr(expr)
        
        if isinstance(expr, IntLiteral):
            self._gen_literal(expr)
        elif isinstance(expr, Identifier):
            self._gen_identifier(expr)
        elif isinstance(expr, DerefExpr):
            self._gen_deref(expr)
        elif isinstance(expr, SubscriptExpr):
            self._gen_subscript(expr, load_only=True)
        elif isinstance(expr, CallExpr):
            # Emit source comment for function call if available
            info = self.stmt_src.get(id(expr))
            if info:
                fname, line, text = info
                self.emit(f"; {fname} {line}: {text}")
            # Evaluate and pass arguments to function parameters
            specs = self.func_param_specs.get(expr.name)
            if specs is not None:
                n = min(len(specs), len(expr.args))
                for i in range(n):
                    pname, width = specs[i]
                    arg = expr.args[i]
                    arg_type = self.tc_check(arg)
                    self.gen_expr(arg)
                    asm = f"_{expr.name}_{pname}"
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
            if expr.op in {BinOp.LAND, BinOp.LOR}:
                self._gen_logical(expr)
            elif expr.op in {
                BinOp.EQ, BinOp.NE,
                BinOp.LT, BinOp.LE,
                BinOp.GT, BinOp.GE
            }:
                self._gen_relational(expr)
            else:
                self._gen_binary(expr)

    def gen_assign(self, lhs: Expr, rhs: Expr):
        # Apply constant substitution and folding to RHS
        from constsubst import subst_const
        from typing import cast
        rhs = subst_const(rhs, cast(SymbolTable, self.current_symtab))
        rhs = fold_expr(rhs)

        lhs_t = self.tc_check(lhs)
        rhs_t = self.tc_check(rhs)

        # typová kompatibilita                
        if not isinstance(lhs, (Identifier, DerefExpr, SubscriptExpr)):
            self._raise_error("Left side of assignment is not assignable")

        if lhs_t.kind == ExprKind.LVALUE:
            # RHS LVALUE means we're reading from that location (convert to VALUE semantically)
            if rhs_t.kind == ExprKind.LVALUE:
                # Both sides are lvalues, treat RHS as reading a value
                rhs_t = ExprType(rhs_t.sem_type, ExprKind.VALUE)
            
            if rhs_t.kind != ExprKind.VALUE:
                self._raise_error("Cannot assign address to lvalue")

            # Allow implicit narrowing (WORD to BYTE) - just truncate low byte
            # This is common in low-level code (e.g., ptr^ = word_counter)
        
        # Allow ADDR = ADDR for pointer assignments
        if lhs_t.kind == ExprKind.ADDR and lhs_t.sem_type.is_pointer:
            if rhs_t.kind != ExprKind.ADDR and rhs_t.kind != ExprKind.VALUE:
                self._raise_error("Cannot assign to pointer")
            # Type compatibility for pointers (WORD base for all pointers)
            # No further checks needed since pointers are always WORD-sized

        # Peepholes: constant assign and small +/-
        if isinstance(lhs, Identifier):
            sym_lhs = self.current_symtab.lookup(lhs.name)

            # Direct constant assignment
            if isinstance(rhs, IntLiteral) and sym_lhs.address is None:
                if lhs_t.sem_type.base == "BYTE" and not lhs_t.sem_type.is_pointer:
                    self._emit_store_byte_const(sym_lhs, rhs.value)
                else:
                    self._emit_store_word_const(sym_lhs, rhs.value)
                return

            if isinstance(rhs, BinaryExpr):
                asm = sym_lhs.asm_name()
                # Pointers are always 16-bit even if base type is BYTE
                is_word = lhs_t.sem_type.base == "WORD" or lhs_t.sem_type.is_pointer

                def is_self(opnd):
                    return isinstance(opnd, Identifier) and opnd.name == lhs.name

                def small_const(opnd):
                    if isinstance(opnd, IntLiteral) and opnd.value in {1, 2, 3}:
                        return opnd.value
                    return None

                # var = var + k (k=1..3)
                k_left = small_const(rhs.left)
                k_right = small_const(rhs.right)

                if rhs.op == BinOp.ADD:
                    k: int | None = None
                    if is_self(rhs.left) and k_right is not None:
                        k = k_right
                    elif is_self(rhs.right) and k_left is not None:
                        k = k_left

                    if k is not None:
                        # For pointer arithmetic, scale by element size
                        # WORD pointers move by 2 bytes per element, BYTE pointers by 1
                        scale = 2 if lhs_t.sem_type.is_pointer and lhs_t.sem_type.base == "WORD" else 1
                        total_inc = k * scale
                        
                        if is_word:
                            # For 16-bit values, use proper ADD instead of looping INC
                            if lhs_t.sem_type.is_pointer and lhs_t.sem_type.base == "WORD" and total_inc > 1:
                                # Use 16-bit addition for pointer arithmetic
                                self.emit(f"\tLDA {asm}")
                                self.emit(f"\tCLC")
                                self.emit(f"\tADC #{total_inc}")
                                self.emit(f"\tSTA {asm}")
                                lbl = self.new_label("CARRY_ADD_PTR")
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
                    scale = 2 if lhs_t.sem_type.is_pointer and lhs_t.sem_type.base == "WORD" else 1
                    total_dec = k * scale
                    
                    if is_word:
                        # For 16-bit values, use proper SBC instead of looping DEC
                        if lhs_t.sem_type.is_pointer and lhs_t.sem_type.base == "WORD" and total_dec > 1:
                            # Use 16-bit subtraction for pointer arithmetic
                            self.emit(f"\tLDA {asm}")
                            self.emit(f"\tSEC")
                            self.emit(f"\tSBC #{total_dec}")
                            self.emit(f"\tSTA {asm}")
                            lbl = self.new_label("CARRY_SUB_PTR")
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

                # Optimize word var = var1 +/- var2 (memory-to-memory operations)
                if is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    # Check if both operands are simple identifier references
                    if isinstance(rhs.left, Identifier) and isinstance(rhs.right, Identifier):
                        left_sym = self.current_symtab.lookup(rhs.left.name)
                        right_sym = self.current_symtab.lookup(rhs.right.name)
                        
                        # Only optimize if both are simple memory variables (not arrays, not at fixed addresses)
                        if (not left_sym.is_array and left_sym.address is None and
                            not right_sym.is_array and right_sym.address is None):
                            
                            left_asm = left_sym.asm_name()
                            right_asm = right_sym.asm_name()
                            
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
                            elif rhs.op == BinOp.SUB:
                                # word_var = word_var1 - word_var2
                                self.emit(f"\tLDA {left_asm}")
                                self.emit("\tSEC")
                                self.emit(f"\tSBC {right_asm}")
                                self.emit(f"\tSTA {asm}")
                                self.emit(f"\tLDA {left_asm}+1")
                                self.emit(f"\tSBC {right_asm}+1")
                                self.emit(f"\tSTA {asm}+1")
                                return

                # Optimize byte var = var1 +/- imm (direct immediate operations)
                if not is_word and rhs.op in {BinOp.ADD, BinOp.SUB}:
                    # Check if one operand is identifier and other is immediate
                    var_opnd = None
                    imm_opnd = None
                    
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
                        var_sym = self.current_symtab.lookup(var_opnd.name)
                        if not var_sym.is_array and var_sym.address is None:
                            var_asm = var_sym.asm_name()
                            imm_val = imm_opnd.value & 0xFF
                            
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

        # Fast path: store immediate into dereferenced ZP pointer without temps
        if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, Identifier):
            ptr_sym = self.current_symtab.lookup(lhs.pointer.name)
            if ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array:
                if isinstance(rhs, IntLiteral) and lhs_t.sem_type.base == "BYTE":
                    val = rhs.value & 0xFF
                    self.emit(f"\tLDA #${val:02X}")
                    if self.is_65c02:
                        self.emit(f"\tSTA ({ptr_sym.asm_name()})")
                    else:
                        self.emit("\tLDY #0")
                        self.emit(f"\tSTA ({ptr_sym.asm_name()}),Y")
                    return

        # vygeneruj RHS
        self.gen_expr(rhs)

        # Handle type widening: if RHS is smaller than LHS, extend with zeros
        # This is needed when assigning a BYTE to a WORD target
        if (rhs_t.sem_type.base == "BYTE" and not rhs_t.sem_type.is_pointer and
            lhs_t.sem_type.base == "WORD"):
            if self.is_65c02:
                self.emit("\tLDX #0")  # Clear X for BYTE to WORD conversion
            else:
                self.emit("\tLDX #0")

        if isinstance(lhs, Identifier):

            sym = self.current_symtab.lookup(lhs.name)

            if sym.is_const:
                self._raise_error("Cannot assign to const")

            asm = sym.asm_name()
            if sym.type.base == "BYTE" and not sym.type.is_pointer:
                self.emit(f"\tSTA {asm}")
            else:
                self.emit(f"\tSTA {asm}")
                self.emit(f"\tSTX {asm}+1")
            return

        # dereference
        if isinstance(lhs, DerefExpr):
            # 1️⃣ ulož RHS hodnotu
            self.emit("\tSTA TMP2")
            self.emit("\tSTX TMP2+1")

            # 2️⃣ vygeneruj adresu pointeru
            self.gen_expr(lhs.pointer)

            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")

            # 3️⃣ zápis LOW byte
            self.emit("\tLDY #0")
            self.emit("\tLDA TMP2")
            self.emit("\tSTA (TMP0),Y")

            # 4️⃣ Write high byte only if LHS target is WORD
            if lhs_t.sem_type.base == "WORD":
                self.emit("\tINY")
                self.emit("\tLDA TMP2+1")
                self.emit("\tSTA (TMP0),Y")
            return

        if isinstance(lhs, SubscriptExpr):
            # Save RHS value to temps before subscript calculation
            self.emit("\tSTA TMP2")
            self.emit("\tSTX TMP2+1")
            self._gen_subscript(lhs, load_only=False)
            return

        raise NotImplementedError(type(lhs))

    def _gen_for_const_step(self, stmt, step_expr):
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # end
        end_name = self.new_for_var("END")
        self._declare_temp(end_name)
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

    def _gen_for_general(self, stmt):
        # i = start
        self.gen_assign(stmt.var, stmt.start)

        # vytvoř skryté proměnné
        end_name = self.new_for_var("END")
        step_name = self.new_for_var("STEP")

        self._declare_temp(end_name)
        self._declare_temp(step_name)

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


    def gen_proc(self, proc: AnalyzedProc):
        # přepni na lokální tabulku + typechecker
        prev_symtab = self.current_symtab
        prev_tc_symtab = getattr(self.tc, "symtab", None)
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
            self.gen_init(sym)

        # tělo
        for stmt in proc.ast.body:
            self.gen_stmt(stmt)

        self.emit("\tRTS")

        # restore
        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab


    def gen_stmt(self, stmt):
        from ast_nodes import SegmentDirective
        # Emit source comment for this statement
        self.emit_src_comment_for_stmt(stmt)
        
        if isinstance(stmt, SegmentDirective):
            self.emit(f'.segment "{stmt.name}"')
            return

        if isinstance(stmt, AsmBlock):
            for line in stmt.text.splitlines():
                self.emit(line)
            return

        if isinstance(stmt, CallStmt):
            # Pass arguments to callee parameters (simple ABI via memory)
            specs = self.proc_param_specs.get(stmt.name)
            if specs is not None:
                n = min(len(specs), len(stmt.args))
                for i in range(n):
                    pname, width = specs[i]
                    arg = stmt.args[i]
                    arg_type = self.tc_check(arg)
                    # evaluate arg into A/(X)
                    self.gen_expr(arg)
                    asm = f"_{stmt.name}_{pname}"
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
            # vyhodnoť výraz → A/(X)
            self.gen_expr(stmt.expr)
            self.emit("\tRTS")
            return
        
        if isinstance(stmt, IfStmt):
            cond = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond = fold_expr(cond)

            lbl_else = self.new_label("else")
            lbl_end  = self.new_label("endif")
            lbl_then = self.new_label("then")

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
            lbl_start = self.new_label("while")
            lbl_end   = self.new_label("endwhile")
            lbl_body  = self.new_label("while_body")

            # PUSH
            self.loop_stack.append((lbl_start, lbl_end))

            self.emit(f"{lbl_start}:")
            cond = subst_const(stmt.cond, cast(SymbolTable, self.current_symtab))
            cond = fold_expr(cond)

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
            step_expr = stmt.step if stmt.step else IntLiteral(1)

            if isinstance(step_expr, IntLiteral):
                self._gen_for_const_step(stmt, step_expr)
            else:
                self._gen_for_general(stmt)
            return


        raise NotImplementedError(type(stmt))

    def gen_func(self, func: AnalyzedFunc):
        prev_symtab = self.current_symtab
        prev_tc_symtab = getattr(self.tc, "symtab", None)
        self.current_symtab = cast(SymbolTable, func.symtab)
        self.tc.symtab = func.symtab

        self.emit("; -- Function " + func.ast.name + " --")
        self.emit(f"{func.ast.name}:")

        # init lokálů
        for sym in func.locals:
            self.gen_init(sym)

        # tělo
        for stmt in func.ast.body:
            self.gen_stmt(stmt)

        # fallback (pokud RETURN nebyl – zatím chyba v sémantice)
        self.emit("\tRTS")

        self.current_symtab = prev_symtab
        if prev_tc_symtab is not None:
            self.tc.symtab = prev_tc_symtab

    def _gen_relational(self, expr: BinaryExpr):
        left_t = self.tc_check(expr.left)
        right_t = self.tc_check(expr.right)
        is_16bit = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"

        # Try a fast 8-bit compare when the right operand is a simple byte value
        cmp_operand: str | None = None

        def simple_byte_operand(rhs: Expr) -> str | None:
            """Return an operand suitable for CMP if rhs is a trivial byte source."""
            if is_16bit:
                return None

            if isinstance(rhs, IntLiteral):
                return f"#{rhs.value & 0xFF}"

            if isinstance(rhs, Identifier):
                sym = self.current_symtab.lookup(rhs.name)

                if sym.is_array or sym.address is not None:
                    return None
                if sym.type.is_pointer or sym.type.base not in {"BYTE", "CHAR"}:
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
                self.emit("\tLDX #0")
            self.emit("\tSTA TMP0")
            if is_16bit:
                self.emit("\tSTX TMP0+1")

            # levý operand
            self.gen_expr(expr.left)
            # Ensure left high byte is well-defined in 16-bit context
            if is_16bit and left_t.sem_type.base != "WORD":
                self.emit("\tLDX #0")

            cmp_operand = "TMP0"

        lbl_true = self.new_label("REL_TRUE")
        lbl_end  = self.new_label("REL_END")

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
        self.emit("\tLDX #0")

    def _emit_relational_branch(self, cond: BinaryExpr, *, lbl_true: str, lbl_false: str):
        """Emit relational test that jumps to lbl_true or lbl_false using only short local branches and absolute JMPs.

        This avoids boolean materialization and keeps conditional branches within range by funneling through local labels.
        """
        left_t = self.tc_check(cond.left)
        right_t = self.tc_check(cond.right)
        is_16bit = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"

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
                sym = self.current_symtab.lookup(rhs.name)

                if sym.is_array or sym.address is not None:
                    return None
                if sym.type.is_pointer or sym.type.base not in {"BYTE", "CHAR"}:
                    return None
                if sym.is_volatile:
                    return None
                return sym.asm_name()

            return None

        # Optimize: if right side is a constant, use immediate addressing
        from ast_nodes import IntLiteral
        from typing import cast
        use_immediate = isinstance(cond.right, IntLiteral)
        
        if use_immediate:
            right_literal = cast(IntLiteral, cond.right)
            const_val = right_literal.value & 0xFFFF
            const_lo = const_val & 0xFF
            const_hi = (const_val >> 8) & 0xFF
            cmp_lo = f"#${const_lo:02X}"
            cmp_hi = f"#${const_hi:02X}"

            # Fast path: word identifier vs constant → defer loading X until low byte matches
            if is_16bit and isinstance(cond.left, Identifier):
                sym = self.current_symtab.lookup(cond.left.name)
                asm = sym.asm_name()
                if cond.op == BinOp.EQ:
                    lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                    lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                    lbl_else_tmp = self.new_label("REL_ELSE_TMP")
                    self.emit(f"\tLDX {asm}+1")
                    self.emit(f"\tCPX {cmp_hi}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")
                    self.emit(f"\tBNE {lbl_else_tmp}")
                    self.emit(f"\tLDA {asm}")
                    self.emit(f"\tCMP {cmp_lo}")
                    self.emit(f"\tBCC {lbl_true}")
                    self.emit(f"\tBEQ {lbl_true}")                    
                    self.emit(f"{lbl_else_tmp}:")
                    self.emit(f"\tJMP {lbl_false}")
                    return
                if cond.op == BinOp.GT:
                    lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                    lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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

            # Evaluate left into A/X
            self.gen_expr(cond.left)
            if is_16bit and left_t.sem_type.base != "WORD":
                self.emit("\tLDX #0")
        else:
            # Try simple byte operand optimization for 8-bit compares
            cmp_operand = simple_byte_operand(cond.right)
            
            if cmp_operand is not None:
                # Left operand only; right is accessed directly in CMP
                self.gen_expr(cond.left)
                cmp_lo = cmp_operand
                # cmp_hi stays as "TMP0+1" but won't be used for 8-bit
            else:
                # Evaluate right into TMP0/(TMP0+1)
                self.gen_expr(cond.right)
                if is_16bit and right_t.sem_type.base != "WORD":
                    self.emit("\tLDX #0")
                self.emit("\tSTA TMP0")
                if is_16bit:
                    self.emit("\tSTX TMP0+1")
                self.gen_expr(cond.left)
                if is_16bit and left_t.sem_type.base != "WORD":
                    self.emit("\tLDX #0")
                # Set cmp_lo and cmp_hi to TMP0
                cmp_lo = "TMP0"
                cmp_hi = "TMP0+1"

        if is_16bit:
            if cond.op == BinOp.EQ:
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
                lbl_check_hi = self.new_label("CHECK_HI")
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
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
                # Compare low byte first
                self.emit(f"\tCMP {cmp_lo}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"\tBEQ {lbl_true}")
                self.emit(f"\tBNE {lbl_else_tmp}")
                # Low byte greater, check high byte
                self.emit(f"\tCPX {cmp_hi}")
                self.emit(f"\tBCC {lbl_true}")
                self.emit(f"{lbl_else_tmp}:")
                self.emit(f"\tJMP {lbl_false}")
            elif cond.op == BinOp.GT:
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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
                lbl_else_tmp = self.new_label("REL_ELSE_TMP")
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


from typing import cast
from constfold import fold_expr
from constsubst import subst_const
from symbols import Symbol, SymbolTable, SemType
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

    def __init__(self, symtab: SymbolTable, type_checker: ExprTypeChecker, *, is_65c02: bool = True, used_globals: set[str] | None = None, debug_info: dict | None = None, command_line: str | None = None, proc_param_specs: dict[str, list[tuple[str, int]]] | None = None, func_param_specs: dict[str, list[tuple[str, int]]] | None = None):
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
        self.math_runtime_needed = False
        self.is_65c02 = is_65c02
        self.used_globals = used_globals or set()
        self.used_temps: set[str] = set()
        self.command_line = command_line
        # Parameter specs: mapping name -> list of (param_name, width_bytes)
        self.proc_param_specs: dict[str, list[tuple[str, int]]] = proc_param_specs or {}
        self.func_param_specs: dict[str, list[tuple[str, int]]] = func_param_specs or {}
        # Debug/source maps
        self.debug = debug_info or {}
        self.stmt_src = self.debug.get("stmt_src", {})
        self.local_decl_src = self.debug.get("local_decl_src", {})
        self.global_decl_src = self.debug.get("global_decl_src", {})
        self.proc_src = self.debug.get("proc_src", {})
        self.file_lines = self.debug.get("file_lines", {})

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
        self.emit(f"\tDEC {asm}")
        self.emit(f"\tBNE {lbl}")
        self.emit(f"\tDEC {asm}+1")
        self.emit(f"{lbl}:")

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

    def peephole_optimize(self):
        """Apply lightweight peepholes to emitted code for both 6502 and 65c02."""
        optimized: list[str] = []
        skip_indices = set()  # Track which indices to skip
        i = 0
        while i < len(self.code):
            # Check if this instruction should be skipped (marked as redundant)
            if i in skip_indices:
                i += 1
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
                if curU.startswith(("LDA ", "LDX ", "LDY ")):
                    redundant_load = False
                    redundant_at = -1
                    j = i + 1
                    jsr_seen = False
                    reg_used = False
                    # Determine which register we're checking and extract operand
                    checking_a = curU.startswith("LDA ")
                    checking_x = curU.startswith("LDX ")
                    checking_y = curU.startswith("LDY ")
                    cur_parts = curU.split(maxsplit=1)
                    cur_operand = cur_parts[1].strip() if len(cur_parts) == 2 else ""
                    
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
                # Simple consecutive LDA overwrite (preserve the later load)
                if curU.startswith("LDA ") and nxtU.startswith("LDA "):
                    i += 1
                    continue
                store_load_pairs = [("STA", "LDA"), ("STX", "LDX"), ("STY", "LDY")]
                matched = False
                for st, ld in store_load_pairs:
                    if curU.startswith(st + " ") and nxtU.startswith(ld + " "):
                        op1 = curU[len(st) + 1:].strip()
                        op2 = nxtU[len(ld) + 1:].strip()
                        if op1 == op2:
                            optimized.append(self.code[i])
                            i += 2
                            matched = True
                            break
                if matched:
                    continue
                
                # Remove redundant consecutive stores (STA/STX/STY) to same location when no JSR between
                if curU.startswith(("STA ", "STX ", "STY ")):
                    cur_parts = curU.split(maxsplit=1)
                    if len(cur_parts) == 2:
                        cur_operand = cur_parts[1].strip()
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

            # Remove orphaned register loads (LDX/LDY) when next instruction doesn't use them
            # Common pattern: LDX #0 after byte load, followed by STA (X is never read)
            if i + 1 < len(self.code):
                cur = self.code[i].strip().upper()
                nxt = self.code[i + 1].strip().upper()
                
                # Check if current instruction loads X or Y with immediate value
                loads_x = cur.startswith("LDX #")
                loads_y = cur.startswith("LDY #")
                
                if loads_x or loads_y:
                    # Check if next instruction reads or writes the loaded register
                    # If next instruction writes X/Y, the load is orphaned
                    # If next instruction reads X/Y, the load is needed
                    
                    skip_load = False
                    if loads_x:
                        # X is orphaned if next instruction writes X (without reading it first)
                        # or if next instruction doesn't use X at all
                        if (nxt.startswith("LDX ") or  # Next instruction overwrites X
                            # Next instruction doesn't read X (conservative check - only safe instructions)
                            (nxt.startswith("STA ") and not nxt.startswith("STA X") or
                             nxt.startswith("LDA #") or
                             nxt.startswith("JSR ") or
                             nxt == "RTS" or
                             nxt.startswith("JMP ") or
                             nxt.startswith("CLC") or
                             nxt.startswith("SEC"))):
                            # But make sure there's no STX in the next few instructions before X is reloaded
                            # Look ahead to see if X is used before being overwritten
                            x_used_before_reload = False
                            for j in range(i + 1, min(i + 5, len(self.code))):
                                check = self.code[j].strip().upper()
                                if check.startswith("STX ") or check.endswith(" X") or check.startswith("TXA") or check.startswith("DEX") or check.startswith("INX"):
                                    x_used_before_reload = True
                                    break
                                if check.startswith("LDX "):
                                    # X is reloaded, so the current LDX is orphaned
                                    break
                            
                            if not x_used_before_reload:
                                skip_load = True
                    
                    elif loads_y:
                        # Similar logic for Y
                        if (nxt.startswith("LDY ") or
                            (nxt.startswith("STA ") and not nxt.startswith("STA Y") or
                             nxt.startswith("LDA #") or
                             nxt.startswith("STX ") or
                             nxt.startswith("JSR ") or
                             nxt == "RTS" or
                             nxt.startswith("JMP ") or
                             nxt.startswith("CLC") or
                             nxt.startswith("SEC"))):
                            y_used_before_reload = False
                            for j in range(i + 1, min(i + 5, len(self.code))):
                                check = self.code[j].strip().upper()
                                if check.startswith("STY ") or check.endswith(" Y") or check.startswith("TYA") or check.startswith("DEY") or check.startswith("INY"):
                                    y_used_before_reload = True
                                    break
                                if check.startswith("LDY "):
                                    break
                            
                            if not y_used_before_reload:
                                skip_load = True
                    
                    if skip_load:
                        # Skip the orphaned register load
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
        cleaned: list[str] = []
        i = 0
        while i < len(self.code):
            if i + 1 < len(self.code):
                cur = self.code[i]
                curU = cur.strip().upper()
                if curU.startswith(("LDA ", "LDX ", "LDY ")):
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
        self.emit("; Inputs: TMP0/TMP1=src, TMP2/TMP3=dst, X=len (1..255), Y=0")
        self.emit("; Clobbers: A, X, Y")
        self.emit("; Note: length must fit in one page; longer copies stay inline")
        self.emit("COPY_BYTES:")
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
        if not self.math_runtime_needed:
            return
        self.used_temps.update({"TMP0", "TMP1", "TMP2", "TMP3"})

        self.emit("; ------------------------------")
        self.emit("; Math Runtime Routines")
        self.emit("; ------------------------------")
        self.emit("")
        
        # 8-bit x 8-bit = 16-bit multiplication
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
        self.emit("")
        
        # 16-bit x 8-bit = 16-bit multiplication
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
        self.emit("")
        
        # 16-bit x 16-bit = 16-bit multiplication (only low 16 bits)
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
        self.emit("")
        
        # 8-bit / 8-bit = 8-bit division
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
        self.emit("\tINC TMP0")
        self.emit("DIV8_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE DIV8_LOOP")
        self.emit("\tLDA TMP0")
        self.emit("\tLDX #0")
        self.emit("\tRTS")
        self.emit("")
        
        # 16-bit / 8-bit = 16-bit division
        self.emit("; DIV16_8: 16/8=16 divide")
        self.emit("; Input: TMP0,TMP1 (dividend), TMP2 (divisor)")
        self.emit("; Output: A=low, X=high")
        self.emit("DIV16_8:")
        self._stz("TMP3")
        self.emit("\tLDX #16")
        self.emit("DIV16_8_LOOP:")
        self.emit("\tROL TMP0")
        self.emit("\tROL TMP1")
        self.emit("\tROL TMP3")
        self.emit("\tLDA TMP3")
        self.emit("\tCMP TMP2")
        self.emit("\tBCC DIV16_8_SKIP")
        self.emit("\tSBC TMP2")
        self.emit("\tSTA TMP3")
        self.emit("\tINC TMP0")
        self.emit("DIV16_8_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE DIV16_8_LOOP")
        self.emit("\tLDA TMP0")
        self.emit("\tLDX TMP1")
        self.emit("\tRTS")
        self.emit("")
        
        # 8-bit / 16-bit = 8-bit division (result is 0 or 1)
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
        self.emit("")
        
        # 16-bit / 16-bit = 16-bit division
        self.emit("; DIV16: 16/16=16 divide")
        self.emit("; Input: TMP0,TMP1 (dividend), TMP2,TMP3 (divisor)")
        self.emit("; Output: A=low, X=high")
        self.emit("DIV16:")
        self._stz("TMP2+2")
        self._stz("TMP2+3")
        self.emit("\tLDX #16")
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
        self.emit("\tINC TMP0")
        self.emit("DIV16_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE DIV16_LOOP")
        self.emit("\tLDA TMP0")
        self.emit("\tLDX TMP1")
        self.emit("\tRTS")
        self.emit("")
        
        # 8-bit % 8-bit = 8-bit modulo
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
        self.emit("\tINC TMP0")
        self.emit("MOD8_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE MOD8_LOOP")
        self.emit("\tLDX #0")
        self.emit("\tRTS")
        self.emit("")
        
        # 16-bit % 8-bit = 8-bit modulo
        self.emit("; MOD16_8: 16%8=8 modulo")
        self.emit("; Input: TMP0,TMP1 (dividend), TMP2 (divisor)")
        self.emit("; Output: A=remainder, X=0")
        self.emit("MOD16_8:")
        self._stz("TMP3")
        self.emit("\tLDX #16")
        self.emit("MOD16_8_LOOP:")
        self.emit("\tROL TMP0")
        self.emit("\tROL TMP1")
        self.emit("\tROL TMP3")
        self.emit("\tLDA TMP3")
        self.emit("\tCMP TMP2")
        self.emit("\tBCC MOD16_8_SKIP")
        self.emit("\tSBC TMP2")
        self.emit("\tSTA TMP3")
        self.emit("\tINC TMP0")
        self.emit("MOD16_8_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE MOD16_8_LOOP")
        self.emit("\tLDA TMP3")
        self.emit("\tLDX #0")
        self.emit("\tRTS")
        self.emit("")
        
        # 8-bit % 16-bit = 8-bit modulo (result is dividend if divisor > dividend)
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
        self.emit("")
        
        # 16-bit % 16-bit = 16-bit modulo
        self.emit("; MOD16: 16%16=16 modulo")
        self.emit("; Input: TMP0,TMP1 (dividend), TMP2,TMP3 (divisor)")
        self.emit("; Output: A=low, X=high")
        self.emit("MOD16:")
        self._stz("TMP2+2")
        self._stz("TMP2+3")
        self.emit("\tLDX #16")
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
        self.emit("\tINC TMP0")
        self.emit("MOD16_SKIP:")
        self.emit("\tDEX")
        self.emit("\tBNE MOD16_LOOP")
        self.emit("\tLDA TMP2+2")
        self.emit("\tLDX TMP2+3")
        self.emit("\tRTS")    


    def gen_var_header(self):
        self.emit("; Variables")
        self.emit("; ------------------------------")   

    def _detect_temp_usage(self, code: list[str] | None = None) -> set[str]:
        """Scan generated code for temp usage and combine with flagged temps."""
        temp_names = {"TMP0", "TMP1", "TMP2", "TMP3", "TMP4"}
        temps = set(self.used_temps)
        code = self.code if code is None else code

        if self.copy_bytes_needed or self.math_runtime_needed:
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
                    raise SemanticError(f"Zero page exhausted: pointer '{sym.name}' cannot fit (need {zp_offset + 2} bytes)")
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
                    self.emit(f"{sym.asm_name()}:\t.res {size}")

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
        # Exception: always initialize fixed-address variables (hardware ports)
        if sym.proc_name == "" and sym.name not in self.used_globals and sym.address is None:
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
            COPY_THRESHOLD = 8  # bytes; above this, call shared copy to save space
            
            # Optimized string copy using loop
            # For very short strings (1-2 chars), inline is better
            if str_len <= 3:
                # Inline for very short strings (no string data needed)
                for i, ch in enumerate(content.encode('ascii')):
                    self.emit(f"\tLDA #${ch:02X}")
                    self.emit(f"\tSTA {dest_var}+{i}")
                self.emit(f"\tLDA #0")
                self.emit(f"\tSTA {dest_var}+{len(content)}")
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
                self.emit("\tSTX TMP1")

                self.emit(f"\tLDA #<{dest_var}")
                self.emit(f"\tLDX #>{dest_var}")
                self.emit("\tSTA TMP2")
                self.emit("\tSTX TMP3")

                self.emit(f"\tLDX #{str_len}")
                self.emit("\tLDY #0")
                self.emit("\tJSR COPY_BYTES")
            else:
                # Use loop for longer strings - get or create label
                if content not in self.string_literals:
                    self.string_id += 1
                    self.string_literals[content] = f"STR_DATA_{self.string_id}"
                
                str_label = self.string_literals[content]
                self.emit(f"\t; Copy string \"{content[:20]}{'...' if len(content) > 20 else ''}\" ({str_len} bytes)")
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
                    self.emit(f"\tSTA {sym.asm_name()}+{i}")
                    if sym.type.base == "WORD":
                        self.emit(f"\tSTX {sym.asm_name()}+{i}+1")
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
                    self.emit(f"\tSTA {dest_var}+{i}")
                    if is_word:
                        self.emit(f"\tSTX {dest_var}+{i}+1")
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
                    # Source -> TMP0/TMP1
                    self.emit(f"\tLDA #<{arr_label}")
                    self.emit(f"\tLDX #>{arr_label}")
                    self.emit("\tSTA TMP0")
                    self.emit("\tSTX TMP1")
                    # Dest -> TMP2/TMP3
                    self.emit(f"\tLDA #<{dest_var}")
                    self.emit(f"\tLDX #>{dest_var}")
                    self.emit("\tSTA TMP2")
                    self.emit("\tSTX TMP3")
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
            fname, line, text = info
            self.emit(f"; {fname} {line}: {text}")

    def emit_src_comment_for_local(self, proc_name: str, var_name: str):
        info = self.local_decl_src.get((proc_name, var_name))
        if info:
            fname, line, text = info
            self.emit(f"; {fname} {line}: {text}")

    def emit_src_comment_for_global(self, var_name: str):
        info = self.global_decl_src.get(var_name)
        if info:
            fname, line, text = info
            self.emit(f"; {fname} {line}: {text}")

    def _load_sym_addr(self, sym_name: str):
        self.emit(f"\tLDA #<{sym_name}")
        self.emit(f"\tLDX #>{sym_name}")

    def _gen_literal(self, expr: IntLiteral):
        t = self.tc.check(expr)
        val = expr.value
        self.emit(f"\tLDA #{val & 0xFF}")
        # self.emit(f'; {t}')
        if t.sem_type.base == "WORD":
            self.emit(f"\tLDX #{(val >> 8) & 0xFF}")


    def _gen_identifier(self, expr: Identifier):
        t = self.tc.check(expr)
        sym = self.current_symtab.lookup(expr.name)

        if sym.is_const:
            if sym.const_value is None:
                raise SemanticError(f"Constant '{sym.name}' has no value")
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
        t = self.tc.check(expr)

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
            self.emit("\tINY")
            self.emit("\tLDX (TMP0),Y")

    def _gen_subscript(self, expr: SubscriptExpr, load_only: bool):
        # only support array identifiers
        if not isinstance(expr.array, Identifier):
            raise SemanticError("Subscript array must be identifier")

        sym = self.current_symtab.lookup(expr.array.name)
        width = 2 if sym.type.base == "WORD" else 1

        # base address -> TMP0/TMP0+1
        self._load_sym_addr(sym.asm_name())
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP0+1")

        # index
        self.gen_expr(expr.index)
        self.emit("\tCLC")
        self.emit("\tADC TMP0")
        self.emit("\tSTA TMP0")
        carry_lbl = self.new_label("CARRY")
        self.emit(f"\tBCC {carry_lbl}")
        self.emit("\tINC TMP0+1")
        self.emit(f"{carry_lbl}:")

        if width == 2:
            # multiply by 2 (simple shift left)
            self.emit("\tASL TMP0")
            self.emit("\tROL TMP0+1")

        if load_only:
            self.emit("\tLDY #0")
            self.emit("\tLDA (TMP0),Y")
            if width == 2:
                self.emit("\tINY")
                self.emit("\tLDX (TMP0),Y")
            else:
                self.emit("\tLDX #0")
        else:
            # RHS already in A/X
            self.emit("\tLDY #0")
            self.emit("\tSTA (TMP0),Y")
            if width == 2:
                self.emit("\tINY")
                self.emit("\tSTX (TMP0),Y")

    def _gen_binary(self, expr: BinaryExpr):
        t = self.tc.check(expr)
        left_t = self.tc.check(expr.left)
        right_t = self.tc.check(expr.right)
        
        # Determine operand sizes
        left_16 = left_t.sem_type.base == "WORD"
        right_16 = right_t.sem_type.base == "WORD"
        result_16 = t.sem_type.base == "WORD"

        # Generate left operand
        self.gen_expr(expr.left)
        self.emit("\tSTA TMP0")
        self.emit("\tSTX TMP1")

        # Generate right operand
        self.gen_expr(expr.right)
        
        # Handle different operations
        if expr.op == BinOp.ADD:
            self._gen_add(result_16)
        elif expr.op == BinOp.SUB:
            self._gen_sub(result_16)
        elif expr.op == BinOp.MUL:
            self._gen_mul(left_16, right_16, result_16)
        elif expr.op == BinOp.DIV:
            self._gen_div(left_16, right_16, result_16)
        elif expr.op == BinOp.MOD:
            self._gen_mod(left_16, right_16, result_16)
    
    def _gen_add(self, is_16bit: bool):
        """Generate addition (inline)"""
        if is_16bit:
            # 16-bit: (A,X) + (TMP0,TMP1) → (A,X)
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
            self.emit("\tTAY")
            self.emit("\tTXA")
            self.emit("\tADC TMP1")
            self.emit("\tTAX")
            self.emit("\tTYA")
        else:
            # 8-bit: A + TMP0 → A
            self.emit("\tCLC")
            self.emit("\tADC TMP0")
    
    def _gen_sub(self, is_16bit: bool):
        """Generate subtraction (inline): TMP0 - A"""
        if is_16bit:
            # 16-bit: (TMP0,TMP1) - (A,X) → (A,X)
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
            self.emit("\tSTA TMP2")
            self.emit("\tSEC")
            self.emit("\tLDA TMP0")
            self.emit("\tSBC TMP2")
    
    def _gen_mul(self, left_16: bool, right_16: bool, result_16: bool):
        """Generate multiplication (call runtime routine)"""
        self.math_runtime_needed = True
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
        self.math_runtime_needed = True
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
        self.math_runtime_needed = True
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
        if expr.op == BinOp.LAND:
            lbl_false = self.new_label("LAND_FALSE")
            lbl_end   = self.new_label("LAND_END")

            # lhs
            self.gen_expr(expr.left)
            self.emit("\tORA X")
            self.emit(f"\tBEQ {lbl_false}")   # lhs == 0 → false

            # rhs
            self.gen_expr(expr.right)
            self.emit("\tORA X")
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
            self.emit("\tORA X")
            self.emit(f"\tBNE {lbl_true}")   # lhs != 0 → true

            # rhs
            self.gen_expr(expr.right)
            self.emit("\tORA X")
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
                    arg_type = self.tc.check(arg)
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

        lhs_t = self.tc.check(lhs)
        rhs_t = self.tc.check(rhs)

        # typová kompatibilita                
        if not isinstance(lhs, (Identifier, DerefExpr, SubscriptExpr)):
            raise SemanticError("Left side of assignment is not assignable")

        if lhs_t.kind == ExprKind.LVALUE:
            # RHS LVALUE means we're reading from that location (convert to VALUE semantically)
            if rhs_t.kind == ExprKind.LVALUE:
                # Both sides are lvalues, treat RHS as reading a value
                rhs_t = ExprType(rhs_t.sem_type, ExprKind.VALUE)
            
            if rhs_t.kind != ExprKind.VALUE:
                raise SemanticError("Cannot assign address to lvalue")

            # Allow implicit narrowing (WORD to BYTE) - just truncate low byte
            # This is common in low-level code (e.g., ptr^ = word_counter)
        
        # Allow ADDR = ADDR for pointer assignments
        if lhs_t.kind == ExprKind.ADDR and lhs_t.sem_type.is_pointer:
            if rhs_t.kind != ExprKind.ADDR and rhs_t.kind != ExprKind.VALUE:
                raise SemanticError("Cannot assign to pointer")
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
                        if is_word:
                            for _ in range(k):
                                self._emit_inc_word(asm)
                        else:
                            for _ in range(k):
                                self.emit(f"\tINC {asm}")
                        return

                # var = var - k (k=1..3) ; only when self - const on rhs
                if rhs.op == BinOp.SUB and is_self(rhs.left) and k_right is not None:
                    k = k_right
                    if is_word:
                        for _ in range(k):
                            self._emit_dec_word(asm)
                    else:
                        for _ in range(k):
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

        if isinstance(lhs, Identifier):
            sym = self.current_symtab.lookup(lhs.name)

            if sym.is_const:
                raise SemanticError("Cannot assign to const")

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
            fname, line, text = pinfo
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
                    arg_type = self.tc.check(arg)
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
            self.gen_expr(cond)
            self.emit("\tORA X")    # WORD-safe
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
                self.gen_expr(cond)
                self.emit("\tORA X")
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
                raise SemanticError("BREAK outside of loop")
            _, end_label = self.loop_stack[-1]
            self.emit(f"\tJMP {end_label}")
            return

        if isinstance(stmt, ContinueStmt):
            if not self.loop_stack:
                raise SemanticError("CONTINUE outside of loop")
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
        left_t = self.tc.check(expr.left)
        right_t = self.tc.check(expr.right)
        is_16bit = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"
        
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
            self.emit("\tCMP TMP0")

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
        left_t = self.tc.check(cond.left)
        right_t = self.tc.check(cond.right)
        is_16bit = left_t.sem_type.base == "WORD" or right_t.sem_type.base == "WORD"

        cmp_lo = "TMP0"
        cmp_hi = "TMP0+1"

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
            # Evaluate right into TMP0/(TMP0+1)
            self.gen_expr(cond.right)
            if is_16bit and right_t.sem_type.base != "WORD":
                self.emit("\tLDX #0")
            self.emit("\tSTA TMP0")
            if is_16bit:
                self.emit("\tSTX TMP0+1")

            # Evaluate left into A/X
            self.gen_expr(cond.left)
            if is_16bit and left_t.sem_type.base != "WORD":
                self.emit("\tLDX #0")

        # Emit direct branches to external labels (short branches to true, absolute JMP to false where needed)
        # Use immediate or memory operand based on whether right side is constant
        if not use_immediate:
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

[x] extend peepholes to fold LDA #c / STA / LDA #c / STA into a single load, 
[x] add INC/DEC pair cancellations, 
[x] run peephole before math/runtime footer too if we emit more helpers later.
[x] line numbers in generated code with source file command 
[x] fix tokenizer to handle character literals and escape sequences properly
[x] ASM for inile assembler entry. 
[x] fix module handling to remove unused functions and procs from modules
[x] .ifdef and related directives
[x] test file without main() should fail compilation
[x] escape sequences for ASCII: \n, \t, \r, \", \', \\
[x] update grammar.ebnf
[x] .segment "name" - removed
[x] binary operators &, | 
[x] struct support
[x] malloc, free? not as internal library
[x] clean up directives with #
[x] improve error messages 
    filename:line:column: severity: message
    Example:
    main.zap:12:5: error: Undefined symbol 'TEMP_VAR'
    main.zap:45:10: warning: Unreachable code detected



[x] implement module constructors? No. 
[x] fix wrong code generation as ORA X is wrong
[x] compiler defines in command line - tested also with conflicting defines and PROC name
[x] Describe how to share identifiers declard in ZAP! in ASM blocks
[ ] Introduce ZAP! to github:
[ ] Add to GitHub Linguist
You could submit your ZAP! language definition to the GitHub Linguist project. This would get ZAP1 officially recognized and syntax-highlighted on GitHub. You already have a good start with the zap.tmLanguage.json file in your repo.
Steps:
- Format your language definition according to Linguist's requirements
- Submit a PR to the Linguist repository with your language definition
- Once merged, GitHub will automatically highlight ZAP! code blocks

[x] "get address" operator @
    Implemented:
    - Parses @ for address-of operator
    - Semantic analysis validates operands (variables, array elements, struct fields)
    - Code generation for all addressable types
    - Returns WORD (16-bit) address preserving base type
    - Works with variables, arrays, structs, and their fields
    - Supports both global and local scopes
[x] Const struct initialization syntax 
    
    const S s2 = { 3, 4 };  ; regular struct initialization

    All struct elements must be initialized.

[x] Multi-dimensional arrays - all data in BSS
[x] Logical NOT operator (!) implementation and fix
[x] Extensible tests for every possible aspect of ZAP language with error messages review
[x] Review of generated unoptimized code - BYTE and WORD arithmetic optimized
    - Fast path for byte ADD/SUB: 3 instructions instead of 15+
    - Fast path for word ADD/SUB: 9 instructions instead of 19+
    - Direct 16-bit arithmetic without temporary register shuffle
[x] Peephole optimization rework.

[x] Review VS Code integration files
    [x] Build on Ctrl-Shift-Z 
    [ ] Ctrl+Shift+P command "Build: ZAP: Compile current file" - recheck hotkeys
    
[ ] Tutorials with examples.
[x] .error, .warning directives


Generated code review checklist:
----------------------------------------------
To optimize:
[x] 
; /home/dusan/src/ZAP-compiler/tests/pass/012-operator-precedence/012-operator-precedence.zap 5:     byte y = x + x + x
	LDA _MAIN_X
	CLC
	ADC _MAIN_X
	STA TMP1
	LDA _MAIN_X
	CLC
	ADC TMP1
	STA _MAIN_Y
; could be optimized to
    LDA _MAIN_X 
    CLC
    ADC _MAIN_X
    ADC _MAIN_X
    STA _MAIN_Y 

---
[x] *2 /2 optimize to ASL, LSR

[x] different optimization for 6502 and 65c02
	LDA #$0A
	STA _MAIN_X
; C:\Users\dusan.holub\src\ZAP-compiler\tests\pass\024-increment-decrement\024-increment-decrement.zap 5:     x = x + 1
	INC _MAIN_X
; C:\Users\dusan.holub\src\ZAP-compiler\tests\pass\024-increment-decrement\024-increment-decrement.zap 6:     result = x
	LDA _MAIN_X
    STA RESULT

Peephole optimization:
[x]
MAIN:
; /home/dusan/src/ZAP-compiler/tests/pass/014-structs-simple/014-structs-simple.zap 9:     p.age = 42
	LDA #42
	STA TMP2
	LDA _MAIN_P
	LDY #0
	LDA TMP2
	STA _MAIN_P
; /home/dusan/src/ZAP-compiler/tests/pass/014-structs-simple/014-structs-simple.zap 10:     result = p.age
	LDA _MAIN_P
	STA _RESULT
	RTS

[x] !!! Peephole optimization must be disabled for ASM blocks and for PORT variables !!!
 
[x] Only if there is no label before second JMP
 	JMP endwhile_2
	JMP endif_5

[x] Define symbols for .ifdef according to cmd line CPU option
    Symbols 6502 or 65C02 defined according to command line option -cpu

[x] static for local variables
    STATIC on global variable - should error
    STATIC on const variable - should error
    STATIC without initializer - should error

[x] implicit parameters for functions and procedures

proc test1(byte a, byte b=5, byte c = 8)
end

proc main
    test1(1, 2)
    test1(3)    ; implies b is initialized to its default value of 5
    test1(4, , 9) ; implies b is initialized to its default value of 5
end

[x] library directory as command line -I <filename> option
    - first search current file directory, thern current + relative to -I
    - then search absolute .include or .incbin


[x] PORT modifier implementation
    - implemented PORT modifier for variables mapped to hardware ports  

    port byte POKEY_AUDF1 @$D200

[x] Attribute to keep not called functions and procedures in the final binary. Or #KEEP, #NOEXPORT, attribute
    - proc FileHeader() #KEEP #NOEXPORT
    - useful for library functions that may be used from ASM blocks
[x] Consider #RD #WR for PORT variables
    - #RD for read-only ports
    - #WR for write-only ports
    byte PIA_DATA $D300 #PORT #RD
[x] Implemet #attributes in compiler

[x] consider changing port TO #PORT to be consistent with other directives starting with #
[x] resolve syntaxt highlighting for # directives in VS Code extension

[x] ASM must properly ignore every ZAP! syntax inside ASM block till END

[x] remove .segment from ZAP directives - use it in ASM blocks only

[x] Implement .error "string", .warning "string", .info "string"

[x] improve and unify error messages for:
    - [x] undeclared identifier
    - [x] type mismatch
    - [x] wrong number of parameters in function/proc call
    - [x] invalid operand for operator
    - [x] invalid initializer for variable
    - [x] invalid struct field access
    - [x] array index out of bounds (if constant)
    - [x] invalid use of CONST, STATIC, PORT modifiers    

To check - enhance tests
[x] Pointer assignment to and from WORD 
[x] -I command line option for library path
[x] Propagation of module symbols to including files
[x] Module constructors
    proc CONSTRUCTOR() #KEEP #NOEXPORT
[x] Address-of operator @
[x] Const struct initialization syntax 
[x] Multi-dimensional arrays
[x] Logical NOT operator (!)
[x] STATIC local variable must have initial value
[x] CONST static local variable = nonsense
[x] CONST without initial value should error
[x] STATIC on global variable should error
[x] STATIC on CONST variable should error
[x] KEEP keyword to keep unused functions and procedures in the final binary

[x] ASM / END act as comment in VSCode syntax highlighting
    Hybrid syntax highlighting now works
[ ] Check VSCode and compiler syntax highlighting for operators - OR etc.
[x] .segment between ASM and END fail for some reason
[x] Array can be initialized:
    byte arr[3] = {10, 20, 30}
[x] Errors in Problems tab can not open file
[x] ENUM?

[x] Enhance STRUCT declarations:

struct VIA_STRUCT #port 
    byte ORB    #rd
    byte ORA
    byte DDRB
    byte DDRA
    byte T1CL   #wr
    byte T1CH
    byte T1LL
    byte T1LH
    byte T2CL
    byte T2CH
    byte SR
    byte ACR
    byte PCR
    byte IFR
    byte IER
    byte PRA 
    byte PRB 
end

VIA_STRUCT VIA1 @40000 
VIA_STRUCT VIA2 @40016 

[x] maybe struct NAME #port #rd for all struct members?

[x] Get high / low byte from two byte variables: low(x) and high(x) as internal functions
[x] Implement sizeof(<struct name>)

[x] Tests for STRUCT name #port #rd #wr
[x] Tests for ENUMs
[x] Change enum usage to qualified access Color.Red (implemented — supports `EnumName.Member` via `.`; unqualified names remain available for backward compatibility)
- Implementation notes:
  - Parser accepts `.` qualified field access for enums (and structs) and does not accept `:`.
  - `EnumAnalyzer` registers enum members as top-level `const` symbols for backward compat and also records enums for qualified lookup.
  - Code generation treats qualified enum access as immediates when used in expressions.

High impact
[x] Strength‑reduce DIV/MOD by power‑of‑two constants: still lowers to runtime DIV8 with full MATH_OP setup. For byte types, LSR/ASR and AND can replace the call. Example: 020-division_6502_-O1.s:41-55
[x] Compare-to-zero loop simplification: count > 0 becomes CMP #0 + BEQ + BCS + JMP. For unsigned, it can be a single BNE (or BEQ to exit). This is codegen structure, not peephole. Example: 049-control-flow-while_O1.s:42-48
[x] Avoid operand shuffling for 16×8 multiply: inputs are moved through MATH_OP0/1/2 to match routine layout. If codegen matched the runtime ABI (or a second ABI), you can skip several loads/stores per call. Example: 099-mul-div-mod-variants_O1.s:136-151

Medium impact
[x] Compile‑time boolean folding: constant boolean expressions still build temps and branch, instead of emitting a direct LDA #1/0; STA. Example: 058-operators-comparison_O1.s:39-44
[x] Expression scheduling to reduce stack saves: expression trees like a + b*(c+1) save A/X on the stack before the multiply and then restore. Reordering to evaluate the multiply first or spill a to a temp would avoid PHA/PLA. Example: 096-arithmetic-16bit_O1.s:54-90
[x] Immediate 16‑bit arithmetic for small constants: word arithmetic with small literals sometimes 
materializes a temp word before SBC/ADC. Emit ADC #$lo then ADC #$hi directly. Example: 096-arithmetic-16bit_O1.s:100-108

Low impact
[x] 8‑bit mul/div/mod ABI could avoid high‑byte clears: byte-only ops still zero MATH_OP0+1/MATH_OP3 each time. A byte‑only calling convention would remove extra stores. Example: 099-mul-div-mod-variants_O1.s:126-133
[x] Function argument passing via globals: calls like addw(1000) store to _ADDW_A/_ADDW_B and then JSR. Passing in A/X would cut memory traffic and reduce call footprint. Example: 095-add-call-16bit_O1.s:53-61
[x] Return values in registers
[x] ; /home/dusan/src/ZAP-compiler/tests/pass/058-operators-comparison/058-operators-comparison.zap 6:     if (3 < 5) && (7 == 7) then
	LDA #$01
	BNE BR_SKIP_4
	JMP else_1
->
	JMP BR_SKIP_4
	JMP else_1
->
	JMP BR_SKIP_4
->
    do not emit ELSE branch
-> 
    JMP BR_SKIP_4 is not needed

[x] Document registers usage in FUNC / PROC parameetrs passing

Possible changes in ZAP Design
---------------------------------------

proc main()
    byte x = 50
    byte y[] = "ABC"
    
    byte z = x > y  ; comparsion requires values - ???
end


========================================

c → MATH0
MATH0 + 1 → MATH0          (ADD routine)
b → A/X (load)
MUL16(A/X, MATH0) → MATH0
a → A/X (load)
ADD(A/X, MATH0) → MATH0    (ADD routine)
MATH0 → result

1. AST-to-RPN converter - Walk AST, build postfix stack
2. Temp allocator - Assign temporaries for intermediate results
3. RPN code generator - Emit code from RPN (instead of current recursive descent)
4. Refactor gen_expr() - Currently recursive; needs to become postfix-based
5. Extensive regression testing - All 100+ tests need verification

---

RPN CODE GENERATION REFACTOR (Started Feb 11, 2026)
===================================================

Phase 1: COMPLETED ✓ (Feb 11, 2026 - Session 1)
- Added SET_MATH0, SET_MATH1, GET_MATH0 helper routines (18 bytes total)
- Set up RPN infrastructure in CodeGen class (rpn_enabled, rpn_eval_stack, etc.)
- Created RPNNode data structure for RPN representation
- Implemented ast_to_rpn() and rpn_eval_to_code() skeletons
- All existing tests still pass (100% backward compatible)

Phase 2-3: COMPLETED ✓ (Feb 11, 2026 - Session 2)
- Completed ast_to_rpn() implementation (65+ lines)
  * Converts BinaryExpr/UnaryExpr to proper RPN sequence via recursive tree walk
  * Handles all leaf node types (constants, variables, array/field access, deref, calls)
  * Proper 16-bit vs 8-bit type tracking through evaluation
  * Respects operator precedence from AST structure
- Completed rpn_eval_to_code() implementation (180+ lines)
  * Stack-based RPN evaluation with A/X operand carrier
  * Loads operands to A/X with proper widths (8-bit or 16-bit)
  * Stores operands via JSR SET_MATH0/SET_MATH1
  * Invokes appropriate math routines (ADD16, SUB16, MUL8, DIV8, MOD16, etc.)
  * Auto-selects routine based on operand widths
  * Handles unary operators (!, ~)
  * Extracts final result to A/X via GET_MATH0
- Integrated RPN into gen_expr() BinaryExpr handler (conditional path)
  * Routes ADD/SUB/MUL/DIV/MOD through RPN when rpn_enabled=True
  * Falls back to traditional handlers for logical/comparison/bitwise
  * Seamless backward compatibility (rpn_enabled=False by default)
- Verified: Compiler still works, backward compatible, test 096 generates 7740 bytes
- Code size savings: ~25% per operation with RPN + helpers (demonstrates 36→27 bytes)
- Documentation: RPN_PHASES_1_3_FINAL_SUMMARY.md created

Phase 4: COMPLETED ✓ (Feb 11, 2026 - Session 3)
- [x] Enabled rpn_enabled=True on full test suite (default)
- [x] Measured actual byte savings:
  * Test 096: 7,740 → 6,134 bytes (1,606 bytes saved, -20.74%)
  * Test 099: 23,238 → 17,432 bytes (5,806 bytes saved, -24.98%)
  * Average: 22.86% code size reduction
- [x] Added _is_rpn_safe() safety check to prevent crashes on array subscripts
- [x] Fixed 18 test failures by implementing fallback to traditional path for complex expressions
- [x] Final test results: 106/106 tests passing (100% success rate)
  * Before fix: 88 passed, 18 failed (82%)
  * After fix: 106 passed, 0 failed (100%) ✅
- [x] Verified: 0 regressions, stable, production-ready
- [x] Documentation: RPN_PHASE4_MEASUREMENT_REPORT.md (comprehensive report)

Key Phase 4 Achievements:
- RPN optimization confirmed effective (22.86% average)
- Backward compatibility: 100%
- Safe fallback mechanism: All test cases covered
- Code quality: Stable, no crashes, no errors

Phase 5: COMPLETED ✓ (Feb 12, 2026 - Session 4)
- [x] Extended RPN to bitwise operators (&, |, ^, <<, >>)
- [x] Added operand loading strategy for commutative vs non-commutative ops
- [x] Implemented bitwise AND/OR/XOR inline code generation in RPN path
- [x] Implemented variable and constant-folded shifts in RPN path
- [x] Fixed MATH0/MATH1 spill strategy using MATH_STACK for safe stacking
- [x] Added test 108: bitwise-shift-rpn (validates complex bitwise+shift expressions)
- [x] All 107 tests still passing (100% backward compatible)

Key Phase 5 Achievements:
- Bitwise operators now fully integrated into RPN path
- MATH_STACK spill prevents clobbering across deep nesting
- Correct operand order preservation for non-commutative ops
- Code size reduction extends to bitwise operations

Phase 6-10: COMPLETED ✓
- [x] (Phase 6) Extend to comparison operators (==, !=, <, <=, >, >=)
- [x] (Phase 6) Handle array subscripts and complex expressions in RPN
- [x] (Phase 7) Implement logical operators (&&, ||) in RPN
- [x] (Phase 8) Temp allocation & spill strategy for very deep nesting (>4 levels)
- [x] (Phase 9-10) Main gen_expr() migration & cleanup
- [x] Check pointers math
- [x] Full regression testing with RPN enabled by default


Further optimizations after implementaion completed
[x] DIV16 registers settings before calling proc.

[x] Use registers A,X,Y as much as possible for parameters in PROC and FUNC calling

[x] Analyze load/store frequency for each local across all calls
[x] Prioritize hot variables into zero page (limited resource: ~256 bytes)
[x] Run AFTER sharing (to see effective locals post-sharing)

Change generated variable naming- remove starting _:
__LVSLOT_n__CONSTRUCTOR__atari_stdio:
___CONSTRUCTOR__ATARI_STDIO_VRAM = __LVSLOT_1
___CONSTRUCTOR__ATARI_STDIO_DATA = __LVSLOT_1
___CONSTRUCTOR__ATARI_STDIO_I = __LVSLOT_2
; /home/dusan/src/ZAP-compiler/work/lib/atari/a

[x] Start Ctrl-Shift Build ZAP code on .zap extensions only

[x] Document sources *.py and *.zap

[x] Check ASM symbols name mangling

[x] Disable color rectangle in VS Code editor where #<number> is. 
[x] readme.md in ZAP plugin shall point to github docs.

[x] Not optimized variables:
; Word variables
__MEMSET_FOR_END_2:	.res 2
_MEMCPY_I:	.res 2
__MEMCPY_FOR_END_3:	.res 2

[x] Test REPEAT, UNTIL
[x] Basic test for assignment of uninitialized variable
[x] Allow direct call with const struct like ch = myfn({0, 3, 6})
[x] wrong file and position when eror is in included module

[x] Review whole documentation
[x] Check ENUM and STRUCT propagation from .module

[x] Check LONG 

    
[x] LDY #0 
; /home/dusan/src/ZAP-compiler/work/lib/atari/atari_stdio.zap 130:         ptr1^ = ptr2^
	LDY #0
	LDA (_MEMCPY_PTR2),Y
	STA __TMP2
	LDY #0
	STA (_MEMCPY_PTR1),Y

[x] codegen
; /home/dusan/src/ZAP-compiler/work/lib/atari/atari_stdio.zap 308:     if cur_xpos >= SCREEN_X_SIZE
	LDA _CUR_XPOS
	CMP #$28
	BCS __ZAP_then_68
	JMP __ZAP_REL_FALSE_PROXY_69
	JMP __ZAP_then_68
__ZAP_REL_FALSE_PROXY_69:
	JMP __ZAP_else_66
__ZAP_then_68:

to

; /home/dusan/src/ZAP-compiler/work/lib/atari/atari_stdio.zap 308:     if cur_xpos >= SCREEN_X_SIZE
	LDA _CUR_XPOS
	CMP #$28
	BCS __ZAP_then_68
	JMP __ZAP_else_66
__ZAP_then_68:


[x] enums are const:
; /home/dusan/src/ZAP-compiler/work/lib/atari/atari_stdio.zap 223:     while BOOL.TRUE
__ZAP_while_24:
	LDA #$01
	BNE __ZAP_while_body_26
	JMP __ZAP_endwhile_25
__ZAP_while_body_26:

to

; /home/dusan/src/ZAP-compiler/work/lib/atari/atari_stdio.zap 223:     while BOOL.TRUE
__ZAP_while_24:
__ZAP_while_body_26:

[x] Unify internal copy routines __COPY_BYTES and __ARRCPY

[x] Better generator
; C:\Users\dusan.holub\src\ZAP-compiler\tests\pass\138-long-control-flow\138-long-control-flow.zap 17:     while my_long
__ZAP_while_4:
	LDA _MAIN_MY_LONG
	STA __MATH0
	LDA _MAIN_MY_LONG+1
	STA __MATH0+1
	LDA _MAIN_MY_LONG+2
	STA __MATH0+2
	LDA _MAIN_MY_LONG+3
	STA __MATH0+3
	LDA __MATH0
	ORA __MATH0+1
	ORA __MATH0+2
	ORA __MATH0+3

to
    LDA _MAIN_MY_LONG    
    ORA _MAIN_MY_LONG+1
    ORA _MAIN_MY_LONG+2
    ORA _MAIN_MY_LONG+3

[x] Remove redundant LDA #$00
; C:\Users\dusan.holub\src\ZAP-compiler\tests\pass\138-long-control-flow\138-long-control-flow.zap 4:     long my_long = 65536
	LDA #$00
	STA _MAIN_MY_LONG
	STA _MAIN_MY_LONG+1
	LDA #$00
	STA _MAIN_MY_LONG+2
	STA _MAIN_MY_LONG+3

[x] Peephole? No, generator optimization.
; C:\Users\dusan.holub\src\ZAP-compiler\tests\pass\138-long-control-flow\138-long-control-flow.zap 24:     for my_long = my_long to end_val step 1
	LDA _MAIN_MY_LONG
	STA _MAIN_MY_LONG
	LDA _MAIN_MY_LONG+1
	STA _MAIN_MY_LONG+1
	LDA _MAIN_MY_LONG+2
	STA _MAIN_MY_LONG+2
	LDA _MAIN_MY_LONG+3
	STA _MAIN_MY_LONG+3


[x] Group STAs when loading values:
	LDA #$04
	STA _MAIN_END_VAL
	LDA #$00
	STA _MAIN_END_VAL+1
	LDA #$01
	STA _MAIN_END_VAL+2
	LDA #$00
	STA _MAIN_END_VAL+3
to:
	LDA #$04
	STA _MAIN_END_VAL
	LDA #$00
	STA _MAIN_END_VAL+1
	STA _MAIN_END_VAL+3	
    LDA #$01
	STA _MAIN_END_VAL+2


[x] Check for .segment directive, it is probably still there
        if isinstance(stmt, SegmentDirective):
            self.emit(f'.segment "{stmt.name}"')
            return

[ ] Check array of structs and arrays in struct

[ ] Check arrays init and copy for lenghts 0, $FF

[ ] Auto short branches?

[x] Syntax sugar = compound assignent
<var> <operator>= <expr>


[ ] Add cmdline parameters for CODE, BSS, DATA segment names SEGC, SEGB, SEGD?


[ ] This is a pre-existing bug — ADC #0A should be ADC #$0A. Let me find the emit location: ${expr ...:02X}
- check for all datatypes and operations

[x] replace IF logic:
; /home/dusan/src/ZAP-compiler/tests/pass/140-compound-assign/140-compound-assign.zap 56:     if b == 2
	LDA _MAIN_B
	CMP #$02
	BNE __ZAP_REL_ELSE_TMP_21
	BEQ __ZAP_then_20
__ZAP_REL_ELSE_TMP_21:
	JMP __ZAP_else_18
__ZAP_then_20:

to

; /home/dusan/src/ZAP-compiler/tests/pass/140-compound-assign/140-compound-assign.zap 56:     if b == 2
	LDA _MAIN_B
	CMP #$02
	BEQ __ZAP_then_20
    JMP __ZAP_REL_ELSE_18
__ZAP_then_20:

[ ] Check <expr> <comparsion operator> <expression> behavior


Closure tasks
[ ] Cosmetics in generated code
    [ ] Unify generated LDA #$00 and #0
    [ ] Empty lines
    [ ] Double -- MAIN


[ ] Change -O1 option: Default is peephole optimization on, if -O - no peephole optimizations.

[ ] Check expressions evaluation for assign and other occurences to be the same

[ ] Check for variable uninitialized for all types

[ ] Remove compiler's debug messages


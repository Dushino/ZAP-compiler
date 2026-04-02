; Example: ref_03_variables.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Variables" (lines 450-619)
;
; Demonstrates: global/local variables, const, static, fixed-address, scope, multiple decl
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Global Variables ---
byte global_x = 0
word gcounter = 0
const byte VERSION = 1

; --- Fixed-Address Variables ---
byte SCREEN_DMA @$D400
word DISPLAY_LIST_PTR @$D402
byte PLAYER0_X @$D000

; --- Variable Initialization ---
byte init_val = 42
word init_word = 1000
byte arr_init[] = {1, 2, 3, 4, 5}
byte text[] = "Hello"

; --- Variable Scope ---
byte scope_x = 10

proc test_scope1()
    byte scope_x = 20   ; Local x shadows global
    scope_x = scope_x + 1
end

proc test_scope2()
    scope_x = scope_x + 1   ; Uses global x
end

; --- Static Local Variables ---
proc counter_increment()
    static byte count = 0
    count = count + 1
end

; --- Uninitialized Variable Detection (valid case) ---
proc safe()
    byte x = 0          ; Must initialize
    byte y = x + 10     ; OK: x is initialized
end

; --- Multiple Declarations ---
byte mx, my, mz           ; Three bytes
byte ma = 1, mb = 2       ; With initialization
byte ^mp1                  ; Byte pointer
byte ^mp2                  ; Byte pointer

proc main()
    byte local_var = 0
    byte temp = 0
    const byte MAX_LOCAL = 100

    local_var = temp + MAX_LOCAL

    test_scope1()
    test_scope2()
    counter_increment()
    counter_increment()
    counter_increment()
    safe()
end

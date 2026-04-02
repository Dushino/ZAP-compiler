; Example: adv_05_optimization.zap
; Source: ADVANCED_TOPICS.md, section "Optimization Techniques" (lines 867-1002)
;
; Demonstrates: constant folding, DCE, lookup tables, byte vs word, pointer cache
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Constant Folding ---
const byte SIZE = 100
byte data[150]

proc init()
    byte x = 2 + 3 * 4  ; x = 14 (computed at compile-time)
end

; --- Dead Code Elimination ---
proc dce_example()
    return
    ; Code after return is removed by DCE
end

; --- Lookup Table ---
byte sine_table[] = {0, 13, 26, 38, 50, 62, 74, 85, 95, 104, 112, 120, 127}

proc sin_table_lookup()
    byte angle = 10
    byte value = sine_table[angle]
end

; --- Byte vs Word ---
byte small_value = 100       ; Use byte when possible (faster, smaller)
word large_value = 40000     ; Use word only if necessary

; --- Minimize Pointer Dereference ---
proc cache_deref()
    byte d = 42
    byte ^p = @d

    ; Cache value instead of repeated derefs
    byte value = p^
    byte v1 = value
    byte v2 = value
    byte v3 = value
end

; --- Binary Number Literals ---
byte b1 = %10101010     ; Binary
byte b2 = %00001010     ; Binary (percent prefix)
byte h1 = $FF           ; Hex (dollar sign)
byte d1 = 255           ; Decimal

proc main()
    init()
    dce_example()
    sin_table_lookup()
    cache_deref()
end

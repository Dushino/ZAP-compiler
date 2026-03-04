; Example: adv_07_safety.zap
; Source: ADVANCED_TOPICS.md, section "Safety Features" (lines 1814-2142)
;
; Demonstrates: initialization methods, control flow handling, special cases

byte result = 0

; --- Explicit Initializer ---
proc test_explicit()
    byte x = 42        ; x is initialized
    byte y = x + 10    ; OK: x is initialized, y becomes initialized
    result = y
end

; --- Assignment Statement ---
proc test_assignment()
    byte x = 0
    byte y = 0
    x = 42             ; x becomes initialized here
    y = x + 10         ; OK: x is initialized
    result = y
end

; --- FOR Loop Variables ---
proc test_for_loop()
    byte i = 0
    for i = 0 to 10    ; i is initialized by the FOR loop
        result = i     ; OK: i is initialized
    end
end

; --- REPEAT-UNTIL ---
proc test_repeat()
    byte x = 0

    repeat
        x = 42
    until x > 10

    result = x         ; OK: x is initialized (loop runs at least once)
end

; --- Const Variables ---
proc test_const()
    const byte x = 42
    result = x         ; OK: const variables are always initialized
end

; --- Fixed-Address Variables ---
byte PORT_A @$D000

proc test_fixed_addr()
    result = PORT_A    ; OK: fixed-address variables are always initialized
end

; --- Struct Variables ---
struct Point
    byte x
    byte y
end

proc test_struct()
    Point p = {0, 0}
    byte ^pp = @p
    pp^ = 3
    result = p.x       ; OK: structs are considered initialized
end

; --- Parameters ---
proc test_params(byte x)
    result = x         ; OK: parameters are always initialized
end

proc main()
    test_explicit()
    test_assignment()
    test_for_loop()
    test_repeat()
    test_const()
    test_fixed_addr()
    test_struct()
    test_params(42)
end

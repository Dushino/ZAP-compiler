; Example: gs_06_functions.zap
; Source: GETTING_STARTED.md, section "Functions and Procedures" (lines 591-707)
;
; Demonstrates: procedures, functions, parameters, return early, utility functions

byte x = 10

proc say_hello()
    ; Just do something
end

proc increment(byte val)
    val = val + 1   ; Changes local copy only
end

func byte double_value(byte input)
    return input * 2
end

func word combine_bytes(byte low, byte high)
    return low + (high * 256)
end

proc validate_input(byte input)
    if input == 0
        return      ; Exit procedure early
    end
    ; Rest of validation here
end

func byte min(byte a, byte b)
    if a < b
        return a
    end
    return b
end

func byte max(byte a, byte b)
    if a > b
        return a
    end
    return b
end

func byte abs_diff(byte a, byte b)
    if a > b
        return a - b
    end
    return b - a
end

proc main()
    ; All locals declared first (ZAP rule)
    byte result = 0
    word address = 0
    byte smallest = 0
    byte largest = 0
    byte distance = 0

    say_hello()
    increment(x)            ; x is still 10 (procedure got a copy)
    result = double_value(21)       ; result = 42
    address = combine_bytes(0, $40) ; address = $4000
    validate_input(5)
    smallest = min(10, 20)          ; 10
    largest = max(10, 20)           ; 20
    distance = abs_diff(5, 15)      ; 10
end

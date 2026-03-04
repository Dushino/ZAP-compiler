; Example: ref_07_control_flow.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Control Flow" (lines 992-1515)
;
; Demonstrates: if/else, switch, while, repeat-until, for, break, continue

; --- if-else ---
proc if_example()
    byte x = 5

    ; Simple if
    if x == 5
        ; This executes
    end

    ; if-else
    if x > 10
        ; x is greater than 10
    else
        ; x is 10 or less
    end

    ; Nested if
    if x > 0
        if x < 100
            ; x is between 0 and 100
        end
    end
end

; --- Switch: break, fall-through, continue ---
proc switch_break()
    byte x = 1

    switch x
        case 1
            x = 10
            break
        case 2
            x = 20
            break
        default
            x = 0
    end
end

proc switch_fallthrough()
    byte x = 1
    byte y = 0

    switch x
        case 1
            y = 1       ; No break, falls through to case 2
        case 2
            y = 2       ; Executes if x is 1 OR 2
            break
        default
            y = 0
    end
end

proc switch_no_default()
    byte x = 7
    byte hit = 0

    switch x
        case 1
            hit = 1
            break
        case 2
            hit = 2
            break
    end
    ; x is 7, no case matches → hit stays 0
end

proc switch_mutation()
    byte var = 1

    switch var
        case 1
            var = 2         ; changes var, but dispatch already matched case 1
            break
        case 2
            ; This does NOT run
    end
end

proc continue_in_switch()
    byte i = 0
    byte cnt = 0

    while i < 5
        i = i + 1
        switch i
        case 3
            continue    ; skip cnt++ for i==3; jumps to while condition
        end
        cnt = cnt + 1   ; runs for i=1,2,4,5
    end
    ; cnt == 4
end

; --- while ---
proc while_example()
    byte count = 0
    byte x = 0

    while count < 10
        count = count + 1
    end

    ; Loop with break
    while 1
        x = x + 1
        if x == 100
            break
        end
    end
end

; --- repeat-until ---
proc repeat_example()
    byte count = 0

    repeat
        count = count + 1
    until count == 5
end

proc repeat_break_continue()
    byte i = 0
    byte j = 0
    byte cnt = 0

    ; break: stop early
    repeat
        i = i + 1
        if i == 3
            break
        end
    until i == 10

    ; continue: jump to until-condition
    repeat
        j = j + 1
        if j == 2
            continue
        end
        cnt = cnt + 1
    until j == 4
    ; cnt == 3
end

; --- for ---
proc for_example()
    byte i = 0

    ; Basic for loop
    for i = 0 to 9
        ; Execute 9 times (0-8)
    end

    ; For loop with step
    for i = 0 to 100 step 10
        ; i = 0, 10, 20, ..., 90
    end

    ; With break
    for i = 0 to 255
        if i == 128
            break
        end
    end
end

; --- LONG for loop ---
proc long_for_example()
    long i = 0
    long start_val = 65536
    long end_val = 65540

    for i = start_val to end_val step 1
        ; Iterates 4 times
    end
end

; --- Expression bounds ---
proc expr_bounds_example()
    byte i = 0
    byte a = 2
    byte b = 5
    word w = 0
    word ws = 5

    for i = a + 1 to b * 2
        ; i = 3, 4, 5, 6, 7, 8, 9
    end

    for w = 0 to 20 step ws
        ; w = 0, 5, 10, 15
    end
end

; --- Pointer as loop variable ---
proc pointer_loop_example()
    byte arr[4]
    byte ^ptr = @arr

    for ptr = @arr[0] to @arr[0] + 4
        ptr^ = 1
    end
    ; arr is now [1, 1, 1, 1]
end

; --- Dereferenced pointer as end bound ---
proc deref_end_example()
    byte target = 6
    byte ^ptr = @target
    byte i = 0
    byte cnt = 0

    cnt = 0
    for i = 0 to ptr^
        cnt = cnt + 1
    end
    ; cnt == 6
end

; --- Zero/Non-Zero Evaluation ---
proc zero_evaluation()
    byte x = 0
    byte y = 1

    if x
    end    ; False (x is 0)

    if y
    end    ; True (y is non-zero)
end

; --- LONG Truthiness ---
proc long_truthiness()
    long counter = 65536

    if counter
        ; True — upper bytes are non-zero
    end

    while counter
        counter = counter - 1
    end
end

; --- continue in while, for, repeat ---
proc continue_example()
    byte i = 0
    byte sum = 0
    byte j = 0
    byte cnt = 0

    ; In while: skip even numbers
    while i < 10
        i = i + 1
        if i & 1 == 0
            continue
        end
        sum = sum + i
    end

    ; In repeat-until
    repeat
        j = j + 1
        if j == 2
            continue
        end
        cnt = cnt + 1
    until j == 5
end

proc main()
    if_example()
    switch_break()
    switch_fallthrough()
    switch_no_default()
    switch_mutation()
    continue_in_switch()
    while_example()
    repeat_example()
    repeat_break_continue()
    for_example()
    long_for_example()
    expr_bounds_example()
    pointer_loop_example()
    deref_end_example()
    zero_evaluation()
    long_truthiness()
    continue_example()
end

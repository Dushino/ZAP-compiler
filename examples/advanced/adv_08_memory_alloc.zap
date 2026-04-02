; Example: adv_08_memory_alloc.zap
; Source: ADVANCED_TOPICS.md, section "Memory Allocation Details" (lines 1517-1813)
;
; Demonstrates: memory segments, slot sharing, ZP prioritization
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Fixed-Address Variables ---
word port_a @$FF00

; --- Scalar Variables ---
proc calculate()
    byte x = 10
    byte y = 20
    word total = 0
    total = x + y
end

; --- Arrays ---
proc process()
    byte buffer[256]   ; Goes to BSS, too large for ZP
    byte temp[4]       ; Still goes to BSS (arrays always in BSS)
    buffer[0] = 1
    temp[0] = 2
end

; --- Structs ---
struct point
    byte x
    byte y
end

; --- Slot Sharing Example ---
proc slot_example()
    word x = 100
    word y = 200
    word z = x + y
end

; --- ZP Priority Example ---
byte counter_data[256]

proc loop_demo()
    byte counter = 0           ; Lower priority
    byte total = 0             ; Higher priority (more accesses in loop)

    while counter < 10
        total = total + counter
        counter = counter + 1
    end
end

proc main()
    point p = {0, 0}
    byte ^ptr_p = @p

    calculate()
    process()
    slot_example()
    loop_demo()

    ptr_p^ = 5
end

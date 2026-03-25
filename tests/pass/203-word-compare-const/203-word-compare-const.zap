; Test 203: Word-vs-constant comparison operators
; Verifies correct codegen for LT, LE, GT, GE, EQ, NE
; with word identifier vs constant in conditional branches.
; Covers edge cases where high bytes differ.

byte result @40000 = 0

proc main()
    word i
    word count = 0

    ; --- LT tests ---
    ; $0100 < $0200 → true
    i = 256
    if i < 512
        result += 1     ; +1
    end

    ; $0300 < $02FF → false (high > const_hi, was buggy without BNE)
    i = 768
    if i < 767
        result += 100   ; should NOT happen
    end

    ; $0200 < $0200 → false (equal)
    i = 512
    if i < 512
        result += 100
    end

    ; $01FF < $0200 → true
    i = 511
    if i < 512
        result += 1     ; +2
    end

    ; --- LE tests ---
    ; $0200 <= $0200 → true (equal)
    i = 512
    if i <= 512
        result += 1     ; +3
    end

    ; $0200 <= $01FF → false (high byte equal but $0200 > $01FF; was buggy with low-first)
    i = 512
    if i <= 511
        result += 100
    end

    ; $01FF <= $0200 → true
    i = 511
    if i <= 512
        result += 1     ; +4
    end

    ; --- GT tests ---
    ; $0300 > $0200 → true
    i = 768
    if i > 512
        result += 1     ; +5
    end

    ; $0100 > $0200 → false
    i = 256
    if i > 512
        result += 100
    end

    ; $0200 > $0200 → false (equal, not greater)
    i = 512
    if i > 512
        result += 100
    end

    ; $0201 > $0200 → true
    i = 513
    if i > 512
        result += 1     ; +6
    end

    ; --- GE tests ---
    ; $0200 >= $0200 → true (equal)
    i = 512
    if i >= 512
        result += 1     ; +7
    end

    ; $0100 >= $0200 → false
    i = 256
    if i >= 512
        result += 100
    end

    ; $0201 >= $0200 → true
    i = 513
    if i >= 512
        result += 1     ; +8
    end

    ; --- EQ / NE tests ---
    ; $0200 == $0200 → true
    i = 512
    if i == 512
        result += 1     ; +9
    end

    ; $0201 != $0200 → true
    i = 513
    if i != 512
        result += 1     ; +10
    end

    ; --- For loop with word comparison (original sieve bug pattern) ---
    ; for i=0 to 300 should iterate 300 times (i = 0..299)
    count = 0
    for i = 0 to 300
        count += 1
    end
    if count == 300
        result += 1     ; +11
    end
end

; Test 204: Word index on byte and word arrays
; Verifies that array subscript with WORD index correctly
; preserves the high byte of the index (no LDX #$00 clobber).
; Also tests word array with word index (element_width==2).

byte result @40000 = 0

proc main()
    byte flags[512]
    word i
    word arr[300]
    word prime

    ; --- Test 1: Byte array write with word index ---
    ; Write marker at index 260 (beyond byte range)
    for i = 0 to 512
        flags[i] = 0
    end
    i = 260
    flags[i] = 42

    ; --- Test 2: Byte array read with word index ---
    i = 260
    if flags[i] == 42
        result += 1     ; +1
    end

    ; Verify index 0 is still 0 (not accidentally written)
    i = 0
    if flags[i] == 0
        result += 1     ; +2
    end

    ; --- Test 3: Byte array loop with word index > 255 ---
    ; Write value at index 300
    i = 300
    flags[i] = 99
    ; Read it back
    if flags[300] == 99
        result += 1     ; +3
    end

    ; --- Test 4: Word array write with word index ---
    i = 150
    arr[i] = 1234

    ; --- Test 5: Word array read with word index ---
    if arr[150] == 1234
        result += 1     ; +4
    end

    ; --- Test 6: Word array with word index > 127 ---
    ; Index 200: byte offset = 400, needs 16-bit address calc
    i = 200
    arr[i] = 5678
    if arr[200] == 5678
        result += 1     ; +5
    end

    ; --- Test 7: Word multiply with word variable (i*2+3 pattern from sieve) ---
    i = 300
    prime = i * 2 + 3
    if prime == 603
        result += 1     ; +6
    end
end

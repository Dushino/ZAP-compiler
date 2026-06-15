; Regression test: LONG array read/write via runtime variable index.
; Existing tests only use constant indices; this covers byte and word
; variable indices for both loads and stores.
;
; Checks:
;   1: larr[byte_i] READ  — i=3 → $44444444
;   2: larr[word_wi] READ  — wi=4 → $55555555
;   3: larr[byte_i] WRITE  — i=1, write $AABBCCDD, read back
;   4: larr[word_wi] WRITE  — wi=2, write $11223344, read back
;   5: larr[expr] — i=1+1 → larr[2] after write == $11223344
;   6: long array element in expression: larr[0] + larr[byte_i] (i=3)
;      $11111111 + $44444444 = $55555555
;
; result @$0200 — each passed check adds 1, expected = 6

byte result @$0200 = 0

long larr[5] = {$11111111, $22222222, $33333333, $44444444, $55555555}

proc main()
    byte i
    word wi
    long val

    ; 1: byte variable index READ
    i = 3
    val = larr[i]
    if val == $44444444
        result = result + 1
    end

    ; 2: word variable index READ
    wi = 4
    val = larr[wi]
    if val == $55555555
        result = result + 1
    end

    ; 3: byte variable index WRITE + read back
    i = 1
    larr[i] = $AABBCCDD
    if larr[1] == $AABBCCDD
        result = result + 1
    end

    ; 4: word variable index WRITE + read back
    wi = 2
    larr[wi] = $11223344
    if larr[2] == $11223344
        result = result + 1
    end

    ; 5: expression index — const 1+1=2 — read back written value
    if larr[1+1] == $11223344
        result = result + 1
    end

    ; 6: LONG array elements in arithmetic (byte index)
    i = 3
    val = larr[0] + larr[i]
    if val == $55555555
        result = result + 1
    end
end

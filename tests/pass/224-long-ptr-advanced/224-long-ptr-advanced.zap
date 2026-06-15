; Regression test: LONG pointer advanced operations.
; Covers gaps left by tests 163/166/167:
;   - pointer distance (lptr - lptr2) in elements
;   - pointer equality comparison
;   - lptr^ = long_variable (non-const RHS)
;   - for-loop walking a LONG array via pointer
;
; Checks:
;   1: distance  — @larr[3] - @larr[0] == 3
;   2: equality  — @larr[1] == @larr[1]
;   3: var write — lptr^ = lval2 → lval1 == lval2
;   4: for-loop  — sum larr[0..3] == $AAAAAAAA
;
; result @$0200 — each passed check adds 1, expected = 4

byte result @$0200 = 0

long larr[4] = {$11111111, $22222222, $33333333, $44444444}
long lval1 = $AABBCCDD
long lval2 = $11223344

proc main()
    long ^lptr
    long ^lptr2
    long dist
    long sum = 0
    byte j

    ; 1: pointer distance in elements
    lptr  = @larr[3]
    lptr2 = @larr[0]
    dist = lptr - lptr2
    if dist == 3
        result = result + 1
    end

    ; 2: pointer equality comparison
    lptr  = @larr[1]
    lptr2 = @larr[1]
    if lptr == lptr2
        result = result + 1
    end

    ; 3: write through pointer using LONG variable RHS
    lptr = @lval1
    lptr^ = lval2
    if lval1 == $11223344
        result = result + 1
    end

    ; 4: for-loop walking LONG array via pointer (stride 4 auto-scaled)
    ; for j = 0 to 4 runs j = 0,1,2,3 (exclusive bound), 4 iterations
    lptr = @larr
    for j = 0 to 4
        sum = sum + lptr^
        lptr += 1
    end
    ; $11111111+$22222222+$33333333+$44444444 = $AAAAAAAA
    if sum == $AAAAAAAA
        result = result + 1
    end
end

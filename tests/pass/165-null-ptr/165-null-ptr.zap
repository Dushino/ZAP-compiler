; GAP-22: NULL pointer checks — WORD and pointers must be compatible for compare and assign
; result accumulates bits: bit0..3 set means checks 1..4 passed

byte result @$9C40 = 0

const word NULL = $0000

proc main()
    byte target = 77
    byte ^ptr = @target

    ; Check 1: ptr != NULL (ptr points to target) → set bit 0
    if ptr != NULL
        result = result | 1
    end

    ; Check 2: NULL == ptr is false (ptr is non-null) → set bit 1
    if NULL == ptr
        ; should NOT fire
    else
        result = result | 2
    end

    ; Assign ptr to NULL (WORD constant) and re-check
    ptr = NULL

    ; Check 3: ptr == NULL after assignment → set bit 2
    if ptr == NULL
        result = result | 4
    end

    ; Check 4: ptr == $0000 (literal zero, equivalent null check) → set bit 3
    if ptr == $0000
        result = result | 8
    end

end

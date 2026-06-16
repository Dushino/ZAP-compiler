; Regression test: logical OR (||) with non-RPN-safe operands.
; Previously _gen_logical had no BinOp.LOR handler — generated no code (silent bug).
; Non-RPN-safe operands: array subscripts, struct field access, pointer deref.
;
; Checks:
;   1: arr[0] || arr[1]  — 0 || 5 == true
;   2: arr[0] || arr[2]  — 0 || 0 == false
;   3: word array: warr[0] || warr[1]  — 0 || $0100 == true
;   4: struct field: r.flag || 0  — 1 || 0 == true
;   5: && with array operands: arr[1] && arr[1]  — 5 && 5 == true
;
; result @$0200 — expected = 5

byte result @$0200 = 0

byte arr[3] = {0, 5, 0}
word warr[2] = {0, $0100}

struct Rec
    byte flag
end
Rec r

proc main()
    r.flag = 1

    ; 1: 0 || 5 → true
    if arr[0] || arr[1]
        result = result + 1
    end

    ; 2: 0 || 0 → false (result stays same)
    if arr[0] || arr[2]
    else
        result = result + 1
    end

    ; 3: 0 || $0100 → true (WORD operand)
    if warr[0] || warr[1]
        result = result + 1
    end

    ; 4: struct field || 0 → true
    if r.flag || 0
        result = result + 1
    end

    ; 5: arr[1] && arr[1] → true (both non-zero)
    if arr[1] && arr[1]
        result = result + 1
    end
end

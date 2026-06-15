; Regression test: struct with multiple LONG fields; compound assignment;
; LONG struct fields used in arithmetic expressions.
; Test 164 covers basic read/write; this covers the arithmetic gaps.
;
; Struct layout: Rec { long val; byte tag; long extra }  (9 bytes)
;
; Checks:
;   1: r1.val += 500       — 1000 + 500 = 1500
;   2: r1.val + r2.val     — 1500 + 60000 = 61500
;   3: r1.extra | r2.extra — $CAFE0000 | $0000BABE = $CAFEBABE
;   4: arr[i].val += 1     — variable-index compound assign on LONG struct field
;   5: arr[i].extra arithmetic — arr[1].extra = arr[0].extra + 1
;   6: r1.val -= 500       — 1500 - 500 = 1000
;
; result @$0200 — each passed check adds 1, expected = 6

byte result @$0200 = 0

struct Rec
    long val
    byte tag
    long extra
end

Rec r1
Rec r2
Rec rarr[3]

proc main()
    long total
    long combined
    byte i

    ; 1: compound add on LONG struct field
    r1.val = 1000
    r1.val += 500
    if r1.val == 1500
        result = result + 1
    end

    ; 2: arithmetic using two LONG struct fields as operands
    r2.val = 60000
    total = r1.val + r2.val
    if total == 61500
        result = result + 1
    end

    ; 3: bitwise OR of two LONG struct fields
    r1.extra = $CAFE0000
    r2.extra = $0000BABE
    combined = r1.extra | r2.extra
    if combined == $CAFEBABE
        result = result + 1
    end

    ; 4: compound assign on LONG field via variable array index
    rarr[0].val = 10
    rarr[1].val = 20
    i = 1
    rarr[i].val += 5
    if rarr[1].val == 25
        result = result + 1
    end

    ; 5: LONG field expression with variable array index
    rarr[0].extra = $00000100
    i = 0
    rarr[1].extra = rarr[i].extra + 1
    if rarr[1].extra == $00000101
        result = result + 1
    end

    ; 6: compound subtract on LONG struct field
    r1.val -= 500
    if r1.val == 1000
        result = result + 1
    end
end

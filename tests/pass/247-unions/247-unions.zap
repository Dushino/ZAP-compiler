; Test: union — all members share the same memory address.
; sizeof(union) = size of the largest member.

; ── 1. Basic union: byte + word overlay ─────────────────────────────────────
union UOverlay
    byte lo
    word val
end

; ── 2. Union with a byte array / word array members ─────────────────────────
union URaw
    byte bytes[4]
    word words[2]
end

; ── 3. Nested: union inside a struct ────────────────────────────────────────
struct SFrame
    byte     id
    UOverlay payload
end

; ── 4. Union containing a struct ────────────────────────────────────────────
struct SPoint
    byte x
    byte y
end

union UData
    byte   raw
    SPoint pt
end

; ── 5. Union with LONG field ─────────────────────────────────────────────────
union ULong
    byte lo
    word w
    long val
end

; ── result word used as a pass-counter ──────────────────────────────────────
word result @$0200 = 0

proc check(byte cond)
    if cond != 0
        result += 1
    end
end

proc main()
    ; All declarations first
    UOverlay u
    SFrame   f
    UData    d
    UOverlay arr[3]
    UOverlay ^uptr
    ULong    ul

    ; ── test 1: write via word, read via byte ───────────────────────────────
    u.val = $1234
    check(u.lo == $34)          ; low byte of $1234 is $34                  [1]
    check(u.val == $1234)       ; full word unchanged                        [2]

    ; ── test 2: write via byte ──────────────────────────────────────────────
    u.lo = $AB
    check(u.lo == $AB)          ; byte we wrote                             [3]

    ; ── test 3: sizeof ──────────────────────────────────────────────────────
    check(sizeof(UOverlay) == 2)    ; max(1,2) = 2                          [4]
    check(sizeof(URaw) == 4)        ; max(4,4) = 4                          [5]
    check(sizeof(UData) == 2)       ; max(1,2) = 2 (SPoint is 2 bytes)      [6]
    check(sizeof(ULong) == 4)       ; max(1,2,4) = 4                        [7]

    ; ── test 4: union as struct member ──────────────────────────────────────
    f.id = 7
    f.payload.val = $BEEF
    check(f.id == 7)                                                         ; [8]
    check(f.payload.lo == $EF)                                               ; [9]

    ; ── test 5: union containing a struct ───────────────────────────────────
    d.pt.x = 10
    d.pt.y = 20
    check(d.pt.x == 10)                                                      ; [10]
    check(d.raw == 10)          ; raw byte overlaps d.pt.x                  ; [11]

    ; ── test 6: array of unions ─────────────────────────────────────────────
    arr[0].val = $0001
    arr[1].val = $0002
    arr[2].val = $0003
    check(arr[0].lo == 1)                                                    ; [12]
    check(arr[1].lo == 2)                                                    ; [13]
    check(arr[2].lo == 3)                                                    ; [14]

    ; ── test 7: pointer to union ─────────────────────────────────────────────
    uptr = @u
    uptr^.val = $5678
    check(u.val == $5678)                                                    ; [15]
    check(uptr^.lo == $78)                                                   ; [16]

    ; ── test 8: LONG field overlay ───────────────────────────────────────────
    ul.val = $12345678
    check(ul.lo == $78)         ; low byte of long                          ; [17]
    check(ul.w  == $5678)       ; low word of long                          ; [18]
    check(ul.val == $12345678)  ; full long value preserved                 ; [19]

    ; ── test 9: write via byte, read via long ───────────────────────────────
    ul.lo = $AA
    check(ul.lo == $AA)         ; byte written into long union              ; [20]
end

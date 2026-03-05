; Test 169: LOWW() / HIGHW() on complex expressions
;
; la = $12345678, lb = $00000001
; la + lb = $12345679
;   LOWW(la + lb) = $5679
;   HIGHW(la + lb) = $1234
;   LOW(la + lb) = $79
;   HIGH(la + lb) = $56
;
; result @40000 — each passed check adds 1, expected = 6 = $06

byte result @40000 = 0
long la = $12345678
long lb = $00000001

struct LS
    long val
end

LS ls

proc main()
    word tw
    ls.val = $AABB0011

    ; --- 1: LOWW on arithmetic expression ---
    tw = LOWW(la + lb)
    if tw == $5679
        result = result + 1
    end

    ; --- 2: HIGHW on arithmetic expression ---
    tw = HIGHW(la + lb)
    if tw == $1234
        result = result + 1
    end

    ; --- 3: LOW on long arithmetic expression ---
    if LOW(la + lb) == $79
        result = result + 1
    end

    ; --- 4: HIGH on long arithmetic expression ---
    if HIGH(la + lb) == $56
        result = result + 1
    end

    ; --- 5: LOWW on struct field access ---
    tw = LOWW(ls.val)
    if tw == $0011
        result = result + 1
    end

    ; --- 6: HIGHW on struct field access ---
    tw = HIGHW(ls.val)
    if tw == $AABB
        result = result + 1
    end
end

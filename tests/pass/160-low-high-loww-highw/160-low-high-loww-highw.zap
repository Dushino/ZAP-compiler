; GAP-16: LOW() / HIGH() edge cases and new LOWW() / HIGHW() for LONG
;
; lval = $12345678:
;   byte 0 (lowest) = $78   LOW(lval)
;   byte 1          = $56   HIGH(lval)
;   bytes 0-1       = $5678 LOWW(lval)
;   bytes 2-3       = $1234 HIGHW(lval)
;   byte 2          = $34   LOW(HIGHW(lval))
;   byte 3          = $12   HIGH(HIGHW(lval))
;
; Edge cases:
;   LOW / HIGH on WORD struct field
;   HIGH on WORD array element (SubscriptExpr path)
;   LOW / HIGH on dereferenced WORD pointer
;
; result @40000 — each passed check adds 1, expected = 11 = $0B

byte result @40000 = 0
long lval   @40002 = $12345678   ; bytes $9C42-$9C45: $78 $56 $34 $12

struct Pair
    word wx
    word wy
end

Pair  sp               ; BSS — struct-typed variable
word  warr[2]          ; BSS — word array
word  wvar             ; BSS — word variable
word ^wptr             ; BSS — pointer to word

proc main()
    word tw       ; declared before statements (ZAP rule)

    ; set up test data
    sp.wx   = $AABB
    warr[0] = $CCDD
    wvar    = $EEFF
    wptr    = @wvar

    ; --- 1: LOW(LONG) = byte 0 ---
    if LOW(lval) == $78
        result = result + 1
    end

    ; --- 2: HIGH(LONG) = byte 1 ---
    if HIGH(lval) == $56
        result = result + 1
    end

    ; --- 3: LOWW(LONG) = bytes 0-1 as WORD ---
    if LOWW(lval) == $5678
        result = result + 1
    end

    ; --- 4: HIGHW(LONG) = bytes 2-3 as WORD ---
    if HIGHW(lval) == $1234
        result = result + 1
    end

    ; --- 5: LOW(HIGHW(LONG)) = byte 2 ---
    if LOW(HIGHW(lval)) == $34
        result = result + 1
    end

    ; --- 6: HIGH(HIGHW(LONG)) = byte 3 (chain: HIGHW then HIGH) ---
    if HIGH(HIGHW(lval)) == $12
        result = result + 1
    end

    ; --- 7: chain via variable: HIGHW → word var → HIGH ---
    tw = HIGHW(lval)
    if HIGH(tw) == $12
        result = result + 1
    end

    ; --- 8: LOW on WORD struct field ---
    if LOW(sp.wx) == $BB
        result = result + 1
    end

    ; --- 9: HIGH on WORD struct field ---
    if HIGH(sp.wx) == $AA
        result = result + 1
    end

    ; --- 10: HIGH on WORD array element (SubscriptExpr path) ---
    if HIGH(warr[0]) == $CC
        result = result + 1
    end

    ; --- 11: LOW on dereferenced WORD pointer ---
    if LOW(wptr^) == $FF
        result = result + 1
    end
end

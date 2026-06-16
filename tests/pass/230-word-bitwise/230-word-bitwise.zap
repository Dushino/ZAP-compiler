; Regression test: WORD bitwise operations (word & word, | word, ^ word, ~word).
; Previously only byte-widened-to-word was tested; pure WORD & WORD was untested.
;
; Checks:
;   1: $FF0F & $0FF0 == $0F00
;   2: $FF0F | $0FF0 == $FFFF
;   3: $FF0F ^ $0FF0 == $F0FF
;   4: ~$FF0F == $00F0  (bitwise NOT of WORD)
;   5: ~0 == $FFFF
;
; result @$0200 — expected = 5

byte result @$0200 = 0

proc main()
    word a = $FF0F
    word b = $0FF0
    word c

    ; 1: AND
    c = a & b
    if c == $0F00
        result = result + 1
    end

    ; 2: OR
    c = a | b
    if c == $FFFF
        result = result + 1
    end

    ; 3: XOR
    c = a ^ b
    if c == $F0FF
        result = result + 1
    end

    ; 4: NOT
    c = ~a
    if c == $00F0
        result = result + 1
    end

    ; 5: NOT of zero
    c = ~0
    if c == $FFFF
        result = result + 1
    end
end

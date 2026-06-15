; Regression test: LONG target widens byte bitwise ops to 32-bit.
; Upper 3 bytes of result must be zero (zero-extended from byte operands).
;
; Each passed check increments result; expected = 6.

byte result @$0200 = 0

proc main()
    byte aa
    byte bb
    long ll

    ; 1: AND: $FF & $AA = $AA, upper bytes zero
    aa = $FF
    bb = $AA
    ll = aa & bb
    if ll == $AA
        result = result + 1
    end
    if HIGHW(ll) == 0
        result = result + 1
    end

    ; 2: OR: $55 | $AA = $FF, upper bytes zero
    aa = $55
    bb = $AA
    ll = aa | bb
    if ll == $FF
        result = result + 1
    end
    if HIGHW(ll) == 0
        result = result + 1
    end

    ; 3: XOR: $FF ^ $55 = $AA, upper bytes zero
    aa = $FF
    bb = $55
    ll = aa ^ bb
    if ll == $AA
        result = result + 1
    end
    if HIGHW(ll) == 0
        result = result + 1
    end
end

; Test: C-style per-declarator pointer declarations
;   byte ^ptr1, ^ptr2  -- both pointers (C-style)
;   byte ^ptr3, plain  -- ptr3 pointer, plain is a byte (mixed)
;   word ^wp1, ^wp2    -- both word pointers
;   ^byte legacy       -- legacy prefix form for single declarator

word result @$0200 = 0

byte bval1 = 11
byte bval2 = 22
word wval1 = $1234
word wval2 = $5678

proc check(byte cond)
    if cond != 0
        result += 1
    end
end

proc main()
    byte ^ptr1, ^ptr2        ; both byte pointers
    byte ^ptr3, plain        ; ptr3 = pointer, plain = plain byte
    byte ^pa, ^pb, ^pc       ; three byte pointers on one line
    word ^wp1, ^wp2          ; both word pointers
    ^byte legacy             ; legacy prefix form

    ; byte ^ptr1, ^ptr2: independent pointers
    ptr1 = @bval1
    ptr2 = @bval2
    check(ptr1^ == 11)    ; 1
    check(ptr2^ == 22)    ; 2

    ; word ^wp1, ^wp2
    wp1 = @wval1
    wp2 = @wval2
    check(wp1^ == $1234)  ; 3
    check(wp2^ == $5678)  ; 4

    ; mixed: ptr3 pointer, plain plain byte
    ptr3 = @bval1
    plain = 99
    check(ptr3^ == 11)    ; 5
    check(plain == 99)    ; 6

    ; three pointers
    pa = @bval1
    pb = @bval2
    pc = @bval1
    check(pa^ == 11)      ; 7
    check(pb^ == 22)      ; 8
    check(pc^ == 11)      ; 9

    ; legacy prefix form
    legacy = @bval2
    check(legacy^ == 22)  ; 10
end

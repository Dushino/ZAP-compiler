; Test suite for compound assignment operators (syntax sugar)
;   lhs op= rhs  desugars to  lhs = lhs op rhs  at parse time.
;
; Operators tested: +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=
; Types tested: byte, word, long, array subscript, pointer
;
; Each successful check increments `result`. Expected final value: 20 ($14).

byte result @40000 = 0

proc main()
    ; All declarations first

    ; BYTE scalar tests
    byte b = 10

    ; WORD scalar tests
    word w = 1000

    ; LONG scalar tests
    long l = 65536          ; $00010000

    ; Array subscript test
    byte arr[4] = {1, 2, 3, 4}

    ; Pointer test
    byte ^ptr

    ; -----------------------------------------------------------------------
    ; 1. BYTE += : 10 + 5 = 15
    b += 5
    if b == 15
        result = result + 1     ; 1
    end

    ; 2. BYTE -= : 15 - 3 = 12
    b -= 3
    if b == 12
        result = result + 1     ; 2
    end

    ; 3. BYTE *= : 12 * 2 = 24
    b *= 2
    if b == 24
        result = result + 1     ; 3
    end

    ; 4. BYTE /= : 24 / 4 = 6
    b /= 4
    if b == 6
        result = result + 1     ; 4
    end

    ; 5. BYTE %= : 6 % 4 = 2
    b %= 4
    if b == 2
        result = result + 1     ; 5
    end

    ; 6. BYTE &= : 2 & $0F = 2
    b &= $0F
    if b == 2
        result = result + 1     ; 6
    end

    ; 7. BYTE |= : 2 | $10 = $12 = 18
    b |= $10
    if b == 18
        result = result + 1     ; 7
    end

    ; 8. BYTE ^= : 18 ^ 18 = 0, then 0 ^ 7 = 7
    b ^= 18
    b ^= 7
    if b == 7
        result = result + 1     ; 8
    end

    ; 9. BYTE <<= : 7 << 1 = 14
    b <<= 1
    if b == 14
        result = result + 1     ; 9
    end

    ; 10. BYTE >>= : 14 >> 1 = 7
    b >>= 1
    if b == 7
        result = result + 1     ; 10
    end

    ; -----------------------------------------------------------------------
    ; 11. WORD += : 1000 + 256 = 1256
    w += 256
    if w == 1256
        result = result + 1     ; 11
    end

    ; 12. WORD -= : 1256 - 256 = 1000
    w -= 256
    if w == 1000
        result = result + 1     ; 12
    end

    ; 13. WORD <<= : 1000 << 1 = 2000
    w <<= 1
    if w == 2000
        result = result + 1     ; 13
    end

    ; 14. WORD >>= : 2000 >> 1 = 1000
    w >>= 1
    if w == 1000
        result = result + 1     ; 14
    end

    ; -----------------------------------------------------------------------
    ; 15. LONG += : 65536 + 1 = 65537
    l += 1
    if l == 65537
        result = result + 1     ; 15
    end

    ; 16. LONG -= : 65537 - 1 = 65536
    l -= 1
    if l == 65536
        result = result + 1     ; 16
    end

    ; 17. LONG <<= : 65536 << 1 = 131072
    l <<= 1
    if l == 131072
        result = result + 1     ; 17
    end

    ; 18. LONG >>= : 131072 >> 1 = 65536
    l >>= 1
    if l == 65536
        result = result + 1     ; 18
    end

    ; -----------------------------------------------------------------------
    ; 19. Array subscript lvalue: arr[1] += 10  (2 + 10 = 12)
    arr[1] += 10
    if arr[1] == 12
        result = result + 1     ; 19
    end

    ; -----------------------------------------------------------------------
    ; 20. Pointer lvalue: ptr = @arr, ptr += 2, then read arr[2] via ptr^
    ptr = @arr
    ptr += 2                    ; advance by 2 byte elements -> points to arr[2]
    if ptr^ == 3                ; arr[2] was initialised to 3
        result = result + 1     ; 20
    end

end

; GAP-19: LONG bitwise operators and all LONG comparison operators
;
; Bitwise (4 checks):
;   1: LONG & (AND)         $12345678 & $0F0F0F0F = $02040608
;   2: LONG | (OR)          $12345678 | $0F0F0F0F = $1F3F5F7F
;   3: LONG ^ (XOR)         $12345678 ^ $0F0F0F0F = $1D3B5977
;   4: LONG ~ (NOT)         ~$12345678 = $EDCBA987
;
; Modulo (1 check):
;   5: LONG % (MOD)         100000 % 30000 = 10000
;
; Comparison operators — two distinct LONG variables (6 checks):
;   6: a == b  (true)       65536 == 65536
;   7: a != b  (true)       65536 != 65537
;   8: a <  b  (true)       65536 < 65537
;   9: a <= b  (true)       65536 <= 65536
;  10: a >  b  (true)       65537 > 65536
;  11: a >= b  (true)       65536 >= 65536
;
; result @40000 — each passed check adds 1, expected = 11 = $0B

byte result @40000 = 0

proc main()
    long x
    long y
    long z

    ; --- 1: LONG & ---
    x = $12345678
    y = $0F0F0F0F
    z = x & y          ; $02040608
    if z == $02040608
        result = result + 1
    end

    ; --- 2: LONG | ---
    x = $12345678
    y = $0F0F0F0F
    z = x | y          ; $1F3F5F7F
    if z == $1F3F5F7F
        result = result + 1
    end

    ; --- 3: LONG ^ ---
    x = $12345678
    y = $0F0F0F0F
    z = x ^ y          ; $1D3B5977
    if z == $1D3B5977
        result = result + 1
    end

    ; --- 4: LONG ~ ---
    x = $12345678
    z = ~x             ; $EDCBA987
    if z == $EDCBA987
        result = result + 1
    end

    ; --- 5: LONG % ---
    x = 100000
    y = 30000
    z = x % y          ; 10000
    if z == 10000
        result = result + 1
    end

    ; --- 6: LONG == (equal) ---
    x = 65536
    y = 65536
    if x == y
        result = result + 1
    end

    ; --- 7: LONG != (not equal) ---
    x = 65536
    y = 65537
    if x != y
        result = result + 1
    end

    ; --- 8: LONG < ---
    x = 65536
    y = 65537
    if x < y
        result = result + 1
    end

    ; --- 9: LONG <= (equal case) ---
    x = 65536
    y = 65536
    if x <= y
        result = result + 1
    end

    ; --- 10: LONG > ---
    x = 65537
    y = 65536
    if x > y
        result = result + 1
    end

    ; --- 11: LONG >= (equal case) ---
    x = 65536
    y = 65536
    if x >= y
        result = result + 1
    end
end

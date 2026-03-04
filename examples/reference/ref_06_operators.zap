; Example: ref_06_operators.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Operators" (lines 622-989)
;
; Demonstrates: arithmetic, comparison, logical, bitwise, unary, compound assign

; --- Arithmetic ---
proc arithmetic_example()
    byte a = 10
    byte b = 3
    byte sum = a + b        ; 13
    byte diff = a - b       ; 7
    byte prod = a * b       ; 30
    byte quot = a / b       ; 3
    byte rem = a % b        ; 1
end

; --- Comparison ---
proc comparison_example()
    byte x = 42

    if x == 42
        ; x equals 42
    end

    if x > 40 && x < 50
        ; x is between 40 and 50
    end
end

; --- Logical Operators ---
proc logical_example()
    byte x = 5
    byte y = 10

    ; AND operator
    if x > 0 && y > 0
        ; Both conditions true
    end

    ; OR operator
    if x == 5 || y == 5
        ; At least one condition true
    end

    ; NOT operator
    if !(x == 0)
        ; x is not zero
    end
end

; --- Unary ---
byte ux = 5
byte flag = 1
byte notflag = !flag  ; Logical negation

; --- Bitwise Operators ---
proc bitwise_example()
    byte mask = $0F
    byte value = $FF
    byte and_result = value & mask     ; $0F
    byte or_result = value | mask      ; $FF
    byte xor_result = value ^ mask     ; $F0
    byte not_result = ~value           ; $00
    long flags = $FFFF0000
    long masked = flags & $00FF0000
    long shifted = flags >> 8

    ; Check if bit is set
    if value & $80
        ; High bit is set
    end
    if flags & $01000000
        ; Bit 24 is set
    end
end

; --- Address-Of Operator ---
byte addr_data = 42
word addr = @addr_data

struct AddrPoint
    byte x
    byte y
end

byte addr_arr[] = { 1, 2, 3 }
AddrPoint addr_p = { 10, 20 }
word elem_addr = @addr_arr[1]
word x_addr = @addr_p.x

; --- Operator Precedence ---
proc precedence_example()
    byte result = 0

    ; Standard precedence
    result = 2 + 3 * 4      ; 14
    result = (2 + 3) * 4    ; 20

    ; Bitwise precedence
    result = 5 & 3 | 1      ; 1
end

; --- Compound Assignment ---
proc compound_assign_example()
    byte b = 10
    word w = 1000
    long l = 65536
    byte arr[4] = {1, 2, 3, 4}
    byte ^ptr = @arr

    b += 5          ; b = 15
    b *= 2          ; b = 30
    b >>= 1         ; b = 15

    w += 256        ; w = 1256
    w &= $00FF      ; w = 232

    l <<= 1         ; l = 131072
    l -= 1          ; l = 131071

    arr[1] += 10    ; arr[1] = 12

    ptr = @arr
    ptr += 2        ; advance pointer by 2 elements
end

proc main()
    arithmetic_example()
    comparison_example()
    logical_example()
    bitwise_example()
    precedence_example()
    compound_assign_example()
end

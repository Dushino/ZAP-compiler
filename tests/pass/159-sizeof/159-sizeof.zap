; GAP-15: SIZEOF() correctness across all argument forms
; Tests:
;  1. SIZEOF(TypeName)            — struct type name directly
;  2. SIZEOF(TypeName)            — second struct type (Large, 5 bytes)
;  3. SIZEOF(structVar)           — struct-typed variable (size = struct type size)
;  4. SIZEOF(ptrToStruct)         — pointer-to-struct var: returns pointed-to struct size
;                                    (unambiguous: Large is 5 bytes, pointer is always 2)
;  5. SIZEOF(TypeWithLong)        — struct whose fields include a LONG (4-byte) member
;
; result @40000 — each passed check adds 1, expected = 5

byte result @40000 = 0

struct Small
    byte x
    byte y
end   ; 2 bytes

struct Large
    byte a
    byte b
    word c
    byte d
end   ; 1+1+2+1 = 5 bytes

struct WithLong
    byte  a     ; 1 byte  at offset 0
    long  b     ; 4 bytes at offset 1
    byte  c     ; 1 byte  at offset 5
end   ; 6 bytes total

Small  sv    ; struct-typed global variable (2 bytes in BSS)
Large ^lptr  ; pointer-to-Large global variable (2 bytes in BSS)

proc main()
    ; --- check 1: SIZEOF by type name (Small = 2) ---
    if SIZEOF(Small) == 2
        result = result + 1
    end

    ; --- check 2: SIZEOF by type name (Large = 5) ---
    if SIZEOF(Large) == 5
        result = result + 1
    end

    ; --- check 3: SIZEOF on struct-typed variable (same as type size) ---
    if SIZEOF(sv) == 2
        result = result + 1
    end

    ; --- check 4: SIZEOF on pointer-to-struct: returns struct size (5), not pointer size (2) ---
    if SIZEOF(lptr) == 5
        result = result + 1
    end

    ; --- check 5: SIZEOF on struct with LONG field: 1 + 4 + 1 = 6 ---
    if SIZEOF(WithLong) == 6
        result = result + 1
    end
end

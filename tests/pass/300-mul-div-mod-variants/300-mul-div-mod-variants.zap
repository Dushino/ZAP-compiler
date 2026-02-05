word r0 @40000 = 0
word r1 @40002 = 0
word r2 @40004 = 0
word r3 @40006 = 0
word r4 @40008 = 0
word r5 @40010 = 0
word r6 @40012 = 0
word r7 @40014 = 0
word r8 @40016 = 0

proc main()
    ; Local declarations (must be before statements)
    byte m8a = 12
    byte m8b = 13
    byte m8_2 = 200
    word m16_1 = 51
    word m16a = 300
    word m16b = 200

    byte d8a = 100
    byte d8b = 3
    byte d8_2 = 200
    word d16_1 = 50
    word d16a = 60000
    word d16b = 300

    ; MUL variants
    r0 = m8a * m8b         ; 8x8 -> 12*13 = 156 (0x009C)
    r1 = m8_2 * m16_1      ; 8x16 -> 200*51 = 10200 (0x27D8)
    r2 = m16a * m16b       ; 16x16 -> 300*200 = 60000 (0xEA60)

    ; DIV variants (quotients)
    r3 = d8a / d8b         ; 8x8 -> 100/3 = 33 (0x0021)
    r4 = d8_2 / d16_1      ; 8x16 -> 200/50 = 4 (0x0004)
    r5 = d16a / d16b       ; 16x16 -> 60000/300 = 200 (0x00C8)

    ; MOD variants (remainders)
    r6 = d8a % d8b         ; 8x8 -> 100 % 3 = 1 (0x0001)
    r7 = d8_2 % d16_1      ; 8x16 -> 200 % 50 = 0 (0x0000)
    r8 = d16a % d16b       ; 16x16 -> 60000 % 300 = 0 (0x0000)
end

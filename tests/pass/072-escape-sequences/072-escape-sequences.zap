; Test 072: Hex, Octal, and Binary escape sequences
; Tests \xHH, \OOO, and \bBBBBBBBB in char and string literals

byte r1 @40000 = 0
byte r2 @40001 = 0
byte r3 @40002 = 0
byte r4 @40003 = 0
byte r5 @40004 = 0
byte r6 @40005 = 0
byte r7 @40006 = 0
byte r8 @40007 = 0

proc main()
    ; Hex escapes - full and short
    byte hex_ff = '\xFF'
    byte hex_f = '\xF'
    byte hex_a = '\x41'

    ; Octal escapes - 3, 2, 1 digit
    byte oct_max = '\377'
    byte oct_a = '\101'
    byte oct_7 = '\7'

    ; Binary escapes - full and short
    byte bin_ff = '\b11111111'
    byte bin_f = '\b1111'
    byte bin_a = '\b01000001'

    ; String with mixed escapes
    byte mixed[4] = "\x41\101\b01000001"

    r1 = hex_ff      ; expect 255 = 0xFF
    r2 = hex_f       ; expect 15  = 0x0F
    r3 = oct_max     ; expect 255 = 0xFF
    r4 = oct_a       ; expect 65  = 0x41
    r5 = oct_7       ; expect 7   = 0x07
    r6 = bin_ff      ; expect 255 = 0xFF
    r7 = bin_f       ; expect 15  = 0x0F
    r8 = mixed[0]    ; expect 65  = 0x41 (all three are 'A')
end

; Regression test: word target widens a chain of byte operations.
; Covers: byte*const (shift-add), byte+byte (ADD16), byte*const (power-of-2).
; Also tests const-add inline path with byte left operand.
;
; test1: w = 40*y + x  (y=7, x=3) = 283 = $011B  [shift-add chain - already covered by 213]
; test2: w = a + 5     (a=250)     = 255 = $00FF  [byte+const inline add]
; test3: w = a + 300   (a=100)     = 400 = $0190  [byte+word-const inline add]
; test4: w = a * 4     (a=200)     = 800 = $0320  [byte*power-of-2 widening]

byte r1_lo @$0200
byte r1_hi @$0201
byte r2_lo @$0202
byte r2_hi @$0203
byte r3_lo @$0204
byte r3_hi @$0205
byte r4_lo @$0206
byte r4_hi @$0207

proc main()
    byte x
    byte y
    byte a
    word w

    ; test1: shift-add chain
    x = 3
    y = 7
    w = 40*y + x
    r1_lo = low(w)
    r1_hi = high(w)

    ; test2: byte + small const (inline add, _iac_hi=0)
    a = 250
    w = a + 5
    r2_lo = low(w)
    r2_hi = high(w)

    ; test3: byte + word const (inline add, _iac_hi!=0)
    a = 100
    w = a + 300
    r3_lo = low(w)
    r3_hi = high(w)

    ; test4: byte * power-of-2 (shift)
    a = 200
    w = a * 4
    r4_lo = low(w)
    r4_hi = high(w)
end

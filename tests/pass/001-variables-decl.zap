; variables declaration tests
; test_variables_decl.zap

byte A1
byte A2 = 1
byte A3 @40000 = %01001000
const byte A4 = 3
const byte a5 = 'a'

byte ^ptr11
byte ^ptr12 @12
byte ^ptr13 @14 = %101

word B1
word B2 = 1
word B3 @40001 = $1234
word B4 = 4

word ^ptr21
word ^ptr22 @16
word ^ptr23 @18 = 512

.define SOMEDEFINE

proc a4x(byte x1, word x2)
    byte a4
end


; main -----------------------------------------
proc main()
end


; functions

byte result01 @40000
byte result02 @40002
byte result03 @40004
byte result04 @40006
byte result05 @40008
byte result06 @40010
byte result07 @40012
byte result08 @40014

word result11 @40016
word result12 @40018
word result13 @40020
word result14 @40022
word result15 @40024
word result16 @40026
word result17 @40028
word result18 @40030


; byte - byte
func byte doublebb(byte x)
return x * 2

func byte quadbb(byte x)
return doublebb(doublebb(x))

; word - byte
func word doublewb(byte x)
return x * 2

func word quadwb(byte x)
return doublewb(doublewb(x))

; byte - word
func byte doublebw(word x)
return x * 2

func byte quadbw(word x)
return doublebw(doublebw(x))

; word - word
func word doubleww(word x)
return x * 2

func word quadww(word x)
return doubleww(doubleww(x))

; -------------------------------------
proc main()
    result01 = doublebb($ab)    ; $156 -> $56
    result02 = quadbb($ab)      ; $2ac -> $ac
    result03 = doublebw($1234)  ; $2468 -> $68
    result04 = quadbw($1234)    ; $48d0 -> $d0
    result05 = doublewb($1234)  ; $68
    result06 = quadwb($1234)    ; $d0
    result07 = doubleww($1234)  ; $68
    result08 = quadww($1234)    ; $d0

    result11 = doublebb($ab)    ; $156 -> $56
    result12 = quadbb($ab)      ; $2ac -> $ac
    result13 = doublebw($1234)  ; $2468 -> $68
    result14 = quadbw($1234)    ; $48d0 -> $d0
    result15 = doublewb($1234)  ; $68
    result16 = quadwb($1234)    ; $d0
    result17 = doubleww($1234)  ; $2468
    result18 = quadww($1234)    ; $48d0

end

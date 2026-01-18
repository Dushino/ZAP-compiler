; functions

byte result01 @40000
byte result02 @40002
byte result03 @40004
byte result04 @40006
byte result05 @40008
byte result06 @40010
byte result07 @40012
byte result08 @40014

byte result11 @40016
byte result12 @40018
byte result13 @40020
byte result14 @40022
byte result15 @40024
byte result16 @40026
byte result17 @40028
byte result18 @40030


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


end

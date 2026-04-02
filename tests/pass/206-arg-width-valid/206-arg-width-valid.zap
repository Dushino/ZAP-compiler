; Argument width validation — all valid combinations

byte gb = $42
word gw = $1234
long gl = $12345678
byte ^gp = $2000

; --- Procedures with various param types ---
proc take_byte(byte x)
end

proc take_word(word x)
end

proc take_long(long x)
end

proc take_ptr(byte ^p)
end

proc take_two(byte a, word b)
end

; --- Functions with various param types ---
func byte ret_byte(byte x)
    return x
end

func word ret_word(word x)
    return x
end

proc main()
    byte lb = $10
    word lw = $2000
    long ll = $AABBCCDD
    byte r
    word rw

    ; --- Same type: byte to byte ---
    take_byte(gb)
    take_byte(lb)

    ; --- Same type: word to word ---
    take_word(gw)
    take_word(lw)

    ; --- Same type: long to long ---
    take_long(gl)
    take_long(ll)

    ; --- Constants that fit in byte ---
    take_byte(0)
    take_byte(42)
    take_byte(255)
    take_byte($FF)

    ; --- Constants that fit in word ---
    take_word(0)
    take_word(255)
    take_word(256)
    take_word($FFFF)

    ; --- Narrowing with LOW/HIGH ---
    take_byte(LOW(gw))
    take_byte(HIGH(gw))
    take_byte(LOW(lw))
    take_byte(HIGH(lw))

    ; --- Narrowing with LOWW/HIGHW ---
    take_word(LOWW(gl))
    take_word(HIGHW(gl))
    take_word(LOWW(ll))
    take_word(HIGHW(ll))

    ; --- Deep narrowing: LONG to BYTE via LOWW/HIGHW + LOW/HIGH ---
    take_byte(LOW(LOWW(gl)))
    take_byte(HIGH(LOWW(gl)))
    take_byte(LOW(HIGHW(gl)))
    take_byte(HIGH(HIGHW(gl)))

    ; --- Pointer to pointer ---
    take_ptr(gp)

    ; --- Multiple params with valid types ---
    take_two(gb, gw)
    take_two($42, $1234)
    take_two(LOW(gw), gw)

    ; --- Byte to word (promotion is OK — narrower to wider) ---
    take_word(gb)
    take_word(lb)

    ; --- Byte to long (promotion is OK) ---
    take_long(gb)
    take_long(gw)

    ; --- Function calls in expressions ---
    r = ret_byte(gb)
    r = ret_byte($42)
    r = ret_byte(LOW(gw))

    rw = ret_word(gw)
    rw = ret_word($1234)
    rw = ret_word(LOWW(gl))

    ; --- Function call as statement (valid too) ---
    ret_byte(gb)
    ret_word(gw)
end

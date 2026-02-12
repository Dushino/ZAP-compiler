byte result @40000 = 0

proc main()
    byte a = $3C
    byte b = $0F
    byte c = 2
    byte d = 1

    byte r = (a & b) + (a ^ b) + (a << c) + (b >> d) + (a | b)
    result = r
end

; ( 3c & 0f ) + ( 3c ^ 0f ) + ( 3c << 2 ) + ( 0f >> 1 ) + ( 3c | 0f )
; ( 0c ) + ( 33 ) + ( f0 ) + ( 07 ) + ( 3f )

struct VIA_STRUCT #PORT
    byte ORB #RD
    byte ORA #WR
    byte DDRB
end

VIA_STRUCT VIA1 @40000

byte x

proc main()
    x = VIA1.ORB    ; read-only field: read allowed
    VIA1.ORA = $02  ; write-only field: write allowed
    VIA1.DDRB = VIA1.DDRB & %01001111
end

struct VIA_STRUCT #PORT
    byte ORB #RD
    byte ORA #WR
end

VIA_STRUCT VIA1 @40000

proc main()
    VIA1.ORB = $01  ; write to read-only field should error
end

struct VIA_STRUCT #PORT
    byte ORB #RD
    byte ORA #WR
end

VIA_STRUCT VIA1 @40000

proc main()
    x = VIA1.ORA  ; read from write-only field should error
end

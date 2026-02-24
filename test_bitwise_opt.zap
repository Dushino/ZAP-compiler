proc main()
    byte a = 5
    word b = 1000
    long c = 100000
    
    a = $80 | a
    b = b ^ $1234
    c = $FFFF0000 & c
end

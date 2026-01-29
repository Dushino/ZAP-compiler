byte result @40000 = 0

.define DEBUG

proc test1()
    .ifdef DEBUG
        result = result + $01
    .else
        result = result + $10
    .endif

    .ifndef DEBUG
        result = result + $10
    .else
        result = result + $01
    .endif
end

.undef DEBUG

proc test2()
    .ifdef DEBUG
        result = result + $10
    .else
        result = result + $01
    .endif

    .ifndef DEBUG
        result = result + $01
    .else
        result = result + $10
    .endif
end



proc main()
    test1()
    test2()
end

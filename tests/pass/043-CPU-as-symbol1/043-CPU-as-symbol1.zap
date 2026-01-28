; early return from procedures and functions

byte result @40000 = 0


proc helper() 

    .ifdef 6502
        result = result + 1
    .endif
    .ifdef 65c02
        result = result + 1
    .endif
end


proc main()
    helper()
end

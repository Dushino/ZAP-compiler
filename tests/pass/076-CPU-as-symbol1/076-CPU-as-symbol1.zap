; testing CPU target as a symbol
; result should be 1 for both CPU types, but manual trests must be done for each CPU

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

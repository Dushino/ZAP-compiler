byte result @40000 = 0

proc main()
    byte x = 10
    word y = 20
    word z = x + y
    result = z ; implicit truncation if required
end

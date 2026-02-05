byte result @40000 = 0

proc main()
    byte x = 100
    word y = 200
    word z = x + y
    result = z ; implicit truncation if required
end

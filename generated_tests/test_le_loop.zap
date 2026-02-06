; Simple test for <= loop
byte result @40000 = 0

proc main()
    byte i
    for i = 0 to 2
        result = result + 1
    end
end

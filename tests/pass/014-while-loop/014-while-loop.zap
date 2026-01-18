; while loop
byte counter

proc main()
    byte counter @40000 = 0
    byte x @40001 = 5

    while counter < 10
        counter = counter + 1
    end
    
    while x != 1
        x = x - 1
    end
end

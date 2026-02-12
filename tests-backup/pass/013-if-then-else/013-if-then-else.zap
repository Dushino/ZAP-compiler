; if - then - else result
byte result

proc main()
    byte x1     @40000 = 5
    byte result @40001 = 0

    if x1 == 5
        result = result + 1
    else
        result = result + 2
    end
    
    if x1 > 3
        if x1 < 10
            result = result + 16
        end
    end
end

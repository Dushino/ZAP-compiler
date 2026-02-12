; early return from procedures and functions

byte result @40000 = 0


proc helper2(byte a)
    if a > 10
        return
    end
    
    if a > 5
        return
    end
end

func byte helper1(byte par1) 
    if par1 > 10
        return 1
    end
    
    if par1 > 5
        return 2
    end
    
    return 3
end


proc main()
    helper2(15)
    helper2(7)
    helper2(3)

    result = helper1(15) + helper1(7) + helper1(3)  ; 6
end

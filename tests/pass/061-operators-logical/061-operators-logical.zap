byte result @40000 = 0

proc main()
    byte r = 0

    if (!0) && (0 || 1) 
        r = 1
    else
        r = 0
    end

    result = r
end

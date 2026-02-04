proc main()
    byte x = 0
    
    while x < 100
        x = x + 1
        if x == 50
            break      ; Break outside of loop context (error)
        end
    end
end

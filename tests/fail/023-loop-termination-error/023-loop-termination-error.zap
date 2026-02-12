proc main()
    byte x = 0
    while x < 5
        x = x + 1
        if x == 3
            break
        end
    end
    break   ; Break outside of loop context (error)
end

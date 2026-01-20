byte result @40000 = 0

proc main()
    byte data = 5
    byte ^p

    p = @data
    p^ = 12
    result = data
end

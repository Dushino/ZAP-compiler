proc greet(byte x)
end

func byte test()
    greet(undeclared_var)
    return 0
end

proc main()
    byte r
    r = test()
end

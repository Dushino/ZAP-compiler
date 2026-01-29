word result @40000 = 0

proc main()
    byte data = 77
    byte ^ptr = @data
    byte value

    value = ptr^
    result = value
end

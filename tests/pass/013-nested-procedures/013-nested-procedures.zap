byte result @40000 = 0

proc increment_all(byte count)
    byte i
    i = 0
    while i < count
        result = result + 1
        i = i + 1
    end
end

proc main()
    increment_all(15)
end

byte result @40000 = 0
const byte msg[] = "Hello"

func byte strlen_simple(byte ^ptr)
    byte count = 0
    while ptr^ != 0
        count += 1
        ptr += 1
    end
    return count
end

proc main()
    word a = 100
    word b = 7
    result = a / b + strlen_simple(msg)
end

struct Small
    byte x
    byte y
end

struct Big
    byte a
    byte b
    byte c
end

byte result @40000

proc main()
    Small s
    Big b
    if s == b
        result = 1
    end
end

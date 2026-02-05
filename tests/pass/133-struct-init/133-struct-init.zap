byte result @40000 = 0

struct S
    byte a
    byte b
end

proc main()
    S s = {1,2}
    result = s.a + s.b ; expect 3
end

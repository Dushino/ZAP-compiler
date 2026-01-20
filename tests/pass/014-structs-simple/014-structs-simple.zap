struct Person
    byte age
end

byte result @40000 = 0

proc main()
    Person p
    p.age = 42
    result = p.age
end

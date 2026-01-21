struct Inner
    byte a
    byte b
end

struct Outer
    byte x
    Inner inner
end

proc main()
    Outer o = { 1, { 2, 3 } }
end

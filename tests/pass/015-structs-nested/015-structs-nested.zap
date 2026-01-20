struct Inner
    byte v
end

struct Outer
    Inner inner
    byte extra
end

byte result @40000 = 0

proc main()
    Outer o
    o.inner.v = 9
    o.extra = 2
    result = o.inner.v + o.extra
end

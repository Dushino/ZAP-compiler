struct Inner
    byte a
    byte b
end

struct Outer
    byte x
    Inner inner
end

proc main()
    Outer arr[2] = { { 1, { 2, 3 } }, { 4, { 5 } } }
end

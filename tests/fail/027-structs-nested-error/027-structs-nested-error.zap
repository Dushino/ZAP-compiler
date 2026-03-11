struct Inner
  byte a
end
struct Outer
  Inner i
end
proc main()
  Outer o
  byte x = o.i.b
end

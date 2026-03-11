struct Point
  byte x
  byte y
end
func byte bad()
  Point p
  return p
end
proc main()
  byte r = bad()
end

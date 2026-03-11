struct Point
  byte x
  byte y
end

proc main()
  Point p
  byte ^bp = @p
  bp^.x = 10
end

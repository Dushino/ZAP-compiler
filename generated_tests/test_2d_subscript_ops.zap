; Test 2D array subscripting with assignment and reads

byte grid[2][3] = {
  {0, 0, 0},
  {0, 0, 0}
}

proc main()
  byte i
  byte j
  
  i = 0
  while i < 2
    j = 0
    while j < 3
      grid[i][j] = i + j
      j = j + 1
    end
    i = i + 1
  end
end

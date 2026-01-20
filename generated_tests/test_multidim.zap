PROC main
  BYTE arr2d[2][3]
  BYTE i = 0
  BYTE j = 0
  
  WHILE i < 2
    j = 0
    WHILE j < 3
      arr2d[i][j] = i + j
      j = j + 1
    END
    i = i + 1
  END
END

PROC test_ptr_add()
  byte arr[8]
  byte^ dst = @arr
  byte m = 3
  dst += m
  dst^ = '+'
END

PROC main()
  test_ptr_add()
END

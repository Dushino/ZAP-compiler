enum Color
    RED
    GREEN
    BLUE
END

byte c = Color.GREEN
byte arr[Color.BLUE + 1] @40001

proc main()
    byte x @40000 = Color.BLUE
    arr[Color.RED] = 1
    arr[Color.GREEN] = 2
    arr[Color.BLUE] = 3
end

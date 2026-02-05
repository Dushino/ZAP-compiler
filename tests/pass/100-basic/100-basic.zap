enum Colors {
    RED,
    GREEN,
    BLUE
}

byte c = GREEN
byte arr[BLUE + 1] @40001

proc main()
    byte x @40000 = BLUE
    arr[RED] = 1
    arr[GREEN] = 2
    arr[BLUE] = 3
end

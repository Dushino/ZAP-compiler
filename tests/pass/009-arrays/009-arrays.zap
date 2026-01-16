; Test arrays and subscripting

byte arr1[] = {1,2,3,4,5,6} @40000
word arr3[] = {$1234, $5678, $9abc} @40008

proc main()
    arr1[1] = $11
    arr3[1] = $f1f2
end

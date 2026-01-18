


byte arr[] = {$10,$20,$30,$40,$50} @40000
byte ^ptr

word arr2[] = {$11f1,$22f2,$33f3,$44f4,$55f5} @40016
word ^ptr2

proc main()
    byte v1 = arr[2]
    word v2 = arr2[2]
    
    ptr = arr + 2
    ptr^ = $ff

    ptr2 = arr2 + 2
    ptr2^ = $ffa0

end

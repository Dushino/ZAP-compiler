; Test pointer assignment conversions

byte ^ptr1 @$5000
byte ^ptr2

word ^ptr3 @$5004
word ^ptr4

proc main()
    ptr1 = $5002
    ptr2 = ptr1
    ptr2^ = ptr2^ + 1

    ptr3 = $5006
    ptr4 = ptr3
    ptr4^ = ptr4^ + $f1f2
end

word arr[] = {$1111, $2222, $3333} @40000
word ^ptr

proc main()
    ptr = arr + 2
    ptr^ = $ffa0
end

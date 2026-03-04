; Writing through pointer derived from const address must be rejected
const byte carr[3] = {1, 2, 3}

proc main()
    byte ^ptr
    ptr = @carr
    (@carr + 1)^ = 99   ; error: Cannot write through pointer to const 'CARR'
end

; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "lib/stdio.zap"


proc getcmd()
    byte ch
    ch = getchar()
    while ch == 0
        ch = getchar()
    end
    return ch
end


proc main()

    byte ch

    cls()
    PLAYF2 = COLOR_GREEN3 + 4
    ch = getchar()
    while ch != 27
        switch ch
    
            default
                putx(ch)
                break
        end
        ch = getchar()
    end 

    PLAYF4 = COLOR_BLUE1  + 2
end

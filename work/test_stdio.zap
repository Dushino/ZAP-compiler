; test_stdio.zap
; working area for testing random parts of stdio.zap

.include "stdio.zap"


proc main()
    atari_autostart_data_area()
    atari_exehdr_data_area()

    cls()
end



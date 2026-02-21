; stdio.zap

.module "stdio"

.include "errno.zap"


proc CONSTRUCTOR()
    ; initialization code for stdio module, if needed
end

.ifdef ATARI
    .include "./atari/atari_stdio.zap"
.endif

.ifdef SBC
    .include "./sbc/sbc_stdio.zap"   
.endif


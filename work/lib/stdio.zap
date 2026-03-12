; ============================================================
; Module: stdio
; File:   lib/stdio.zap
; Platform: Multi-platform (conditional)
; Depends:  errno, types
;
; Description:
;   Platform I/O coordinator.  Selects the correct platform-specific
;   I/O implementation at compile time via preprocessor symbols:
;
;     -D ATARI  →  includes lib/atari/atari_stdio.zap
;     -D SBC    →  includes lib/sbc/sbc_stdio.zap  (not yet implemented)
;
;   All I/O functions (putchar, puts, getchar, fopen, …) are provided
;   by the included platform file and become part of this module's
;   exported namespace.
;
; Exports (own):
;   proc CONSTRUCTOR()  -- module init stub (empty; actual init in platform file)
;
; Status: Complete (platform selection); platform implementations vary
; ============================================================

.module "stdio"

.include "errno.zap"
.include "types.zap"


proc CONSTRUCTOR()
    ; initialization code for stdio module, if needed
end

.ifdef ATARI
    .include "./atari/atari_stdio.zap"
.endif

.ifdef SBC
    .include "./sbc/sbc_stdio.zap"   
.endif


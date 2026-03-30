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
;     -D ATARI  ->  includes lib/atari/atari_stdio.zap
;     -D SBC    ->  includes lib/sbc/sbc_stdio.zap  (not yet implemented)
;
;   All I/O functions (putchar, puts, getchar, fopen, …) are provided
;   by the included platform file and become part of this module's
;   exported namespace.
;
; Exports (own):
;   proc CONSTRUCTOR()  -- module init stub (empty; actual init in platform file)
;   proc poke(word addr, byte val)  -- write byte to memory address
;   func byte peek(word addr)       -- read byte from memory address
;
; Status: Complete (platform selection); platform implementations vary
; ============================================================

.module "stdio"

.include "errno.zap"
.include "types.zap"


proc CONSTRUCTOR()
    ; initialization code for stdio module, if needed
end


/*
    poke - write a byte value to a memory address
    Platform-independent equivalent of Action!'s POKE or BASIC's POKE.
    Uses indirect addressing through the ZP parameter slot for efficiency.
*/
proc poke(word addr, byte val)
    asm
        lda _POKE_VAL
        ldy #$00
        sta (_POKE_ADDR),y
    end
end


/*
    peek - read a byte value from a memory address
    Platform-independent equivalent of Action!'s PEEK or BASIC's PEEK.
    Uses indirect addressing through the ZP parameter slot for efficiency.
*/
func byte peek(word addr)
    byte result

    asm
        ldy #$00
        lda (_PEEK_ADDR),y
        sta _PEEK_RESULT
    end

    return result
end

.ifdef ATARI
    .include "./atari/atari_stdio.zap"
.endif

.ifdef SBC
    .include "./sbc/sbc_stdio.zap"   
.endif


; ============================================================
; Module: types
; File:   lib/types.zap
; Platform: All
; Depends:  errno
;
; Description:
;   Provides fundamental type definitions and file-I/O structures
;   used throughout the standard library.
;
; Exports:
;   enum BOOL           -- FALSE / TRUE
;   struct FILE         -- open file handle (fd, error, eof)
;   const word NULL     -- null pointer constant ($0000)
;   const byte FILE_HANDLE_MAX -- maximum simultaneous open handles (4)
;
; Status: Complete
; ============================================================

.module "types"

.include "errno.zap"


enum BOOL
    FALSE,
    TRUE
end


; FILE structure
struct FILE
    byte  fd        ; handle
    ERRNO error     ; error code
    BOOL eof        ; EOF reached
end


; NULL pointer constant
const word NULL = $0000


; maximum number of open file handles
const byte FILE_HANDLE_MAX = 4


; EOF
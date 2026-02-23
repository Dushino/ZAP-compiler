; types.zap

.module "types"

.include "errno.zap"


enum BOOL
    FALSE,
    TRUE
end


; FILE structure
struct FILE
    byte  fd     ; handle
    ERRNO error  ; error code
    BOOL  eof    ; end of file
end


; NULL file handle
const word NULL = 0


; maximum number of open file handles
const byte FILE_HANDLE_MAX = 4


; constants for fopen modes
const byte FILE_MODE_READ = 1
const byte FILE_MODE_WRITE = 2
const byte FILE_MODE_APPEND = 4


; Constants for fseek
const byte SEEK_SET = 0
const byte SEEK_CUR = 1
const byte SEEK_END = 2 

; EOF
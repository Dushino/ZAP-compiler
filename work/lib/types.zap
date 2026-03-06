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


; NULL pointer constant
const word NULL = $0000


; maximum number of open file handles
const byte FILE_HANDLE_MAX = 4


; Constants for fseek
enum SEEK
    SEEK_SET = 0
    SEEK_CUR = 1
    SEEK_END = 2
end


; EOF
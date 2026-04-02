; ============================================================
; Module: errno
; File:   lib/errno.zap
; Platform: Atari 400/800/XL/XE
; Depends:  (none)
;
; Description:
;   Defines the ERRNO enum with Atari CIO status byte values.
;   OK = 0 is the API-level success code.
;   CIO raw status: bit 7 clear ($01-$7F) = success,
;   bit 7 set ($80-$FF) = error.  CIO() remaps all success
;   codes to OK (0).
;
; Exports:
;   enum ERRNO  -- Atari CIO error/status codes
;
; Status: Complete
; Reference: Atari OS Reference Manual, Appendix B
; ============================================================

.module "errno"


; Atari CIO status codes
enum ERRNO
    OK              = 0     ; No error (API level)
    SUCCESS         = 1     ; Operation complete (raw CIO)
    BRK_KEY         = 128   ; BREAK key abort
    IOCB_IN_USE     = 129   ; IOCB already in use (open)
    NONEXISTENT_DEV = 130   ; Non-existent device
    WRITE_ONLY      = 131   ; Opened for write only
    INVALID_CMD     = 132   ; Invalid command
    NOT_OPEN        = 133   ; Device or file not open
    INVALID_IOCB    = 134   ; Invalid IOCB number
    READ_ONLY       = 135   ; Opened for read only
    EOF             = 136   ; End of file
    TRUNCATED       = 137   ; Truncated record
    TIMEOUT         = 138   ; Device timeout
    NAK             = 139   ; Device NAK
    FRAMING_ERR     = 140   ; Serial bus input framing error
    CURSOR_RANGE    = 141   ; Cursor out of range
    OVERRUN         = 142   ; Serial bus data frame overrun error
    CHECKSUM        = 143   ; Serial bus data frame checksum error
    DEVICE_ERR      = 144   ; Device done error
    BAD_MODE        = 145   ; Bad screen mode
    NOT_SUPPORTED   = 146   ; Function not supported by handler
    NO_MEMORY       = 147   ; Insufficient memory for screen mode
    DRIVE_ERR       = 160   ; Disk drive # error
    TOO_MANY_FILES  = 161   ; Too many open disk files
    DISK_FULL       = 162   ; Disk full
    DISK_IO_ERR     = 163   ; Fatal disk I/O error
    FILE_MISMATCH   = 164   ; Internal file # mismatch
    BAD_FILENAME    = 165   ; File name error
    POINT_LENGTH    = 166   ; Point data length error
    FILE_LOCKED     = 167   ; File locked
    INVALID_DISK_CMD= 168   ; Command invalid for disk
    DIR_FULL        = 169   ; Directory full (64 files)
    FILE_NOT_FOUND  = 170   ; File not found
    POINT_INVALID   = 171   ; Point invalid
end


; EOF
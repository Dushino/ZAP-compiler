; errno.zap
; Error codes for ZAP
; Based on Linux kernel error codes https://man7.org/linux/man-pages/man3/errno.3.html

.module "errno"


; Error codes
enum ERRNO 
    OK,                   ; No error
    E2BIG,                ; Argument list too long
    EACCES,               ; Permission denied
    EAGAIN,               ; Resource temporarily unavailable
    EALREADY,             ; Connection already in progress
    EBADF,                ; Bad file descriptor
    EBADFD,               ; File descriptor in bad state
    EBADRQC,              ; Invalid request code
    EBUSY,                ; Device or resource busy
    ECANCELED,            ; Operation canceled
    ECHRNG,               ; Channel number out of range
    ECOMM,                ; Communication error on send
    ECONNABORTED,         ; Connection aborted
    ECONNREFUSED,         ; Connection refused
    ECONNRESET,           ; Connection reset
    EEXIST,               ; File exists
    EFBIG,                ; File too large
    EHOSTUNREACH,         ; Host is unreachable
    EHWPOISON,            ; Hardware error
    EILSEQ,               ; Invalid sequence
    EINPROGRESS,          ; Operation in progress
    EINTR,                ; Interrupted
    EINVAL,               ; Invalid argument
    EIO,                  ; I/O error
    EISCONN,              ; Connection already in progress
    EISDIR,               ; Is a directory
    EMFILE,               ; Too many files
    EMSGSIZE,             ; Message too long
    ENAMETOOLONG,         ; Filename too long
    ENETDOWN,             ; Network down
    ENETRESET,            ; Network reset
    ENETUNREACH,          ; Network unreachable
    ENOANO,               ; No anonymous node
    ENODATA,              ; No data
    ENODEV,               ; No device
    ENOENT,               ; No entry
    ENOEXEC,              ; No execute
    ENOLINK,              ; No link
    ENOMEDIUM,            ; No medium
    ENOMEM,               ; No memory
    ENOMSG,               ; No message
    ENONET,               ; No network
    ENOPROTOOPT,          ; No protocol option
    ENOSPC,               ; No space
    ENOSR,                ; No stream resources
    ENOSTR,               ; No stream
    ENOSYS,               ; No system
    ENOTBLK,              ; Not a block device
    ENOTCONN,             ; Not connected
    ENOTDIR,              ; Not a directory
    ENOTEMPTY,            ; Directory not empty
    ENOTRECOVERABLE,      ; Not recoverable
    ENOTSOCK,             ; Not a socket
    ENOTSUP,              ; Not supported
    ENOTUNIQ,             ; Not unique
    ENXIO,                ; No such device or address
    EOPNOTSUPP,           ; Operation not supported
    EPROTO,               ; Protocol error    
    EPROTONOSUPPORT,      ; Protocol not supported
    ERANGE,               ; Value too large
    EREMCHG,              ; Remote address changed
    EREMOTEIO,            ; Remote I/O error
    EROFS,                ; Read-only file system
    ESHUTDOWN,            ; Cannot send after socket shutdown
    ESPIPE,               ; Invalid seek
    ESOCKTNOSUPPORT,      ; Socket type not supported
    ESRCH,                ; No such process
    ESTALE,               ; File handle is stale
    ESTRPIPE,             ; Stream pipe error
    ETIME,                ; Timer expired
    ETIMEDOUT,            ; Connection timed out
    ETXTBSY,              ; Text file busy
    EUCLEAN,              ; File system needs cleaning
    EUNATCH,              ; Protocol driver not attached
    EWOULDBLOCK,          ; Operation would block
    EXDEV,                ; Cross-device link
    EXFULL                ; Exchange full
end

/*
Appendix B -- CIO STATUS BYTE VALUES
Shown below are the known CIO STATUS BYTE values.
01 (001) -- OPERATION COMPLETE (NO ERRORS)
80 (128) -- CBREAKI KEY ABORT
81 (129) -- IOCB ALREADY IN USE (OPEN)
82 (130) -- NON-EXISTENT DEVICE
83 (131) -- OPENED FOR WRITE ONLY
84 (1332) -- INVALID COMMAND
85 (133) -- DEVICE OR FILE NOT OPEN
86 (134} -- INVALID IOCB NUMBER (Y reg only}
87 (135) -- OPENED FOR READ ONLY
88 (136) -- END OF FILE
89 (137) -- TRUNCATED RECORD
BA (138) -- DEVICE TIMEOUT (DOESN'T RESPOND
BB (139) -- DEVICE NAK
8C (140) -- SERIAL BUS INPUT FRAMING ERROR
BD (141) -- CURSOR out-of-range
8E (142) -- SERIAL BUS DATA FRAME OVERRUN ERROR
8F (143) -- SERIAL BUS DATA FRAME CHECKSUM ERROR
90 (144) -- DEVICE DONE ERROR
91 (145) -- BAD SCREEN MODE
92 (146) -- FUNCTION NOT SUPPORTED BY HANDLER
93 (147) -- INSUFFICIENT MEMORY FOR SCREEN MODE
AO (160) -- DISK DRIVE # ERROR
A1 (161) -- TOO MANY OPEN DISK FILES
A2 (162) -- DISK FULL
AЗ (163) -- FATAL DISK I/0 ERROR
A4 (164) -- INTERNAL FILE # MISMATCH
A5 (165) -- FILE NAME ERROR
A6 (166) -- POINT DATA LENGTH ERROR
A7 (167) -- FILE LOCKED
A8 (168)-- COMMAND INVALID FOR DISK
A9 (169) -- DIRECTORY FULL (64 FILES)
AA (170) -- FILE NOT FOUND
AB (171) -- POINT INVALID
*/


; EOF
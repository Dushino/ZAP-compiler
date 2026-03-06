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

; EOF
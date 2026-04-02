; Example: ref_04_const_enum.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, sections "const" + "Enums" (lines 177-340)
;
; Demonstrates: const variables, const arrays, enums with byte/word
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Const ---
const byte CVERSION = 1
const word MAX_SIZE = 1024
const byte carr[] = { 1, 2, 3 }

; --- Basic Enum (default byte) ---
enum Colors
    RED
    GREEN
    BLUE
END

byte c_val = Colors.GREEN        ; c_val == 1
byte arr_e[Colors.BLUE + 1]      ; use enum value in an array size

; --- Explicit values and auto-increment ---
enum byte E
    A = 1
    B       ; B == 2
    C = 5
    D       ; D == 6
END

const byte v = E.D


; --- Word-sized enum ---
enum word Big
    BA = 300
    BB
    BC = 65535
END

const word w1 = Big.BA

proc main()
    byte r = Colors.RED     ; 0
    byte g = Colors.GREEN   ; 1
    byte b = Colors.BLUE    ; 2

    ; Qualified syntax
    byte qa = E.A    ; 1
    byte qd = E.D    ; 6

    word wb = Big.BB ; 301
end

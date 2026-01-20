
byte dividend1 @40000
byte divisor1  @40001
byte result11  @40002
byte result12  @40003

word dividend2 @40004
word divisor2  @40006
word result21  @40008
word result22  @40010
word result23  @40012
word result24  @40014

proc main()
    dividend1 = 23                      ; $17
    divisor1 = 5                        ; $05
    result11 = dividend1 / divisor1     ; Should be $04
    result12 = dividend1 % divisor1     ; Should be $03

    dividend2 = 23876                   ; $5D44 
    divisor2 = 515                      ; $0203
    result21 = dividend2 / divisor2     ; Should be 46 $2E
    result22 = dividend2 % divisor2     ; Should be 186 $ba

    divisor2 = 43                       ; $2B
    result23 = dividend2 / divisor2     ; Should be 555 $22B
    result24 = dividend2 % divisor2     ; Should be 11 $0b
end

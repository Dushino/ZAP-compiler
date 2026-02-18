; Fresh compilation test
long a @40000 = 0
long b = 0
long c @40004 = 0
word d @40008 = 0
byte e @40010 = 0

proc main()
  a = 123456
  b = 100
  c = a + b     ; 123556
  c = c - 56    ; 123500
  c = c * 2     ; 247000
  c = c / 10    ; 24700
  c = c << 2    ; 98800
  c = c >> 1    ; 49400

  e = c
  d = c
  e = d
  d = e  

  if c > 40000
     c = 1
  else
     c = 0
  end

  c = ~c        ; BNOT

  ; Bitwise checks
  c = c & 1     ; BAND
  c = c | 2     ; BOR
  c = c ^ 12345 ; BXOR

  ; Mixed type checks
  c = c & d     ; LONG & WORD
  c = d | c     ; WORD | LONG

  d = c
  e = c
  c = d
  c = e  
end

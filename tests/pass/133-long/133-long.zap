; Fresh compilation test
long a @40000 = 0
long b = 0
long c @40004 = 0

proc main()

  a = 123456
  b = 100
  c = a + b     ; 123556
  c = c - 56    ; 123500
  c = c * 2     ; 247000
  c = c / 10    ; 24700
  c = c << 2    ; 98800
  c = c >> 1    ; 49400 $C0F8

  if c > 40000
     c = c + 1 ; $C0F9
  else
     c = 0
  end
end

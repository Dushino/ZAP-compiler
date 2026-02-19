; BYTE datatype declarations and operations

byte a
byte b @40000 = 0
byte c = 0 
byte d[4] @40000+8 = {$01, $02, $03, $04}

const byte ca = $05
const byte cc[4] = {$11, $12, $13, $14}

byte ^pa
byte ^pb @40001
byte ^pc @40002 = $2345
byte ^pd[4] @40000+12 = {$1300, $1301, $1302, $1303}

proc main()
   
   ; const - should be computed during compilation
   a = 1
   a = 1 + 2 * 3
   a = ca
   a = ca + 5  ; const + const
   a = 4 + 5   ; const + const
   a = ca - 5  ; const - const
   a = 4 - 5   ; const - const
   a = ca * 5  ; const * const
   a = 4 * 5   ; const * const
   a = ca / 5  ; const / const
   a = 4 / 5   ; const / const
   a = ca % 5  ; const % const
   a = 4 % 5   ; const % const
   a = ca << 5 ; const << const
   a = 4 << 5  ; const << const
   a = ca >> 5 ; const >> const
   a = 4 >> 5  ; const >> const
   a = ca & 5  ; const & const
   a = 4 & 5   ; const & const
   a = ca | 5  ; const | const
   a = 4 | 5   ; const | const
   a = ca ^ 5  ; const ^ const
   a = 4 ^ 5   ; const ^ const
   a = ca && 5 ; const && const
   a = 4 && 5  ; const && const
   a = ca || 5 ; const || const
   a = 4 || 5  ; const || const
   c = a

   ; unary operators on const
   a = ~5
   a = ~ca
   a = 1 + 2 * 3
   a = ~(ca + 5)
   a = ~(ca - 5)
   a = ~(ca * 5)
   a = ~(ca / 5)
   a = ~(ca % 5)
   a = ~(ca << 5)
   a = ~(ca >> 5)
   a = ~(ca & 5)
   a = ~(ca | 5)
   a = ~(ca ^ 5)
   a = ~(ca && 5)
   a = ~(ca || 5)
   a = ~ca + 5
   a = ~ca - 5
   a = ~ca * 5
   a = ~ca / 5
   a = ~ca % 5
   a = ~ca << 5
   a = ~ca >> 5
   a = ~ca & 5
   a = ~ca | 5
   a = ~ca ^ 5
   a = ~ca && 5
   a = ~ca || 5   

   ; unary operators on variables
   a = ~a
   a = ~a + 1  ; INC
   a = ~a - 1  ; DEC
   a = a * 2   ; << 1
   a = a / 2   ; >> 2
   a = ~a + 5
   a = ~a - 5
   a = ~a * 5
   a = ~a / 5
   a = ~a % 5
   a = ~a << 5
   a = ~a >> 5
   a = ~a & 5
   a = ~a | 5
   a = ~a ^ 5
   a = ~a && 5
   a = ~a || 5 
   a = ~c
   a = ~d[2]
   a = ~pa
   a = ~pb
   a = ~pc
   a = ~pd[2]
   a = ~pd[2] + 5
   a = ~pd[2] - 5
   a = ~pd[2] * 5
   a = ~pd[2] / 5
   a = ~pd[2] % 5
   a = ~pd[2] << 5
   a = ~pd[2] >> 5
   a = ~pd[2] & 5
   a = ~pd[2] | 5
   a = ~pd[2] ^ 5
   a = ~pd[2] && 5
   a = ~pd[2] || 5   
   
   a = !0
   a = !1
   a = !ca
   a = !a
   a = !c
   a = !d[2]
   a = !pa
   a = !pb
   a = !pc
   a = !pd[2]
   a = !pd[2] + 5
   a = !pd[2] - 5
   a = !pd[2] * 5
   a = !pd[2] / 5
   a = !pd[2] % 5
   a = !pd[2] << 5
   a = !pd[2] >> 5
   a = !pd[2] & 5
   a = !pd[2] | 5
   a = !pd[2] ^ 5
   a = !pd[2] && 5
   a = !pd[2] || 5   
   
   ; binary operators
   a = 0
   a = a + 1   ; INC
   a = a - 1   ; DEC
   a = a * 2   ; << 1
   a = a / 2   ; >> 2
   a = b + 10
   a = b - 10
   a = b * 10
   a = b / 10
   a = b % 10
   a = a >> 2
   a = a << 2
   a = a & $0f
   a = a | $80
   a = a ^ $ff
   a = a && b
   a = a || b  


   ; math. expressions
   a = 1 + 2 * 3     ; expression to RPN
   a = a - 1         ; should use DEC
   a = a + 1         ; should use INC
   a = a * 2         ; should use ASL
   a = a / 2         ; should use LSR
   a = a + b         ; should use ADD
   a = a - b         ; should use SUB
   a = a * b         ; should use MUL
   a = a / b         ; should use DIV
   a = a % b         ; should use MOD


   c = 2
   d[0] = 6
   d[1] = 7
   d[2] = 8
   d[3] = 9

   /*
   ; pointer assignments
   pa = &a
   pb = &b
   pc = &c
   pd = &d

   ; pointer dereferencing
   a = *pa
   b = *pb
   c = *pc
   d[0] = *pd

   ; pointer arithmetic
   pa = pa + 1
   pb = pb - 1
   pc = pc + 2
   pd = pd - 2

   ; pointer array assignments
   pa[0] = 10
   pa[1] = 11
   pa[2] = 12
   pa[3] = 13

   ; pointer array dereferencing
   a = pa[0]
   b = pa[1]
   c = pa[2]
   d[0] = pa[3]

   ; pointer array arithmetic
   pa = pa + 1
   pb = pb - 1
   pc = pc + 2
   pd = pd - 2

   ; pointer array dereferencing
   a = pa[0]
   b = pa[1]
   c = pa[2]
   d[0] = pa[3]
   */
end

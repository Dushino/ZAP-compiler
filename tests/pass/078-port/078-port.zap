
struct VIA_STRUCT
    byte ORB
    byte ORA    
    byte DDRB
    byte DDRA
    byte T1CL
    byte T1CH   
    byte T1LL   
    byte T1LH   
    byte T2CL   
    byte T2CH   
    byte SR    
    byte ACR   
    byte PCR
    byte IFR    
    byte IER 
    byte PRA 
    byte PRB     
end

VIA_STRUCT VIA1 @40000 #port
VIA_STRUCT VIA2 @40016 #port

proc helper() 
    VIA1.ORB = $01
    VIA1.DDRB = $FF
    VIA2.ORB = $02
    VIA2.DDRB = $FF
end


proc main()
    helper()
end

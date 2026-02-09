
struct VIA_STRUCT #port
    byte ORB    #wr ; warning: not true for real VIA
    byte ORA    #rd ; warning: not true for real VIA
    byte DDRB
    byte DDRA
    byte T1CL
    byte T1CH   
    byte T1LL   
    byte T1LH   
    byte T2CL   
    byte T2CH   
    byte SR     #rd  ; warning: not true for real VIA
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
    VIA1.ORB = $01      ; #wr
    VIA1.DDRB = $FF     ; #rd #wr
    VIA2.ORB = $02      ; #wr
    VIA2.DDRB = $FF     ; #rd #wr
end


proc main()
    helper()
end

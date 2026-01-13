.import NMI_SERVICE
.import RESB_VECT
.import IRQ_SERVICE

.segment "VECTORS"
    .word NMI_SERVICE
    .word RESB_VECT
    .word IRQ_SERVICE

.segment "CODE"


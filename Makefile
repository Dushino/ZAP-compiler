# 65c02 experimental compiler

APPNAME=p1
LIBDIR=lib
SRC1DIR=src1
SRC2DIR=src2
OBJDIR=obj
BINDIR=out

USBDEVICE=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

# compiler and linekr options
ZC   = python3 compiler.py
CL   = cl65
CC   = cc65
AS   = ca65
LD   = ld65
DA   = da65

# main
APPDIR 		=  $(APPNAME)
APPSRC1DIR 	=  $(APPDIR)/$(SRC1DIR)
APPSRC1 	=  $(APPSRC1DIR)/$(APPNAME).zap
APPSRC2DIR 	=  $(APPDIR)/$(SRC2DIR)
APPSRC 		=  $(APPSRC2DIR)/$(APPNAME).s
APPOBJDIR 	=  $(APPDIR)/$(OBJDIR)
APPOBJ 		=  $(APPOBJDIR)/$(APPNAME).o
APPBINDIR 	=  $(APPDIR)/$(BINDIR)
APPBIN 		:= $(APPBINDIR)/$(APPNAME)
LIBDIR      =  lib

ATARI_CPU = 6502
ATARI_AS_OPTS = -I $(LIBDIR) -t none --cpu $(ATARI_CPU) -g

SBC_CPU   = w65c02
SBC_AS_OPTS  = -I $(LIBDIR) -t none --cpu $(SBC_CPU) -g


# Rules
.PHONY:	all clean sbc atari tests


all: atari 

upload: sbc
	@./upload.sh $(BINDIR)/$(APPNAME).s19 $(USBDEVICE)

run: atari
	atari800 -basic $(APPBIN).com

atari: compile_atari
	$(AS) $(ATARI_AS_OPTS) $(LIBDIR)/atari/exehdr.s -o $(APPOBJDIR)/exehdr.o
	$(LD) -C cfg/my_atari.cfg $(APPOBJ) $(APPOBJDIR)/exehdr.o  -o $(APPBIN).com	
	dd if=$(APPBIN).com of=$(APPBIN).cut bs=6 skip=1
	$(DA) --cpu $(ATARI_CPU) --multi-pass --start-addr $4006 --comments 3 --hexoffs --verbose --verbose  $(APPBIN).cut > $(APPBIN).da65


compile_atari: 
	@mkdir -p $(APPSRC2DIR) $(APPOBJDIR) $(APPBINDIR)	
	$(ZC) -6502 $(APPSRC1) -o $(APPSRC)		
#	$(ZC) -6502 --peepholes $(APPSRC1) -o $(APPSRC)	
	$(AS) $(ATARI_AS_OPTS) $(APPSRC) -o $(APPOBJ)


upload: sbc

sbc: compile_sbc
	$(AS) $(SBC_AS_OPTS) $(LIBDIR)/atari/exehdr.s -o $(APPOBJDIR)/exehdr.o
	$(LD) -C cfg/my_sbc.cfg $(APPOBJ) -o $(APPBIN).com	
	$(DA) --cpu $(SBC_CPU) --multi-pass --start-addr $4006 --comments 3 --hexoffs --verbose --verbose  $(APPBIN).cut > $(APPBIN).da65

compile_sbc: 
	@mkdir -p $(APPSRC2DIR) $(APPOBJDIR) $(APPBINDIR)	
#	$(ZC) $(APPSRC1) -o $(APPSRC)	
	$(ZC) --peepholes $(APPSRC1) -o $(APPSRC)	
	$(AS) $(SBC_AS_OPTS) $(APPSRC) -o $(APPOBJ)


tests:
	@echo "Compiling all tests with 4 variants each..."
	@mkdir -p tests
	@for zapfile in tests/*.zap; do \
		if [ -f "$$zapfile" ]; then \
			base=$$(basename $$zapfile .zap); \
			echo "Processing $$base.zap..."; \
			echo "  Variant 1: default (WDC65c02, no peepholes)"; \
			$(ZC) $$zapfile -o tests/$$base.s; \
			echo "  Variant 2: --peepholes (WDC65c02)"; \
		$(ZC) $$zapfile --peepholes -o tests/$$base--peepholes.s; \
		echo "  Variant 3: --6502 (no peepholes)"; \
		$(ZC) $$zapfile --6502 -o tests/$$base--6502.s; \
		echo "  Variant 4: --peepholes --6502"; \
		$(ZC) $$zapfile --peepholes --6502 -o tests/$$base--peepholes--6502.s; \
		fi; \
	done
	@echo "Assembling all .s files..."
	@for sfile in tests/*.s; do \
		if [ -f "$$sfile" ]; then \
			if echo "$$sfile" | grep -q -- "--6502"; then \
				echo "Assembling $$sfile with $(ATARI_CPU)..."; \
				$(AS) $(ATARI_AS_OPTS) $$sfile -o $${sfile%.s}.o 2>&1 | head -20; \
			else \
				echo "Assembling $$sfile with $(SBC_CPU)..."; \
				$(AS) $(SBC_AS_OPTS) $$sfile -o $${sfile%.s}.o 2>&1 | head -20; \
			fi; \
		fi; \
	done
	@echo "Tests compilation complete!"



# --------------------------------------------------------------------------
# Cleanup rules
clean:
	find $(APPOBJDIR)  -name *.o -type f -delete | true
	find $(APPBINDIR)  -name *.com -type f -delete | true
	find $(APPBINDIR)  -name *.cut -type f -delete | true
	find $(APPBINDIR)  -name *.da65 -type f -delete | true
	find $(APPSRC2DIR) -name *.s -type f -delete | true
	find $(APPSRC2DIR) -name *.inc -type f -delete | true
	find tests -name *.s -type f -delete 2>/dev/null | true
	find tests -name *.o -type f -delete 2>/dev/null | true


	
	



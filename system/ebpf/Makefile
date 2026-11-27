# Makefile eBPF de NexoraOS: requiere clang, bpftool y /sys/kernel/btf/vmlinux.
CLANG   ?= clang
BPFTOOL ?= bpftool
ARCH    ?= $(shell uname -m)
BPF_TARGET := bpf

VMLINUX := vmlinux.h

$(VMLINUX):
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $(VMLINUX)

%.bpf.o: %.bpf.c $(VMLINUX) include/nexora_events.h
	$(CLANG) -O2 -g -target $(BPF_TARGET) -D__TARGET_ARCH_$(ARCH) -Iinclude -I. -c $< -o $@

build: sentinel.bpf.o antivirus.bpf.o netwall.bpf.o

load: build
	$(BPFTOOL) prog load sentinel.bpf.o /sys/fs/bpf/nexora/sentinel
	$(BPFTOOL) prog load netwall.bpf.o  /sys/fs/bpf/nexora/netwall

unload:
	-$(BPFTOOL) prog unload /sys/fs/bpf/nexora/sentinel
	-$(BPFTOOL) prog unload /sys/fs/bpf/nexora/netwall

clean:
	rm -f *.bpf.o $(VMLINUX)

.PHONY: build load unload clean

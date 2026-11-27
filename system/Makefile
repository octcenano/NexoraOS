# Makefile de NexoraOS Tools.
PREFIX ?= /usr
LIBDIR ?= $(PREFIX)/lib/nexora
BINDIR ?= $(PREFIX)/bin
UNITDIR ?= $(PREFIX)/lib/systemd/system

install:
	install -d $(DESTDIR)$(LIBDIR) $(DESTDIR)$(BINDIR) $(DESTDIR)$(UNITDIR)
	cp -a sentinel core blueprint app-time cell netwall vault persona privacy \
	      perf doctor guardian lens bridge ramopt tor tuning ebpf $(DESTDIR)$(LIBDIR)/
	for d in sentinel/antivirus sentinel core blueprint app-time cell netwall \
	         vault persona privacy perf doctor guardian lens bridge ramopt tor tuning; do \
	  for f in $(DESTDIR)$(LIBDIR)/$$d/nexora-*; do \
	    [ -e "$$f" ] && ln -sf $$f $(DESTDIR)$(BINDIR)/$$(basename $$f); \
	  done; done
	find $(DESTDIR)$(LIBDIR) -maxdepth 2 -type f \( -name 'nexora-*' -o -name '*.sh' \) -exec chmod +x {} +
	install -m 644 */units/*.service */units/*.timer $(DESTDIR)$(UNITDIR)/ 2>/dev/null || true
	install -m 644 sentinel/units/*.service $(DESTDIR)$(UNITDIR)/

test:
	@echo "bateria de validacion: cada CLI con subcomando de estado"
	@bash -c 'set -e; ./sentinel/antivirus/nexora-antivirus status >/dev/null; \
	  ./core/nexora-core status >/dev/null; ./netwall/nexora-netwall show >/dev/null; \
	  ./ramopt/nexora-ramopt status >/dev/null; ./tor/nexora-tor status >/dev/null; \
	  ./tor/nexora-stealth status >/dev/null; echo "OK"'

antivirus-baseline:
	sudo ./sentinel/antivirus/nexora-antivirus baseline --update

ebpf:
	$(MAKE) -C ebpf build

kernel-patches:
	./kernel/fetch-patches.sh

clean:
	rm -f ebpf/*.bpf.o ebpf/vmlinux.h

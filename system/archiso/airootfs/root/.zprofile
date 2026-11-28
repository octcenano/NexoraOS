# NexoraOS: el instalador propio sustituye a archinstall.
echo ""
echo "  Bienvenido a NexoraOS (live)."
echo "  Instalacion del sistema:  nexora-installer   (instalador exclusivo; archinstall no esta presente)."
echo "  Herramientas: nexora-perf, nexora-ramopt, nexora-stealth, nexora-tor, nexora-privacy."
if [ -t 0 ]; then
  printf "  Iniciar el instalador ahora? [s/N] "
  read -r r
  [ "$r" = "s" ] && exec /usr/local/bin/nexora-installer
fi

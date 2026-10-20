#!/bin/sh
# Installiert Controme Connect in das Konfigurationsverzeichnis
# von Home Assistant und startet Home Assistant neu.
#
# Aufruf:  ./install.sh
#
# Das Verzeichnis lässt sich überschreiben:
#   HA_CONFIG=/pfad/zum/config ./install.sh

set -eu

ZIEL="${HA_CONFIG:-/config}"
QUELLE="$(cd "$(dirname "$0")" && pwd)/custom_components/controme_connect"

if [ ! -d "$ZIEL/custom_components" ]; then
    echo "Kein Konfigurationsverzeichnis gefunden: $ZIEL" >&2
    echo "Bitte HA_CONFIG auf den Pfad zum Config-Verzeichnis setzen." >&2
    exit 1
fi

echo "Installiere $QUELLE nach $ZIEL/custom_components/controme_connect"
rm -rf "$ZIEL/custom_components/controme_connect"
cp -r "$QUELLE" "$ZIEL/custom_components/controme_connect"
find "$ZIEL/custom_components/controme_connect" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "Fertig. Home Assistant bitte neu starten."

#!/bin/bash
# A runs this ONCE on the board after binding both real adapters. Daily use is physical.
set -eu
SOURCE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEST=/opt/shengdi
PYTHON=/usr/local/share/pynq-venv/bin/python
[ "$(id -u)" = 0 ] || { echo 'First installation requires sudo on the board'; exit 2; }
"$PYTHON" "$SOURCE/recal_product.py" --base "$SOURCE" --check
DIGEST="$(sha256sum "$SOURCE/product-manifest.json" | cut -c1-16)"
RELEASE="$DEST/releases/$DIGEST"
mkdir -p "$RELEASE"
"$PYTHON" - "$SOURCE" "$RELEASE" <<'PY'
from pathlib import Path
import json, shutil, sys
source, target = (Path(p).resolve() for p in sys.argv[1:3])
manifest = json.loads((source/'product-manifest.json').read_text(encoding='utf-8'))
for name in list(manifest['hashes'])+['product-manifest.json']:
    original = (source/name).resolve()
    original.relative_to(source)
    destination = target/name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, destination)
PY
"$PYTHON" "$RELEASE/recal_product.py" --base "$RELEASE" --check
systemctl stop shengdi-product.service 2>/dev/null || true
if [ -e "$DEST/current.new" ] && [ ! -L "$DEST/current.new" ]; then
    echo 'Unexpected installation staging directory; stop and ask the maintainer'; exit 2
fi
ln -sfn "$RELEASE" "$DEST/current.new"
mv -Tf "$DEST/current.new" "$DEST/current"
install -d -o xilinx -g xilinx /home/xilinx/.local/state/shengdi
install -m 644 "$RELEASE/shengdi-product.service" /etc/systemd/system/shengdi-product.service
systemctl daemon-reload
systemctl enable --now shengdi-product.service
echo 'Installed. Startup remains muted; use the physical CAL / START / STOP controls.'

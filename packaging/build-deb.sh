#!/bin/sh
# Construye servidores-cli_<ver>_all.deb sin necesidad de dpkg-dev.
# Solo requiere: sh, ar, tar, gzip, python3.
# Uso: ./packaging/build-deb.sh   -> deja el .deb en dist/
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="servidores-cli"
VER="$(python3 -c "import re; print(re.search(r'__version__ *= *[\"\x27]([^\"\x27]+)', open('$ROOT/servidores_cli/__init__.py').read()).group(1))")"
ARCH="all"
OUTDIR="$ROOT/dist"
OUT="$OUTDIR/${PKG}_${VER}_${ARCH}.deb"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT INT TERM

# --- Árbol de datos ---
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/$PKG"
LIB="$STAGE/usr/lib/python3/dist-packages/servidores_cli"
mkdir -p "$LIB/commands"
cp "$ROOT/servidores_cli/"*.py "$LIB/"
cp "$ROOT/servidores_cli/commands/"*.py "$LIB/commands/"
rm -rf "$LIB/__pycache__" "$LIB/commands/__pycache__"

cat > "$STAGE/usr/bin/servidores" <<'EOF'
#!/bin/sh
# Vendored primero: combinación probada (click/textual/rich/...) gana a los
# paquetes del sistema para evitar mezclas de versiones en el parcial.
VENDOR=/usr/share/servidores-cli/vendored
if [ -d "$VENDOR" ]; then
  PYTHONPATH="$VENDOR${PYTHONPATH:+:$PYTHONPATH}"
  export PYTHONPATH
fi
exec /usr/bin/python3 -m servidores_cli "$@"
EOF
cat > "$STAGE/usr/bin/srv" <<'EOF'
#!/bin/sh
VENDOR=/usr/share/servidores-cli/vendored
if [ -d "$VENDOR" ]; then
  PYTHONPATH="$VENDOR${PYTHONPATH:+:$PYTHONPATH}"
  export PYTHONPATH
fi
exec /usr/bin/python3 -m servidores_cli "$@"
EOF
chmod 755 "$STAGE/usr/bin/servidores" "$STAGE/usr/bin/srv"

# .pth de respaldo: resuelve vendored también con `python3 -m servidores_cli`
# (los paquetes del sistema, si existen, tienen prioridad aquí).
echo "/usr/share/servidores-cli/vendored" > "$LIB/../servidores-cli-vendored.pth"

# --- Dependencias Python vendored (offline: click + textual + árbol) ---
# Ruedas puras (py3-none-any): se descomprimen tal cual, sin pip ni internet
# en el PC destino. Fijadas a la combinación probada por la suite (89 tests).
VENDOR="$STAGE/usr/share/servidores-cli/vendored"
mkdir -p "$VENDOR"
WHEELS="$(mktemp -d)"
python3 -m pip download --quiet --only-binary=:all: \
  --dest "$WHEELS" "click==8.5.0" "textual==8.2.8"
STAGE_VENV="$VENDOR" WHEELS="$WHEELS" python3 - <<'EOF'
import glob, os, zipfile
vendor = os.environ["STAGE_VENV"]
for whl in sorted(glob.glob(os.path.join(os.environ["WHEELS"], "*.whl"))):
    with zipfile.ZipFile(whl) as z:
        z.extractall(vendor)
print("ruedas instaladas:", len(glob.glob(os.path.join(os.environ["WHEELS"], "*.whl"))))
EOF
rm -rf "$WHEELS"
find "$VENDOR" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

cat > "$STAGE/usr/share/applications/servidores-cli.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Servidores CLI (Lab Comunicaciones)
GenericName=Despliegue de servidores de laboratorio
Comment=Despliega DNS (Bind9), DHCP, Correo (Postfix+Dovecot) y Web (Apache2) para los laboratorios de Comunicaciones (UdeA)
Exec=sh -c 'sudo -E servidores; echo; echo "--- Pulse Enter para cerrar ---"; read _'
Icon=utilities-terminal
Terminal=true
Categories=Education;System;
Keywords=servidores;dns;dhcp;correo;laboratorio;udea;
StartupNotify=false
EOF

cp "$ROOT/README.md" "$STAGE/usr/share/doc/$PKG/README.md"
cat > "$STAGE/usr/share/doc/$PKG/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Source: https://github.com/MalvarezU/Comu

Files: *
License: Material de curso (uso académico, Universidad de Antioquia)
EOF

# --- Control ---
# Solo exige python3: click/textual/rich/... van vendored dentro del paquete.
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: education
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9)
Recommends: bind9, dnsutils, isc-dhcp-server, postfix, dovecot-imapd, dovecot-pop3d, apache2, bsd-mailx
Maintainer: Curso Comunicaciones y Laboratorio (UdeA)
Description: CLI + TUI para desplegar servidores de laboratorio (DNS, DHCP, Correo, Web)
 Automatiza la instalación y configuración de Bind9, isc-dhcp-server,
 Postfix + Dovecot y Apache2 para los laboratorios de Comunicaciones.
 Incluye TUI interactivo y comandos CLI por servicio.
 Funciona sin internet: las dependencias Python (click, textual, rich)
 van incluidas en el paquete.
EOF
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v python3 >/dev/null 2>&1; then
  python3 -m compileall -q /usr/lib/python3/dist-packages/servidores_cli /usr/share/servidores-cli/vendored || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE/usr" "$STAGE/DEBIAN/control" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/usr/bin/servidores" "$STAGE/usr/bin/srv" "$STAGE/DEBIAN/postinst"

# --- Empaquetar (tars reproducibles vía python3: uid/gid 0, ordenados) ---
mkdir -p "$OUTDIR"
TMPDEB="$(mktemp -d)"
trap 'rm -rf "$STAGE" "$TMPDEB"' EXIT INT TERM
printf '2.0\n' > "$TMPDEB/debian-binary"
STAGE="$STAGE" TMPDEB="$TMPDEB" python3 - <<'EOF'
import gzip, os, tarfile
stage = os.environ["STAGE"]
tmp = os.environ["TMPDEB"]
MTIME = 1767225600  # 2026-01-01 UTC

def reset(ti):
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    ti.mtime = MTIME
    return ti

def mktar(src_dir, miembros, destino):
    with open(destino, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, mtime=0, fileobj=raw) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as t:
                for m in sorted(miembros):
                    t.add(os.path.join(src_dir, m), arcname=m, recursive=True, filter=reset)

mktar(os.path.join(stage, "DEBIAN"), ["control", "postinst"], os.path.join(tmp, "control.tar.gz"))
mktar(stage, ["./usr"], os.path.join(tmp, "data.tar.gz"))
EOF
(cd "$TMPDEB" && ar r "$OUT" debian-binary control.tar.gz data.tar.gz)

echo "OK: $OUT"
ls -la "$OUT"

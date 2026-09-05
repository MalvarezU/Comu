# servidores-cli · Guía de usuario

CLI + TUI para desplegar los servidores de Comunicaciones y Laboratorio (UdeA):
**DNS** (Bind9), **DHCP** (isc-dhcp-server), **Correo** (Postfix + Dovecot) y **Web** (Apache2).
Sin argumentos abre el TUI; con subcomando corre el CLI.

## Requisitos

- Linux Debian/Kali (VM del laboratorio), Python 3.9+, `pip` o `apt`.
- Root (`sudo`) para instalar, configurar y controlar servicios. Probar y sondear no lo exige.

## Instalación (una vez por máquina)

```bash
cd servidores-cli
python3 -m venv ~/.venv-serv
~/.venv-serv/bin/pip install -e .
```

Alternativa sin pip (Kali/Debian):

```bash
sudo apt install -y python3-click python3-textual
```

## TUI (recomendado en el parcial)

```bash
sudo ~/.venv-serv/bin/servidores   # si usó venv
sudo python3 -m servidores_cli     # directo desde la carpeta
```

Mapa de teclas (también hay botones para todo):

| Tecla | Acción |
|---|---|
| `1`–`4` | Menú de DNS / DHCP / Correo / Web |
| `d` | Despliegue completo paso a paso (18 pasos con checklist) |
| `t` | Topología y roles (quién es host, quién receptor) |
| `n` / `r` | Configurar red / ver estado de red |
| `f` | Firewall (ufw) |
| `c` | Parámetros (persisten en `~/.config/servidores-cli/config.json`) |
| `1`–`9` | Ejecutar paso dentro de un servicio · `t` = todos |
| `p` | Re-sondear · `l` limpiar bitácora · `x` dry-run on/off |
| `Esc`/`q` | Volver / salir |

Cada servicio muestra sus pasos en orden (instalar → configurar → iniciar) más verificación.
`deploy` corre todo y cierra con `Resumen: N OK, M con fallos`.

## CLI (scripts o sin TUI)

```bash
sudo servidores red config                    # IP estática + gateway
sudo servidores dns install|config|start      # igual para dhcp, mail, web
servidores dns status | servidores dns test   # estado y pruebas (dig A/PTR/MX/NS)
servidores panel                              # IP, rol y topología de esta máquina
sudo servidores deploy                        # todo de una vez + pruebas
servidores --dry-run deploy                   # simular sin tocar nada
```

Desde un nodo (receptor):

```bash
servidores dns test
servidores web test --host 192.168.1.12
servidores mail test --servidor 192.168.1.13
sudo servidores dhcp renew
```

Opciones globales (van entre `servidores` y el subcomando):

`--dominio` (midominio.com) · `-i/--interfaz` (eth0, `auto` detecta) · `--ip-dns`
(192.168.1.10) · `--ip-www` (.12) · `--ip-correo` (.13) · `--gateway` (.1) ·
`--forwarders` (8.8.8.8,8.8.4.4) · `--rango` (.100-.150) · `--lease-default/--lease-max` ·
`--dry-run`.

## Problemas comunes

- `requiere permisos de root` → reintente con `sudo` (y ruta del venv si aplica).
- `El TUI necesita 'textual'` → `pip install textual` o use los subcomandos CLI.
- Pruebas que fallan con `SIN RESPUESTA` → verifique red (`red estado`, `panel`) y
  firewall (`red firewall desactivar` solo en laboratorio).

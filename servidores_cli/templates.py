from datetime import datetime

from .config import Config


def _serial() -> int:
    return int(datetime.now().strftime("%Y%m%d") + "01")


def named_options(cfg: Config) -> str:
    reenviadores = "\n".join(f"        {ip};" for ip in cfg.forwarders)
    return f"""options {{
    directory "/var/cache/bind";

    forwarders {{
{reenviadores}
    }};

    dnssec-validation auto;
    listen-on-v6 {{ any; }};
}};
"""


def named_local(cfg: Config) -> str:
    return f"""zone "{cfg.dominio}" {{
    type master;
    file "/etc/bind/db.{cfg.dominio}";
}};

zone "{cfg.zona_inversa}" {{
    type master;
    file "{cfg.archivo_inverso}";
}};
"""


def zona_directa(cfg: Config) -> str:
    d = cfg.dominio
    return f"""; BIND archivo de datos para zona directa {d}
$TTL 604800
@    IN    SOA {d}. root.{d}. (
                   {_serial()}    ; Serial
                    604800    ; Refresh
                     86400    ; Retry
                   2419200    ; Expire
                    604800 )  ; Negative Cache TTL
;
@         IN    NS     ns.{d}.
@         IN    A      {cfg.ip_dns}
ns        IN    A      {cfg.ip_dns}
www       IN    A      {cfg.ip_www}
web       IN    CNAME  www
@         IN    MX 1   correo.{d}.
correo    IN    A      {cfg.ip_correo}
"""


def zona_inversa(cfg: Config) -> str:
    d = cfg.dominio
    ultimo = lambda ip: ip.split(".")[-1]
    return f"""; BIND archivo de zona inversa para la red {cfg.red}
$TTL 604800
@    IN    SOA ns.{d}. root.{d}. (
                   {_serial()}    ; Serial
                    604800    ; Refresh
                     86400    ; Retry
                   2419200    ; Expire
                    604800 )  ; Negative Cache TTL
;
@                   IN    NS    ns.{d}.
{ultimo(cfg.ip_dns)}     IN    PTR   ns.{d}.
{ultimo(cfg.ip_www)}     IN    PTR   www.{d}.
{ultimo(cfg.ip_correo)}  IN    PTR   correo.{d}.
"""


def dhcpd_conf(cfg: Config) -> str:
    a, b, c, _ = cfg.ip_dns.split(".")
    subred = f"{a}.{b}.{c}.0"
    return f"""# Configuración generada por servidores-cli
subnet {subred} netmask {cfg.netmask} {{
    range {cfg.rango_inicio} {cfg.rango_fin};
    option domain-name-servers {cfg.ip_dns}, {cfg.forwarders[0]};
    option domain-name "{cfg.dominio}";
    option routers {cfg.gateway};
    option broadcast-address {cfg.broadcast};
    default-lease-time {cfg.lease_default};
    max-lease-time {cfg.lease_max};
}}
"""


def isc_dhcp_default(cfg: Config) -> str:
    return f'INTERFACESv4="{cfg.interfaz}"\n'


def linea_hosts(cfg: Config) -> str:
    return f"{cfg.ip_correo}    correo.{cfg.dominio} correo"


def index_html(cfg: Config) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>{cfg.dominio}</title></head>
<body>
  <h1>Servidor Web de {cfg.dominio}</h1>
  <p>Laboratorio CL_03 - Comunicaciones y Laboratorio - UdeA</p>
</body>
</html>
"""

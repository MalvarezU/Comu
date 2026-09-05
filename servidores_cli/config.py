import ipaddress
import json
import os
from dataclasses import dataclass

RUTA_CONFIG = os.path.join(os.path.expanduser("~/.config"), "servidores-cli", "config.json")

CAMPOS_PERSISTENTES = (
    "dominio",
    "interfaz",
    "ip_dns",
    "ip_www",
    "ip_correo",
    "gateway",
    "rango_inicio",
    "rango_fin",
    "lease_default",
    "lease_max",
)


@dataclass
class Config:
    dominio: str = "midominio.com"
    interfaz: str = "eth0"
    ip_dns: str = "192.168.1.10"
    ip_www: str = "192.168.1.12"
    ip_correo: str = "192.168.1.13"
    gateway: str = "192.168.1.1"
    forwarders: tuple = ("8.8.8.8", "8.8.4.4")
    rango_inicio: str = "192.168.1.100"
    rango_fin: str = "192.168.1.150"
    lease_default: int = 600
    lease_max: int = 7200
    dry_run: bool = False

    @property
    def red(self) -> str:
        return str(ipaddress.ip_network(f"{self.ip_dns}/24", strict=False))

    @property
    def netmask(self) -> str:
        return str(ipaddress.ip_network(f"{self.ip_dns}/24", strict=False).netmask)

    @property
    def broadcast(self) -> str:
        a, b, c, _ = self.ip_dns.split(".")
        return f"{a}.{b}.{c}.255"

    @property
    def octetos_inversos(self) -> str:
        a, b, c, _ = self.ip_dns.split(".")
        return f"{c}.{b}.{a}"

    @property
    def zona_inversa(self) -> str:
        return f"{self.octetos_inversos}.in-addr.arpa"

    @property
    def archivo_inverso(self) -> str:
        return f"/etc/bind/db.{self.ip_dns.split('.')[0]}"


def detectar_interfaz() -> str:
    for nombre in sorted(os.listdir("/sys/class/net")):
        if nombre != "lo":
            return nombre
    return "eth0"


def guardar_config(cfg: "Config") -> str:
    carpeta = os.path.dirname(RUTA_CONFIG)
    os.makedirs(carpeta, exist_ok=True)
    datos = {campo: getattr(cfg, campo) for campo in CAMPOS_PERSISTENTES}
    datos["forwarders"] = list(cfg.forwarders)
    with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return RUTA_CONFIG


def cargar_config() -> dict:
    try:
        with open(RUTA_CONFIG, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def aplicar_config(cfg: "Config", datos: dict) -> None:
    for campo in CAMPOS_PERSISTENTES:
        if campo in datos:
            setattr(cfg, campo, datos[campo])
    forwarders = datos.get("forwarders")
    if isinstance(forwarders, list) and forwarders:
        cfg.forwarders = tuple(str(ip) for ip in forwarders)

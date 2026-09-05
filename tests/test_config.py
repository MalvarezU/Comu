import json

import servidores_cli.config as config
from servidores_cli.config import (
    Config,
    aplicar_config,
    cargar_config,
    detectar_interfaz,
    guardar_config,
)


class TestPropiedades:
    def test_por_defecto(self):
        cfg = Config()
        assert cfg.red == "192.168.1.0/24"
        assert cfg.netmask == "255.255.255.0"
        assert cfg.broadcast == "192.168.1.255"
        assert cfg.octetos_inversos == "1.168.192"
        assert cfg.zona_inversa == "1.168.192.in-addr.arpa"
        assert cfg.archivo_inverso == "/etc/bind/db.192"

    def test_red_custom(self):
        cfg = Config(ip_dns="10.0.5.7")
        assert cfg.red == "10.0.5.0/24"
        assert cfg.octetos_inversos == "5.0.10"
        assert cfg.archivo_inverso == "/etc/bind/db.10"


class TestPersistencia:
    def test_roundtrip(self, tmp_path, monkeypatch):
        ruta = str(tmp_path / "config.json")
        monkeypatch.setattr(config, "RUTA_CONFIG", ruta)
        cfg = Config(dominio="lab.xyz", ip_dns="10.0.0.10", forwarders=("1.1.1.1",))
        assert guardar_config(cfg) == ruta
        datos = json.load(open(ruta, encoding="utf-8"))
        assert datos["dominio"] == "lab.xyz"
        assert datos["forwarders"] == ["1.1.1.1"]
        assert "dry_run" not in datos  # no persiste estado efímero

        otra = Config()
        aplicar_config(otra, cargar_config())
        assert otra.dominio == "lab.xyz"
        assert otra.ip_dns == "10.0.0.10"
        assert otra.forwarders == ("1.1.1.1",)
        assert otra.rango_inicio == "192.168.1.100"  # default intacto

    def test_cargar_inexistente(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RUTA_CONFIG", str(tmp_path / "no.json"))
        assert cargar_config() == {}

    def test_cargar_corrupto(self, tmp_path, monkeypatch):
        ruta = tmp_path / "config.json"
        ruta.write_text("{no es json", encoding="utf-8")
        monkeypatch.setattr(config, "RUTA_CONFIG", str(ruta))
        assert cargar_config() == {}

    def test_aplicar_ignora_basura(self):
        cfg = Config()
        aplicar_config(cfg, {"dominio": "x.y", "campo_desconocido": 1, "forwarders": "no-lista"})
        assert cfg.dominio == "x.y"
        assert cfg.forwarders == ("8.8.8.8", "8.8.4.4")


class TestDetectarInterfaz:
    def test_devuelve_nombre_valido(self):
        nombre = detectar_interfaz()
        assert isinstance(nombre, str) and nombre
        assert nombre != "lo"

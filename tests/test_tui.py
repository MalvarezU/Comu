import pytest

pytest.importorskip("textual")

from servidores_cli.config import Config
from servidores_cli.tui import (
    Parametros,
    estado_compacto,
    estado_verbose,
)


def d(vivo, tcp=None, puerto=None):
    return {"vivo": vivo, "tcp": tcp, "puerto": puerto}


class TestEstadoVerbose:
    def test_sin_sondeo(self):
        assert estado_verbose(d(None)) == "(sin sondeo)"

    def test_sin_respuesta(self):
        assert estado_verbose(d(False)) == "SIN RESPUESTA"

    def test_solo_ping(self):
        assert estado_verbose(d(True, puerto=None)) == "ALCANZABLE (ping)"

    def test_puerto_abierto(self):
        assert estado_verbose(d(True, tcp=True, puerto=80)) == "ALCANZABLE · 80/TCP abierto"

    def test_puerto_cerrado(self):
        assert estado_verbose(d(True, tcp=False, puerto=25)) == "ALCANZABLE · 25/TCP cerrado"


class TestEstadoCompacto:
    def test_sin_sondeo(self):
        assert estado_compacto(d(None)) == "(?)"

    def test_sin_respuesta(self):
        assert estado_compacto(d(False)) == "[X]"

    def test_solo_ping(self):
        assert estado_compacto(d(True, puerto=None)) == "[OK]"

    def test_puerto(self):
        assert estado_compacto(d(True, tcp=True, puerto=80)) == "[OK:80]"
        assert estado_compacto(d(True, tcp=False, puerto=80)) == "[!]:80"


class TestValidacionParametros:
    def _valores_validos(self):
        return {
            "dominio": "lab.xyz",
            "interfaz": "eth0",
            "ip_dns": "192.168.1.10",
            "ip_www": "192.168.1.12",
            "ip_correo": "192.168.1.13",
            "gateway": "192.168.1.1",
            "forwarders": "8.8.8.8,8.8.4.4",
            "rango": "192.168.1.100-192.168.1.150",
            "lease_default": "600",
            "lease_max": "7200",
        }

    def test_valido(self):
        Parametros(Config())._validar(self._valores_validos())

    def test_vacio(self):
        valores = self._valores_validos()
        valores["dominio"] = "  "
        with pytest.raises(ValueError, match="dominio"):
            Parametros(Config())._validar(valores)

    def test_ip_mala(self):
        valores = self._valores_validos()
        valores["ip_dns"] = "no-ip"
        with pytest.raises(ValueError):
            Parametros(Config())._validar(valores)

    def test_lease_no_positivo(self):
        valores = self._valores_validos()
        valores["lease_default"] = "0"
        with pytest.raises(ValueError, match="arriendo"):
            Parametros(Config())._validar(valores)

    def test_lease_no_numerico(self):
        valores = self._valores_validos()
        valores["lease_max"] = "abc"
        with pytest.raises(ValueError):
            Parametros(Config())._validar(valores)

    def test_rango_malo(self):
        valores = self._valores_validos()
        valores["rango"] = "1.2.3.4"
        with pytest.raises(ValueError):
            Parametros(Config())._validar(valores)

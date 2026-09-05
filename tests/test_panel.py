from servidores_cli.commands import panel
from servidores_cli.config import Config


class TestClasificacion:
    def test_es_servidor_dns(self):
        rol, roles = panel._clasificar(Config(), ["192.168.1.10"])
        assert rol == "SERVIDOR / HOST"
        assert ("DNS + DHCP", "192.168.1.10") in roles

    def test_es_servidor_web(self):
        rol, roles = panel._clasificar(Config(), ["192.168.1.12"])
        assert rol == "SERVIDOR / HOST"
        assert ("WEB", "192.168.1.12") in roles

    def test_servidor_multiple(self):
        rol, roles = panel._clasificar(Config(), ["192.168.1.10", "192.168.1.13"])
        assert rol == "SERVIDOR / HOST"
        assert len(roles) == 2

    def test_cliente_en_rango_dhcp(self):
        rol, roles = panel._clasificar(Config(), ["192.168.1.120"])
        assert rol.startswith("NODO / CLIENTE (IP entregada")
        assert roles == []

    def test_cliente_ip_fija(self):
        rol, roles = panel._clasificar(Config(), ["192.168.1.200"])
        assert rol == "NODO / CLIENTE"
        assert roles == []

    def test_sin_ip(self):
        rol, roles = panel._clasificar(Config(), [])
        assert rol == "NODO / CLIENTE"
        assert roles == []


class TestRangoDhcp:
    def test_dentro(self):
        assert panel._en_rango_dhcp(Config(), ["192.168.1.100", "192.168.1.150"]) is True

    def test_fuera(self):
        assert panel._en_rango_dhcp(Config(), ["192.168.1.99"]) is False

    def test_rango_invertido_tambien_valido(self):
        assert panel._en_rango_dhcp(Config(rango_inicio="192.168.1.150", rango_fin="192.168.1.100"), ["192.168.1.120"]) is True

    def test_rango_invalido(self):
        cfg = Config(rango_inicio="no-ip", rango_fin="tampoco")
        assert panel._en_rango_dhcp(cfg, ["192.168.1.120"]) is False


class TestResumenRol:
    def test_servidor(self, monkeypatch):
        monkeypatch.setattr(panel, "_ipv4_locales", lambda: [("eth0", "192.168.1.10")])
        resumen = panel.resumen_rol(Config())
        assert "SERVIDOR / HOST" in resumen
        assert "DNS + DHCP" in resumen

    def test_cliente(self, monkeypatch):
        monkeypatch.setattr(panel, "_ipv4_locales", lambda: [("eth0", "192.168.1.200")])
        assert "NODO / CLIENTE" in panel.resumen_rol(Config())

    def test_sin_ipv4(self, monkeypatch):
        monkeypatch.setattr(panel, "_ipv4_locales", lambda: [])
        assert "sin IPv4 detectada" in panel.resumen_rol(Config())


class TestEstadosSinSondeo:
    def test_sin_sondeo(self):
        class Run:
            dry_run = False

        assert panel._estado_desde(Run(), "192.168.1.10", 80, True) == "(sondeo desactivado)"

    def test_dry_run(self):
        class Run:
            dry_run = True

        assert "dry-run" in panel._estado_desde(Run(), "192.168.1.10", 80, False)

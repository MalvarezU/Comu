from servidores_cli.config import Config
from servidores_cli.templates import (
    dhcpd_conf,
    index_html,
    isc_dhcp_default,
    linea_hosts,
    named_local,
    named_options,
    zona_directa,
    zona_inversa,
)


def cfg(**kwargs) -> Config:
    return Config(**kwargs)


class TestNamedOptions:
    def test_contiene_forwarders(self):
        texto = named_options(cfg())
        assert "8.8.8.8;" in texto
        assert "8.8.4.4;" in texto
        assert 'directory "/var/cache/bind";' in texto

    def test_sin_forwarders(self):
        texto = named_options(cfg(forwarders=()))
        assert "forwarders" in texto
        assert "8.8.8.8" not in texto


class TestNamedLocal:
    def test_zonas_directa_e_inversa(self):
        texto = named_local(cfg())
        assert 'zone "midominio.com"' in texto
        assert 'zone "1.168.192.in-addr.arpa"' in texto
        assert 'file "/etc/bind/db.midominio.com";' in texto
        assert 'file "/etc/bind/db.192";' in texto


class TestZonaDirecta:
    def test_registros(self):
        texto = zona_directa(cfg())
        for esperado in (
            "@    IN    SOA midominio.com. root.midominio.com. (",
            "@         IN    NS     ns.midominio.",
            "www       IN    A      192.168.1.12",
            "web       IN    CNAME  www",
            "@         IN    MX 1   correo.midominio.",
            "correo    IN    A      192.168.1.13",
        ):
            assert esperado in texto

    def test_dominio_custom(self):
        texto = zona_directa(cfg(dominio="lab.xyz"))
        assert "zone" not in texto
        assert "lab.xyz." in texto


class TestZonaInversa:
    def test_ptr_usa_ultimo_octeto(self):
        texto = zona_inversa(cfg())
        assert "10     IN    PTR   ns.midominio." in texto
        assert "12     IN    PTR   www.midominio." in texto
        assert "13     IN    PTR   correo.midominio." in texto


class TestDhcpdConf:
    def test_contenido(self):
        texto = dhcpd_conf(cfg())
        assert "subnet 192.168.1.0 netmask 255.255.255.0 {" in texto
        assert "range 192.168.1.100 192.168.1.150;" in texto
        assert "option routers 192.168.1.1;" in texto
        assert "option broadcast-address 192.168.1.255;" in texto
        assert "default-lease-time 600;" in texto
        assert "max-lease-time 7200;" in texto

    def test_dns_con_forwarders(self):
        assert "option domain-name-servers 192.168.1.10, 8.8.8.8, 8.8.4.4;" in dhcpd_conf(cfg())

    def test_sin_forwarders_no_explota(self):
        texto = dhcpd_conf(cfg(forwarders=()))
        assert "option domain-name-servers 192.168.1.10;" in texto

    def test_rango_custom(self):
        texto = dhcpd_conf(cfg(rango_inicio="192.168.1.50", rango_fin="192.168.1.99"))
        assert "range 192.168.1.50 192.168.1.99;" in texto


class TestOtros:
    def test_isc_dhcp_default(self):
        assert isc_dhcp_default(cfg(interfaz="ens33")) == 'INTERFACESv4="ens33"\n'

    def test_linea_hosts(self):
        assert linea_hosts(cfg()) == "192.168.1.13    correo.midominio.com correo"

    def test_index_html(self):
        texto = index_html(cfg(dominio="lab.xyz"))
        assert "<title>lab.xyz</title>" in texto
        assert "Servidor Web de lab.xyz" in texto

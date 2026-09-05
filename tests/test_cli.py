import pytest
from click.testing import CliRunner

from servidores_cli import __version__
from servidores_cli.cli import cli


@pytest.fixture()
def runner():
    return CliRunner()


class TestAyuda:
    def test_help(self, runner):
        res = runner.invoke(cli, ["--help"])
        assert res.exit_code == 0
        for comando in ("dns", "dhcp", "mail", "web", "red", "panel", "deploy"):
            assert comando in res.output

    def test_version(self, runner):
        res = runner.invoke(cli, ["--version"])
        assert res.exit_code == 0
        assert __version__ in res.output

    def test_help_de_subcomando(self, runner):
        res = runner.invoke(cli, ["dns", "--help"])
        assert res.exit_code == 0
        assert "install" in res.output
        assert "test" in res.output


class TestValidacionOpciones:
    def test_rango_mal_formado(self, runner):
        res = runner.invoke(cli, ["--rango", "sin-guion", "panel"])
        assert res.exit_code != 0
        assert "--rango" in res.output

    def test_ip_invalida(self, runner):
        res = runner.invoke(cli, ["--ip-dns", "no-ip", "panel"])
        assert res.exit_code != 0
        assert "--ip-dns" in res.output

    def test_gateway_invalido(self, runner):
        res = runner.invoke(cli, ["--gateway", "999.1.1.1", "panel"])
        assert res.exit_code != 0
        assert "--gateway" in res.output

    def test_forwarder_invalido(self, runner):
        res = runner.invoke(cli, ["--forwarders", "8.8.8.8,malo", "panel"])
        assert res.exit_code != 0
        assert "forwarder" in res.output

    def test_rango_ips_invalidas(self, runner):
        res = runner.invoke(cli, ["--rango", "1.2.3.4-no", "panel"])
        assert res.exit_code != 0


class TestPanel:
    def test_panel_sin_sondeo(self, runner):
        res = runner.invoke(cli, ["panel", "--sin-sondeo"])
        assert res.exit_code == 0
        assert "PANEL DE LA INSTANCIA" in res.output
        assert "192.168.1.10" in res.output

    def test_panel_custom(self, runner):
        res = runner.invoke(
            cli,
            ["--dominio", "lab.xyz", "--ip-dns", "10.0.0.10", "panel", "--sin-sondeo"],
        )
        assert res.exit_code == 0
        assert "lab.xyz" in res.output
        assert "10.0.0.10" in res.output


class TestDryRun:
    def test_deploy(self, runner):
        res = runner.invoke(cli, ["--dry-run", "deploy"])
        assert res.exit_code == 0, res.output
        assert "MODO DRY-RUN" in res.output
        assert "Despliegue completo" in res.output
        assert "Todos los servidores pasaron" in res.output

    def test_deploy_sin_pruebas(self, runner):
        res = runner.invoke(cli, ["--dry-run", "deploy", "--sin-pruebas"])
        assert res.exit_code == 0, res.output
        assert "Todos los servidores pasaron" not in res.output

    def test_dns_config(self, runner):
        res = runner.invoke(cli, ["--dry-run", "dns", "config"])
        assert res.exit_code == 0, res.output
        assert "dry-run" in res.output

    def test_dns_test(self, runner):
        res = runner.invoke(cli, ["--dry-run", "dns", "test"])
        assert res.exit_code == 0, res.output

    def test_dhcp_config_sin_forwarders(self, runner):
        res = runner.invoke(cli, ["--dry-run", "--forwarders", "", "dhcp", "config"])
        assert res.exit_code == 0, res.output
        assert "option domain-name-servers 192.168.1.10;" in res.output

    def test_mail_config(self, runner):
        res = runner.invoke(cli, ["--dry-run", "mail", "config"])
        assert res.exit_code == 0, res.output

    def test_web_config(self, runner):
        res = runner.invoke(cli, ["--dry-run", "web", "config"])
        assert res.exit_code == 0, res.output
        assert "/var/www/html/index.html" in res.output

    def test_web_simple(self, runner):
        res = runner.invoke(cli, ["--dry-run", "web", "simple"])
        assert res.exit_code == 0, res.output
        assert "http.server" in res.output

    def test_red_config(self, runner):
        res = runner.invoke(cli, ["--dry-run", "red", "config"])
        assert res.exit_code == 0, res.output

    def test_tui_requiere_tty(self, runner):
        res = runner.invoke(cli, [])
        assert res.exit_code != 0
        assert "terminal interactiva" in res.output

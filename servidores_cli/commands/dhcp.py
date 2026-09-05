import shutil

import click

from ..templates import dhcpd_conf, isc_dhcp_default

SERVICIO = "isc-dhcp-server"


@click.group("dhcp", help="Servidor DHCP con isc-dhcp-server (instalar, configurar, iniciar, estado, test).")
def grupo():
    pass


@grupo.command("install", help="Instala isc-dhcp-server.")
@click.pass_obj
def install(app):
    _instalar(app)


@grupo.command("config", help="Configura la interfaz de escucha y el rango en dhcpd.conf.")
@click.pass_obj
def config(app):
    _configurar(app)


@grupo.command("start", help="Reinicia el servicio DHCP y muestra su estado.")
@click.pass_obj
def start(app):
    _iniciar(app)


@grupo.command("status", help="Muestra el estado del servicio DHCP.")
@click.pass_obj
def status(app):
    _estado(app)


@grupo.command("test", help="Verifica que el servicio esté activo y escuchando en el puerto 67/UDP.")
@click.pass_obj
def test(app):
    if not _probar(app):
        raise click.ClickException("Pruebas DHCP con fallos")


@grupo.command("renew", help="Libera y renueva la IP de esta máquina con dhclient (uso en el CLIENTE).")
@click.option("--auto", is_flag=True, help="No pedir confirmación.")
@click.pass_obj
def renew(app, auto):
    _renovar(app, confirmar=not auto)


def _instalar(app):
    run = app.run
    run.check_root()
    run.run(["apt-get", "install", "-y", "isc-dhcp-server"], check=True)
    run.warn("Es normal que el servicio falle al iniciar antes de configurar la subred")
    run.ok("isc-dhcp-server instalado")


def _configurar(app):
    run, cfg = app.run, app.cfg
    run.check_root()
    run.escribir("/etc/default/isc-dhcp-server", isc_dhcp_default(cfg))
    run.escribir("/etc/dhcp/dhcpd.conf", dhcpd_conf(cfg))
    if run.dry_run:
        run.info("validaría: dhcpd -t -cf /etc/dhcp/dhcpd.conf")
        return
    binario = shutil.which("dhcpd") or "/usr/sbin/dhcpd"
    res = run.consultar([binario, "-t", "-cf", "/etc/dhcp/dhcpd.conf"])
    salida = ((res.stdout or "") + (res.stderr or "")).strip()
    if res.returncode != 0:
        run.error(salida)
        run.warn("Sintaxis de dhcpd.conf inválida; corrija antes de reiniciar")
        return
    run.detalle(salida)
    run.ok("Sintaxis de dhcpd.conf válida")


def _iniciar(app):
    app.run.check_root()
    app.run.run(["systemctl", "restart", SERVICIO], check=True)
    app.run.ok(f"Servicio {SERVICIO} reiniciado")
    _estado(app)


def _estado(app):
    app.run.run(["systemctl", "--no-pager", "--full", "status", SERVICIO])


def _activo(run, servicio):
    return run.consultar(["systemctl", "is-active", servicio]).returncode == 0


def _probar(app) -> bool:
    run = app.run
    if run.dry_run:
        run.dry(f"$ systemctl is-active {SERVICIO}")
        run.dry("$ ss -uln | grep :67")
        return True
    activo = _activo(run, SERVICIO)
    if activo:
        run.ok(f"El servicio {SERVICIO} está activo")
    else:
        run.error(f"El servicio {SERVICIO} no está activo")
    res = run.consultar(["ss", "-uln"])
    escuchando = ":67 " in (res.stdout or "")
    if escuchando:
        run.ok("El servidor está escuchando en el puerto 67/UDP")
    else:
        run.error("El servidor NO está escuchando en el puerto 67/UDP")
    if activo and escuchando:
        run.info("En el cliente ejecute: dhclient -r && dhclient (o use: servidores dhcp renew)")
    return activo and escuchando


def _renovar(app, confirmar=True):
    run = app.run
    run.warn("Esto liberará y renovará la dirección IP de ESTA máquina (dhclient -r && dhclient)")
    if confirmar and not run.dry_run and not click.confirm("¿Continuar?", default=True):
        raise click.Abort()
    run.check_root()
    run.run(["dhclient", "-r"])
    run.run(["dhclient"])
    run.ok("Renovación solicitada. Verifique con: ip a")

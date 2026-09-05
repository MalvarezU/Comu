import sys

import click

import ipaddress

from . import __version__
from .config import Config, detectar_interfaz
from .commands import dhcp as cmd_dhcp
from .commands import dns as cmd_dns
from .commands import mail as cmd_mail
from .commands import panel as cmd_panel
from .commands import red as cmd_red
from .commands import web as cmd_web
from .runner import Contexto, Runner


def _ip(valor: str, etiqueta: str) -> str:
    try:
        ipaddress.ip_address(valor)
    except ValueError:
        raise click.ClickException(f"{etiqueta} no es una IP válida: {valor}")
    return valor


def _abrir_tui(cfg: Config) -> None:
    if not sys.stdout.isatty():
        raise click.ClickException(
            "El TUI necesita una terminal interactiva. Use los subcomandos CLI (ver --help)."
        )
    try:
        from .tui import lanzar_tui
    except ImportError:
        raise click.ClickException(
            "El TUI necesita el paquete 'textual' (pip install textual).\n"
            "Mientras tanto puede usar los subcomandos CLI (ver --help) o 'servidores panel'."
        )
    lanzar_tui(cfg)


@click.group(
    "servidores",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, "-V", "--version")
@click.option("--dominio", default="midominio.com", show_default=True, help="Dominio del laboratorio.")
@click.option(
    "--interfaz",
    "-i",
    default="eth0",
    show_default=True,
    help="Interfaz de red del servidor ('auto' para detectarla).",
)
@click.option(
    "--ip-dns",
    default="192.168.1.10",
    show_default=True,
    help="IP del servidor (el DNS debe ser 192.168.1.10 según la guía).",
)
@click.option("--ip-www", default="192.168.1.12", show_default=True, help="IP que anunciará el registro www.")
@click.option("--ip-correo", default="192.168.1.13", show_default=True, help="IP del servidor de correo.")
@click.option("--gateway", default="192.168.1.1", show_default=True, help="Puerta de enlace predeterminada.")
@click.option(
    "--forwarders",
    default="8.8.8.8,8.8.4.4",
    show_default=True,
    help="DNS externos para reenvío, separados por coma.",
)
@click.option(
    "--rango",
    default="192.168.1.100-192.168.1.150",
    show_default=True,
    help="Rango dinámico del DHCP (inicio-fin).",
)
@click.option(
    "--lease-default",
    default=600,
    show_default=True,
    help="Tiempo de arriendo por defecto del DHCP (segundos).",
)
@click.option(
    "--lease-max",
    default=7200,
    show_default=True,
    help="Tiempo máximo de arriendo del DHCP (segundos).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Muestra los comandos y archivos que se ejecutarían/escribirían, sin tocar nada.",
)
@click.pass_context
def cli(
    ctx,
    dominio,
    interfaz,
    ip_dns,
    ip_www,
    ip_correo,
    gateway,
    forwarders,
    rango,
    lease_default,
    lease_max,
    dry_run,
):
    """Automatiza la instalación y configuración de los servidores de los laboratorios de
    Comunicaciones y Laboratorio (UdeA): DNS (Bind9), DHCP (isc-dhcp-server),
    Correo (Postfix + Dovecot) y Web (Apache2).

    Sin argumentos abre el TUI (dashboard interactivo).
    Use --dry-run para previsualizar todo sin ejecutar nada.
    """
    if interfaz == "auto":
        interfaz = detectar_interfaz()
    try:
        inicio, fin = (parte.strip() for parte in rango.split("-", 1))
    except ValueError:
        raise click.ClickException("--rango debe tener el formato IP_inicio-IP_fin")
    ip_dns = _ip(ip_dns, "--ip-dns")
    ip_www = _ip(ip_www, "--ip-www")
    ip_correo = _ip(ip_correo, "--ip-correo")
    gateway = _ip(gateway, "--gateway")
    inicio = _ip(inicio, "El inicio de --rango")
    fin = _ip(fin, "El fin de --rango")
    forwarders = tuple(
        _ip(p.strip(), f"El forwarder '{p.strip()}'")
        for p in forwarders.split(",")
        if p.strip()
    )
    cfg = Config(
        dominio=dominio,
        interfaz=interfaz,
        ip_dns=ip_dns,
        ip_www=ip_www,
        ip_correo=ip_correo,
        gateway=gateway,
        forwarders=forwarders,
        rango_inicio=inicio,
        rango_fin=fin,
        lease_default=lease_default,
        lease_max=lease_max,
        dry_run=dry_run,
    )
    ctx.obj = Contexto(cfg=cfg, run=Runner(dry_run))
    if dry_run:
        click.secho("== MODO DRY-RUN: no se ejecutará ni escribirá nada ==", fg="magenta", bold=True)
    if ctx.invoked_subcommand is None:
        _abrir_tui(cfg)


cli.add_command(cmd_red.grupo)
cli.add_command(cmd_dns.grupo)
cli.add_command(cmd_dhcp.grupo)
cli.add_command(cmd_mail.grupo)
cli.add_command(cmd_web.grupo)
cli.add_command(cmd_panel.panel)


@cli.command("tui", help="Abre el TUI (igual que ejecutar 'servidores' sin subcomando).")
@click.pass_obj
def tui(app):
    _abrir_tui(app.cfg)


@cli.command("deploy", help="Despliega todo de una vez (red + DNS + DHCP + correo + web) y corre las pruebas.")
@click.option("--sin-pruebas", is_flag=True, help="No ejecutar las pruebas finales de verificación.")
@click.pass_obj
def deploy(app, sin_pruebas):
    from .commands import dhcp, dns, mail, red, web
    from .commands.panel import resumen_rol

    red._configurar(app)
    app.run.info(f"Panel: {resumen_rol(app.cfg)}")
    dns._instalar(app)
    dns._configurar(app)
    dns._iniciar(app)
    cmd_dhcp._instalar(app)
    cmd_dhcp._configurar(app)
    cmd_dhcp._iniciar(app)
    mail._instalar(app)
    mail._configurar(app)
    mail._usuarios(app, mail.USUARIO1, mail.USUARIO2, mail.CLAVE)
    mail._iniciar(app)
    web._instalar(app)
    web._configurar(app)
    web._iniciar(app)
    app.run.ok("Despliegue completo")

    if sin_pruebas:
        return
    resultados = {
        "DNS": dns._probar(app),
        "DHCP": cmd_dhcp._probar(app),
        "Correo": mail._probar(app, "localhost", mail.USUARIO1, mail.USUARIO2, mail.CLAVE),
        "Web": web._probar(app, "localhost"),
    }
    fallos = [nombre for nombre, exito in resultados.items() if not exito]
    if fallos:
        raise click.ClickException(f"Verificación con fallos en: {', '.join(fallos)}")
    app.run.ok("Todos los servidores pasaron las pruebas de verificación")

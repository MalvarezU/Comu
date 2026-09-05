import click

from ..config import detectar_interfaz


@click.group("red", help="Configuración de la interfaz de red y del firewall del servidor.")
def grupo():
    pass


@grupo.command("config", help="Levanta la interfaz, asigna la IP estática y configura la ruta por defecto.")
@click.option("--sin-gateway", is_flag=True, help="No configura la ruta por defecto.")
@click.pass_obj
def config(app, sin_gateway):
    _configurar(app, sin_gateway)


@grupo.command("estado", help="Muestra las interfaces (ip a) y la tabla de rutas.")
@click.pass_obj
def estado(app):
    _estado(app)


@grupo.command("firewall", help="Gestiona el firewall local con ufw (estado | desactivar).")
@click.argument("accion", type=click.Choice(["estado", "desactivar"]))
@click.pass_obj
def firewall(app, accion):
    _firewall(app, accion)


def _configurar(app, sin_gateway=False):
    run, cfg = app.run, app.cfg
    run.check_root()
    itf = cfg.interfaz or detectar_interfaz()
    run.run(["ip", "link", "set", "dev", itf, "up"], check=True)
    res = run.consultar(["ip", "-o", "addr", "show", "dev", itf])
    if cfg.ip_dns in (res.stdout or ""):
        run.info(f"{cfg.ip_dns}/24 ya está asignada a {itf}")
    else:
        run.run(["ip", "addr", "add", f"{cfg.ip_dns}/24", "dev", itf], check=True)
    if not sin_gateway:
        rutas = run.consultar(["ip", "route", "show", "default"])
        if cfg.gateway in (rutas.stdout or ""):
            run.info(f"La ruta por defecto vía {cfg.gateway} ya existe")
        else:
            run.run(["ip", "route", "add", "default", "via", cfg.gateway, "dev", itf], check=True)
    run.ok(f"Interfaz {itf} configurada con {cfg.ip_dns}/24")


def _estado(app):
    app.run.run(["ip", "addr"])
    app.run.run(["ip", "route"])


def _firewall(app, accion):
    run = app.run
    if accion == "estado":
        run.run(["ufw", "status"])
        return
    run.check_root()
    run.run(["ufw", "disable"], check=True)
    run.warn("Firewall deshabilitado (recomendado solo para laboratorio)")

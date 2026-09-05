import re
import shutil

import click

from ..templates import named_local, named_options, zona_directa, zona_inversa

SERVICIO = "bind9"


@click.group("dns", help="Servidor DNS con Bind9 (instalar, configurar, iniciar, estado, test).")
def grupo():
    pass


@grupo.command("install", help="Instala Bind9 y dnsutils (dig, nslookup).")
@click.pass_obj
def install(app):
    _instalar(app)


@grupo.command("config", help="Escribe named.conf.options, named.conf.local y las zonas directa/inversa.")
@click.pass_obj
def config(app):
    _configurar(app)


@grupo.command("start", help="Reinicia bind9 y muestra su estado.")
@click.pass_obj
def start(app):
    _iniciar(app)


@grupo.command("status", help="Muestra el estado del servicio bind9.")
@click.pass_obj
def status(app):
    _estado(app)


@grupo.command("test", help="Prueba resolución directa (A), inversa (PTR), MX y NS con dig.")
@click.pass_obj
def test(app):
    if not _probar(app):
        raise click.ClickException("Pruebas DNS con fallos")


def _instalar(app):
    run = app.run
    run.check_root()
    run.run(["apt-get", "update"], check=True)
    run.run(["apt-get", "install", "-y", "bind9", "dnsutils"], check=True)
    run.ok("Bind9 y dnsutils instalados")


def _configurar(app):
    run, cfg = app.run, app.cfg
    run.check_root()
    base = "/etc/bind"
    directa = f"{base}/db.{cfg.dominio}"
    run.escribir(f"{base}/named.conf.options", named_options(cfg))
    run.escribir(f"{base}/named.conf.local", named_local(cfg))
    run.escribir(directa, zona_directa(cfg))
    run.escribir(cfg.archivo_inverso, zona_inversa(cfg))
    if run.dry_run:
        run.info("validaría: named-checkconf, named-checkzone (directa e inversa)")
        return
    validaciones = (
        [shutil.which("named-checkconf") or "/usr/sbin/named-checkconf"],
        [shutil.which("named-checkzone") or "/usr/sbin/named-checkzone", cfg.dominio, directa],
        [shutil.which("named-checkzone") or "/usr/sbin/named-checkzone", cfg.zona_inversa, cfg.archivo_inverso],
    )
    for comando in validaciones:
        res = run.consultar(comando)
        salida = ((res.stdout or "") + (res.stderr or "")).strip()
        if res.returncode != 0:
            run.error(salida)
            run.warn("Corrija los errores de sintaxis antes de reiniciar el servicio")
            return
        run.detalle(salida)
    run.ok("Configuración DNS validada")

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
    run, cfg = app.run, app.cfg
    pruebas = (
        ("Resolución directa (A) de www", [f"www.{cfg.dominio}"]),
        ("Resolución inversa (PTR)", ["-x", cfg.ip_dns]),
        ("Registro MX del dominio", [cfg.dominio, "MX"]),
        ("Registro NS del dominio", [cfg.dominio, "NS"]),
    )
    fallos = 0
    for nombre, args in pruebas:
        cmd = ["dig", "+time=3", "+tries=1", f"@{cfg.ip_dns}", *args]
        if run.dry_run:
            run.dry(f"$ {' '.join(cmd)}")
            continue
        res = run.consultar(cmd)
        salida = res.stdout or ""
        exito = _dig_ok(salida)
        if exito:
            run.ok(nombre)
        else:
            run.error(nombre)
            fallos += 1
        run.linea(salida.strip())
    if not run.dry_run:
        run.ok("Todas las pruebas DNS pasaron") if fallos == 0 else run.warn(
            f"{fallos} de {len(pruebas)} pruebas DNS fallaron"
        )
    return fallos == 0


def _dig_ok(salida: str) -> bool:
    coincidencia = re.search(r"status:\s*([A-Z]+)", salida)
    if not coincidencia or coincidencia.group(1) != "NOERROR":
        return False
    if "ANSWER SECTION:" not in salida:
        return False
    bloque = salida.split("ANSWER SECTION:", 1)[1]
    respuestas = [
        linea
        for linea in bloque.splitlines()[1:]
        if linea.strip() and not linea.strip().startswith(";;")
    ]
    return bool(respuestas)

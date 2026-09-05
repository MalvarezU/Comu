import urllib.request

import click

from ..templates import index_html

SERVICIO = "apache2"


@click.group("web", help="Servidor Web del lab CL_03: Apache2 (o http.server de Python con 'simple').")
def grupo():
    pass


@grupo.command("install", help="Instala Apache2.")
@click.pass_obj
def install(app):
    _instalar(app)


@grupo.command("config", help="Escribe la página inicial en /var/www/html/index.html.")
@click.pass_obj
def config(app):
    _configurar(app)


@grupo.command("start", help="Reinicia Apache2 y muestra su estado.")
@click.pass_obj
def start(app):
    _iniciar(app)


@grupo.command("status", help="Muestra el estado de Apache2.")
@click.pass_obj
def status(app):
    _estado(app)


@grupo.command("test", help="Hace una petición HTTP y muestra el código de respuesta.")
@click.option("--host", default="localhost", show_default=True, help="Host a probar (desde el cliente use la IP).")
@click.pass_obj
def test(app, host):
    if not _probar(app, host):
        raise click.ClickException("Prueba web con fallos")


@grupo.command("simple", help="Levanta un servidor HTTP simple con Python (sin Apache, en cualquier máquina).")
@click.option("--puerto", default=8080, show_default=True)
@click.option("--directorio", default=".", show_default=True)
@click.pass_obj
def simple(app, puerto, directorio):
    _simple(app, puerto, directorio)


def _instalar(app):
    run = app.run
    run.check_root()
    run.run(["apt-get", "install", "-y", "apache2"], check=True)
    run.ok("Apache2 instalado")


def _configurar(app):
    run, cfg = app.run, app.cfg
    run.check_root()
    run.escribir("/var/www/html/index.html", index_html(cfg))
    run.ok("Página inicial escrita")


def _iniciar(app):
    app.run.check_root()
    app.run.run(["systemctl", "restart", SERVICIO], check=True)
    app.run.ok(f"Servicio {SERVICIO} reiniciado")
    _estado(app)


def _estado(app):
    app.run.run(["systemctl", "--no-pager", "--full", "status", SERVICIO])


def _probar(app, host) -> bool:
    run = app.run
    url = f"http://{host}/"
    if run.dry_run:
        run.dry(f"GET {url}")
        return True
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            cuerpo = respuesta.read(300).decode("utf-8", "replace")
            run.ok(f"HTTP {respuesta.status} desde {url}")
            run.linea(cuerpo.strip()[:200])
            return True
    except Exception as e:
        run.error(f"No se pudo conectar a {url}: {e}")
        return False


def _simple(app, puerto, directorio):
    run = app.run
    cmd = ["python3", "-m", "http.server", str(puerto), "--bind", "0.0.0.0", "--directory", directorio]
    if run.dry_run:
        run.run(cmd)
        return
    run.info(f"Servidor HTTP simple sirviendo {directorio} en el puerto {puerto} (Ctrl+C para detener)")
    try:
        import subprocess

        subprocess.run(cmd)
    except KeyboardInterrupt:
        click.echo("")
        run.ok("Servidor HTTP simple detenido")

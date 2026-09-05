import click

from ..templates import linea_hosts

SERVICIOS = ("postfix", "dovecot")
USUARIO1 = "user1"
USUARIO2 = "user2"
CLAVE = "1234"


@click.group("mail", help="Servidor de correo con Postfix (SMTP) + Dovecot (IMAP/POP3).")
def grupo():
    pass


@grupo.command("install", help="Instala Postfix, Dovecot (imap/pop3) y mailx (preseed no interactivo).")
@click.pass_obj
def install(app):
    _instalar(app)


@grupo.command("config", help="Agrega la entrada en /etc/hosts, los protocolos de Dovecot y mydestination en Postfix.")
@click.pass_obj
def config(app):
    _configurar(app)


@grupo.command("usuarios", help="Crea los usuarios de correo del laboratorio de forma no interactiva.")
@click.option("--usuario1", default=USUARIO1, show_default=True)
@click.option("--usuario2", default=USUARIO2, show_default=True)
@click.option("--clave", default=CLAVE, show_default=True, help="Contraseña para ambos usuarios.")
@click.pass_obj
def usuarios(app, usuario1, usuario2, clave):
    _usuarios(app, usuario1, usuario2, clave)


@grupo.command("start", help="Reinicia postfix y dovecot.")
@click.pass_obj
def start(app):
    _iniciar(app)


@grupo.command("status", help="Muestra el estado de postfix y dovecot.")
@click.pass_obj
def status(app):
    _estado(app)


@grupo.command("test", help="Envía un correo por SMTP y lo verifica por IMAP.")
@click.option("--servidor", default="localhost", show_default=True, help="Host del servidor de correo para las pruebas.")
@click.option("--usuario1", default=USUARIO1, show_default=True)
@click.option("--usuario2", default=USUARIO2, show_default=True)
@click.option("--clave", default=CLAVE, show_default=True)
@click.pass_obj
def test(app, servidor, usuario1, usuario2, clave):
    if not _probar(app, servidor, usuario1, usuario2, clave):
        raise click.ClickException("Pruebas de correo con fallos")


def _instalar(app):
    run, cfg = app.run, app.cfg
    run.check_root()
    run.run_shell(
        'echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections',
        check=True,
    )
    run.run_shell(f'echo "postfix postfix/mailname string {cfg.dominio}" | debconf-set-selections', check=True)
    run.run(["apt-get", "install", "-y", "postfix", "dovecot-imapd", "dovecot-pop3d", "bsd-mailx"], check=True)
    run.ok("Postfix, Dovecot (imap/pop3) y bsd-mailx instalados")


def _configurar(app):
    run, cfg = app.run, app.cfg
    run.check_root()
    _asegurar_hosts(run, cfg)
    _asegurar_dovecot(run)
    _asegurar_postfix(run, cfg)


def _asegurar_hosts(run, cfg):
    ruta = "/etc/hosts"
    linea = linea_hosts(cfg)
    if run.dry_run:
        run.dry(f"agregaría a {ruta}: {linea}")
        return
    with open(ruta, encoding="utf-8") as f:
        contenido = f.read()
    if f"correo.{cfg.dominio}" in contenido:
        run.info("La entrada de /etc/hosts para el correo ya existe")
        return
    run.escribir(ruta, contenido.rstrip("\n") + "\n" + linea + "\n")


def _asegurar_dovecot(run):
    ruta = "/etc/dovecot/dovecot.conf"
    linea = "protocols = imap pop3"
    if run.dry_run:
        run.dry(f"verificaría/apendaría '{linea}' en {ruta}")
        return
    with open(ruta, encoding="utf-8") as f:
        contenido = f.read()
    for l in contenido.splitlines():
        if l.strip().startswith("protocols") and not l.strip().startswith("#"):
            run.info(f"Dovecot ya tiene: {l.strip()}")
            return
    run.escribir(ruta, contenido.rstrip("\n") + "\n" + linea + "\n")


def _asegurar_postfix(run, cfg):
    ruta = "/etc/postfix/main.cf"
    if run.dry_run:
        run.dry(f"verificaría '{cfg.dominio}' en mydestination de {ruta}")
        return
    with open(ruta, encoding="utf-8") as f:
        contenido = f.read()
    if cfg.dominio in contenido:
        run.info("main.cf ya referencia al dominio del laboratorio")
        return
    nueva = f"mydestination = $myhostname, localhost, {cfg.dominio}"
    run.escribir(ruta, contenido.rstrip("\n") + "\n" + nueva + "\n")


def _usuarios(app, usuario1, usuario2, clave):
    run = app.run
    run.check_root()
    for u in (usuario1, usuario2):
        existe = run.consultar(["id", u]).returncode == 0
        if existe:
            run.info(f"El usuario {u} ya existe")
            continue
        run.run(["useradd", "-m", "-s", "/bin/bash", u], check=True)
        run.run_shell(f"echo '{u}:{clave}' | chpasswd", check=True)
        run.ok(f"Usuario {u} creado")
    run.info(f"Puede probar con: echo 'Cuerpo' | mail -s 'Asunto' {usuario2}@{app.cfg.dominio}")


def _iniciar(app):
    app.run.check_root()
    for servicio in SERVICIOS:
        app.run.run(["systemctl", "restart", servicio], check=True)
    app.run.ok("Servicios postfix y dovecot reiniciados")
    _estado(app)


def _estado(app):
    for servicio in SERVICIOS:
        app.run.run(["systemctl", "--no-pager", "--full", "status", servicio])


def _activo(run, servicio):
    return run.consultar(["systemctl", "is-active", servicio]).returncode == 0


def _probar(app, servidor, usuario1, usuario2, clave) -> bool:
    run, cfg = app.run, app.cfg
    if run.dry_run:
        run.dry("$ systemctl is-active postfix dovecot")
        run.dry(
            f"envío SMTP de {usuario1}@{cfg.dominio} a {usuario2}@{cfg.dominio} "
            f"vía {servidor}:25 y verificación IMAP en {servidor}:143"
        )
        return True
    fallos = 0
    for servicio in SERVICIOS:
        if _activo(run, servicio):
            run.ok(f"Servicio {servicio} activo")
        else:
            run.error(f"Servicio {servicio} inactivo")
            fallos += 1
    remitente = f"{usuario1}@{cfg.dominio}"
    destino = f"{usuario2}@{cfg.dominio}"
    try:
        import smtplib
        from email.message import EmailMessage

        mensaje = EmailMessage()
        mensaje["From"] = remitente
        mensaje["To"] = destino
        mensaje["Subject"] = "Prueba servidores-cli"
        mensaje.set_content("Correo de prueba generado por servidores-cli")
        with smtplib.SMTP(servidor, 25, timeout=10) as smtp:
            smtp.sendmail(remitente, [destino], mensaje.as_string())
        run.ok(f"Correo enviado por SMTP ({remitente} -> {destino})")
    except Exception as e:
        run.error(f"Fallo el envío SMTP: {e}")
        run.warn("Verifique que postfix esté activo y que el dominio esté en mydestination (servidores mail config)")
        fallos += 1
    try:
        import imaplib

        with imaplib.IMAP4(servidor, 143) as imap:
            imap.login(usuario2, clave)
            estado, datos = imap.select("INBOX")
            cantidad = len(datos[0].split()) if estado == "OK" and datos and datos[0] else 0
            run.ok(f"Buzón IMAP de {usuario2}: {cantidad} mensaje(s)")
    except Exception as e:
        run.warn(f"No se pudo verificar el buzón IMAP: {e}")
        run.warn("¿Ya creó los usuarios? Ejecute: sudo servidores mail usuarios")
    return fallos == 0

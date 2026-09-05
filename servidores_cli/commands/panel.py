import ipaddress
import re
import socket
import subprocess

import click


def _ipv4_locales():
    try:
        res = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        entradas = []
        for linea in res.stdout.splitlines():
            m = re.match(r"\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)", linea.strip())
            if m and m.group(2) != "127.0.0.1":
                entradas.append((m.group(1), m.group(2)))
        if entradas:
            return entradas
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    try:
        salida = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=10
        ).stdout
        return [("--", ip) for ip in salida.split() if "." in ip]
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return []


def _roles_servidor(cfg, solo_ips):
    roles = []
    if cfg.ip_dns in solo_ips:
        roles.append(("DNS + DHCP", cfg.ip_dns))
    if cfg.ip_www in solo_ips:
        roles.append(("WEB", cfg.ip_www))
    if cfg.ip_correo in solo_ips:
        roles.append(("CORREO", cfg.ip_correo))
    return roles


def _en_rango_dhcp(cfg, solo_ips):
    try:
        a = ipaddress.ip_address(cfg.rango_inicio)
        b = ipaddress.ip_address(cfg.rango_fin)
        lo, hi = min(a, b), max(a, b)
    except ValueError:
        return False
    return any(lo <= ipaddress.ip_address(ip) <= hi for ip in solo_ips)


def _clasificar(cfg, solo_ips):
    roles = _roles_servidor(cfg, solo_ips)
    if roles:
        return "SERVIDOR / HOST", roles
    if _en_rango_dhcp(cfg, solo_ips):
        return "NODO / CLIENTE (IP entregada por el DHCP del laboratorio)", []
    return "NODO / CLIENTE", []


def resumen_rol(cfg) -> str:
    solo = [ip for _, ip in _ipv4_locales()]
    texto = ", ".join(solo) if solo else "sin IPv4 detectada"
    rol, roles = _clasificar(cfg, solo)
    if roles:
        servicios = " + ".join(nombre for nombre, _ in roles)
        return f"IP local {texto} -> esta instancia es {rol}: {servicios}"
    return f"IP local {texto} -> esta instancia es {rol}"


def _ping_ok(ip):
    try:
        res = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _tcp_ok(ip, puerto):
    try:
        with socket.create_connection((ip, puerto), timeout=1.5):
            return True
    except OSError:
        return False


def _estado_desde(run, ip, puerto, sin_sondeo):
    if sin_sondeo:
        return "(sondeo desactivado)"
    if run.dry_run:
        extra = f" y puerto {puerto}/TCP" if puerto else ""
        return f"(dry-run: se sondearía con ping{extra})"
    vivo = _ping_ok(ip)
    if vivo is None:
        return "(no se pudo sondear)"
    if not vivo:
        return "SIN RESPUESTA (ping)"
    if puerto is None:
        return "ALCANZABLE (ping)"
    abierto = _tcp_ok(ip, puerto)
    detalle = f"puerto {puerto}/TCP " + ("abierto" if abierto else "cerrado")
    return f"ALCANZABLE (ping) - {detalle}"


@click.command("panel", help="Panel de esta instancia: IP local, rol (servidor o nodo) y estado de los servidores del laboratorio.")
@click.option("--sin-sondeo", is_flag=True, help="No hace ping ni conexiones hacia los servidores.")
@click.pass_obj
def panel(app, sin_sondeo):
    run, cfg = app.run, app.cfg
    entradas = _ipv4_locales()
    solo = [ip for _, ip in entradas]

    click.secho("== PANEL DE LA INSTANCIA ==", bold=True, fg="cyan")
    click.echo(f"Host:      {socket.gethostname()}")
    click.echo(f"Dominio:   {cfg.dominio}      Red: {cfg.red}")
    if entradas:
        for itf, ip in entradas:
            click.echo(f"Interfaz:  {itf:<12} IP: {ip}")
    else:
        run.warn("Sin IPv4 detectada. Servidor: servidores red config | Nodo: sudo dhclient")

    rol, roles = _clasificar(cfg, solo)
    click.echo("")
    click.secho("-- Rol de esta instancia --", bold=True)
    if roles:
        click.secho(f"*** {rol} ***", fg="green", bold=True)
        for nombre, ip in roles:
            click.echo(f"   - SERVIDOR {nombre} en {ip} (esta máquina)")
        run.info("Siguiente paso en esta máquina: sudo servidores deploy")
    else:
        click.secho(f"*** {rol} ***", fg="yellow", bold=True)
        run.info("Nodo: no instala servicios, solo consulta y prueba (ver comandos al final)")

    click.echo("")
    click.secho(f"-- Topología del laboratorio ({cfg.dominio}) --", bold=True)
    topo = (
        ("DNS + DHCP", f"ns.{cfg.dominio}", cfg.ip_dns, None),
        ("Web", f"www.{cfg.dominio}", cfg.ip_www, 80),
        ("Correo", f"correo.{cfg.dominio}", cfg.ip_correo, 25),
    )
    for nombre, host, ip, puerto in topo:
        estado = _estado_desde(run, ip, puerto, sin_sondeo)
        propio = "  <- esta máquina" if ip in solo else ""
        color = "green"
        if estado.startswith("SIN"):
            color = "red"
        elif "cerrado" in estado or estado.startswith("("):
            color = "yellow"
        click.echo(f"  {nombre:<12} {host:<26} {ip:<15} ", nl=False)
        click.secho(f"{estado}{propio}", fg=color)
    click.echo(
        f"  {'Nodos':<12} {'clientes (sin servicios)':<26} "
        f"{cfg.rango_inicio} - {cfg.rango_fin} (DHCP) o estáticas"
    )

    if not roles:
        click.echo("")
        click.secho("-- Comandos útiles desde este NODO --", bold=True)
        click.echo(f"  servidores dns test                          (consultas dig al {cfg.ip_dns})")
        click.echo(f"  servidores web test --host {cfg.ip_www}")
        click.echo(f"  servidores mail test --servidor {cfg.ip_correo}")
        click.echo("  sudo servidores dhcp renew                   (liberar y renovar IP por DHCP)")

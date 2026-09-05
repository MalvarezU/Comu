import ipaddress
import os
import socket

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static
from rich.text import Text

from .commands import mail, red
from .commands.panel import _clasificar, _ipv4_locales, _ping_ok, _tcp_ok
from .config import Config, aplicar_config, cargar_config, guardar_config
from .tui_base import CSS, PASOS_DEPLOY, SERVICIOS, Bitacora, PantallaConBitacora


def sondear_topologia(cfg):
    datos = []
    for largo, corto, host, ip, puerto in (
        ("SERVIDOR DNS + DHCP", "DNS+DHCP", f"ns.{cfg.dominio}", cfg.ip_dns, None),
        ("SERVIDOR Web", "Web", f"www.{cfg.dominio}", cfg.ip_www, 80),
        ("SERVIDOR Correo", "Correo", f"correo.{cfg.dominio}", cfg.ip_correo, 25),
    ):
        vivo = _ping_ok(ip)
        tcp = _tcp_ok(ip, puerto) if (vivo and puerto) else None
        datos.append(
            {"largo": largo, "corto": corto, "host": host, "ip": ip,
             "puerto": puerto, "vivo": vivo, "tcp": tcp}
        )
    return datos


def estado_verbose(d):
    if d["vivo"] is None:
        return "(sin sondeo)"
    if not d["vivo"]:
        return "SIN RESPUESTA"
    if d["puerto"] is None:
        return "ALCANZABLE (ping)"
    return f"ALCANZABLE · {d['puerto']}/TCP " + ("abierto" if d["tcp"] else "cerrado")


def estado_compacto(d):
    if d["vivo"] is None:
        return "(?)"
    if not d["vivo"]:
        return "[X]"
    if d["puerto"] is None:
        return "[OK]"
    return f"[OK:{d['puerto']}]" if d["tcp"] else f"[!]:{d['puerto']}"


class Panel(PantallaConBitacora):
    BINDINGS = [
        Binding("p", "refrescar", "Refrescar"),
        Binding("d", "desplegar", "Desplegar todo"),
        Binding("n", "red_config", "Red: configurar"),
        Binding("r", "red_estado", "Red: estado"),
        Binding("f", "firewall", "Firewall"),
        Binding("t", "topologia", "Topología"),
        Binding("c", "parametros", "Parámetros"),
        Binding("1", "abrir_servicio('dns')", "DNS"),
        Binding("2", "abrir_servicio('dhcp')", "DHCP"),
        Binding("3", "abrir_servicio('correo')", "Correo"),
        Binding("4", "abrir_servicio('web')", "Web"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("== Panel principal ==", id="titulo")
        with Horizontal(id="principal"):
            with VerticalScroll(id="panel_info"):
                yield Static(id="rol")
                yield DataTable(id="topologia")
                yield Static(
                    Text(
                        "Maq.=esta máquina · [OK]=responde · [OK:80]=puerto abierto · "
                        "[X]=sin respuesta"
                    ),
                    id="leyenda",
                )
            with VerticalScroll(id="menu"):
                yield Label("[b]Asistente completo[/b]")
                yield Button("Desplegar TODO paso a paso", id="btn_deploy", variant="primary")
                yield Label("[b]Servidores (menú anidado)[/b]")
                yield Button("1 · DNS (Bind9) · UDP 53", id="btn_dns")
                yield Button("2 · DHCP · UDP 67/68", id="btn_dhcp")
                yield Button("3 · Correo · SMTP/IMAP", id="btn_correo")
                yield Button("4 · Web (Apache2) · TCP 80", id="btn_web")
                yield Label("[b]General[/b]")
                yield Button("Configurar red (IP estática)", id="btn_red")
                yield Button("Estado de red (ip a / rutas)", id="btn_red_estado")
                yield Button("Firewall (ufw)", id="btn_firewall")
                yield Button("Topología y roles (t)", id="btn_topologia")
                yield Button("Parámetros del laboratorio", id="btn_parametros")
        yield Bitacora(id="log")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one("#topologia", DataTable)
        tabla.add_columns("Servicio", "IP", "Estado", "Maq.")
        self.query_one("#btn_deploy", Button).focus()
        self.refrescar()

    def on_screen_resume(self) -> None:
        self.refrescar()

    def refrescar(self) -> None:
        self.run_worker(self._sondear, thread=True, exclusive=True)

    def _sondear(self) -> None:
        cfg = self.app.cfg
        entradas = _ipv4_locales()
        solo = [ip for _, ip in entradas]
        rol, roles = _clasificar(cfg, solo)
        filas = [
            (d["corto"], d["ip"], estado_compacto(d), "SÍ" if d["ip"] in solo else "")
            for d in sondear_topologia(cfg)
        ]
        filas.append(("Receptores", "rango DHCP", "—", ""))
        self.app.call_from_thread(self._pintar, entradas, rol, roles, filas)

    def _pintar(self, entradas, rol, roles, filas) -> None:
        cfg = self.app.cfg
        ips = ", ".join(ip for _, ip in entradas) or "sin IPv4 (revise: ip a)"
        if roles:
            detalle = "\n".join(f"   · SERVIDOR {nombre} en {ip} (esta máquina)" for nombre, ip in roles)
            rol_txt = f"[b green]*** {rol} ***[/]\n{detalle}"
        else:
            rol_txt = f"[b yellow]*** {rol} ***[/]"
        if os.geteuid() != 0:
            rol_txt += "\n[b yellow]Sin root: solo sondea y prueba. Use: sudo servidores[/]"
        self.query_one("#rol", Static).update(
            f"[b]Host:[/] {socket.gethostname()}    [b]IP local:[/] {ips}\n"
            f"[b]Dominio:[/] {cfg.dominio}    [b]Red:[/] {cfg.red}\n{rol_txt}"
        )
        tabla = self.query_one("#topologia", DataTable)
        tabla.clear()
        for fila in filas:
            tabla.add_row(*fila)
        self.app.sub_title = (
            f"{cfg.dominio} · {cfg.red}"
            f"{' · DRY-RUN' if self.app.dry_run else ''}"
            f"{' · SIN ROOT' if os.geteuid() != 0 else ''}"
        )

    def action_refrescar(self) -> None:
        self.refrescar()

    def action_parametros(self) -> None:
        self.app.push_screen(Parametros(self.app.cfg))

    def action_desplegar(self) -> None:
        self.app.push_screen(AsistenteDeploy())

    def action_firewall(self) -> None:
        self.app.push_screen(FirewallMenu())

    def action_topologia(self) -> None:
        self.app.push_screen(Topologia())

    def action_red_config(self) -> None:
        self.ejecutar("Configurar red", red._configurar)

    def action_red_estado(self) -> None:
        self.ejecutar("Estado de red", red._estado)

    def action_abrir_servicio(self, servicio: str) -> None:
        self.app.push_screen(PantallaServicio(SERVICIOS[servicio]))

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        mapa = {
            "btn_deploy": self.action_desplegar,
            "btn_dns": lambda: self.action_abrir_servicio("dns"),
            "btn_dhcp": lambda: self.action_abrir_servicio("dhcp"),
            "btn_correo": lambda: self.action_abrir_servicio("correo"),
            "btn_web": lambda: self.action_abrir_servicio("web"),
            "btn_red": self.action_red_config,
            "btn_red_estado": self.action_red_estado,
            "btn_firewall": self.action_firewall,
            "btn_topologia": self.action_topologia,
            "btn_parametros": self.action_parametros,
        }
        accion = mapa.get(evento.button.id)
        if accion:
            accion()


class PantallaServicio(PantallaConBitacora):
    BINDINGS = [
        Binding("escape", "volver", "Volver"),
        Binding("q", "volver", "Volver"),
        Binding("t", "todos", "Todos"),
    ] + [Binding(str(i), f"atajo('{i}')", "") for i in range(1, 10)]

    def __init__(self, spec):
        super().__init__()
        self.spec = spec

    def _intro(self) -> str:
        cfg = self.app.cfg
        return (
            self.spec["intro"]
            .replace("{dominio}", cfg.dominio)
            .replace("{rango}", f"{cfg.rango_inicio} - {cfg.rango_fin}")
            .replace("{u1}", mail.USUARIO1)
            .replace("{u2}", mail.USUARIO2)
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"== {self.spec['titulo']} ==", id="titulo")
        with Horizontal(id="principal"):
            with VerticalScroll(id="pasos_col"):
                yield Static(self._intro(), id="intro")
                yield Label("[b]Pasos en orden (asistente)[/b]")
                for i, (etiqueta, _) in enumerate(self.spec["pasos"], 1):
                    yield Button(f"[{i}] {etiqueta}", id=f"paso_{i}")
                yield Button("[T] Ejecutar TODOS los pasos", id="btn_todos", variant="primary")
            with VerticalScroll(id="extras_col"):
                yield Label("[b]Verificación y extras[/b]")
                base = len(self.spec["pasos"])
                for j, (etiqueta, _) in enumerate(self.spec["extras"], base + 1):
                    yield Button(f"[{j}] {etiqueta}", id=f"extra_{j - base}")
                yield Button("Volver (Esc)", id="btn_volver", variant="error")
        yield Bitacora(id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.app.sub_title = f"{self.app.cfg.dominio} · {self.spec['titulo']}"
        self.query_one("#paso_1", Button).focus()

    def action_volver(self) -> None:
        self.app.pop_screen()

    def action_todos(self) -> None:
        self.secuencia(self.spec["titulo"], self.spec["pasos"])

    def action_atajo(self, tecla: str) -> None:
        plana = list(self.spec["pasos"]) + list(self.spec["extras"])
        indice = int(tecla) - 1
        if 0 <= indice < len(plana):
            etiqueta, funcion = plana[indice]
            self.ejecutar(etiqueta, funcion)

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        ident = evento.button.id
        if ident == "btn_volver":
            self.action_volver()
        elif ident == "btn_todos":
            self.action_todos()
        elif ident and ident.startswith("paso_"):
            indice = int(ident.split("_")[1]) - 1
            etiqueta, funcion = self.spec["pasos"][indice]
            self.ejecutar(etiqueta, funcion)
        elif ident and ident.startswith("extra_"):
            indice = int(ident.split("_")[1]) - 1
            etiqueta, funcion = self.spec["extras"][indice]
            self.ejecutar(etiqueta, funcion)


class AsistenteDeploy(PantallaConBitacora):
    BINDINGS = [Binding("escape", "volver", "Volver")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("== Despliegue completo ==", id="titulo")
        with Horizontal(id="principal"):
            with VerticalScroll(id="lista_pasos"):
                yield Static(
                    "[b]Despliegue completo paso a paso[/] - red, DNS, DHCP, correo y web,\n"
                    "con pruebas de verificación al final.",
                    id="intro_dep",
                )
                for i, (etiqueta, _) in enumerate(PASOS_DEPLOY):
                    yield Static(Text(f"[ ]  {etiqueta}"), id=f"dep_{i}")
            with VerticalScroll(id="menu"):
                yield Label("[b]Control[/b]")
                yield Button("Iniciar despliegue", id="btn_iniciar", variant="primary")
                yield Button("Volver (Esc)", id="btn_volver", variant="error")
        yield Bitacora(id="log")
        yield Footer()

    def _marcar(self, indice: int, estado: str) -> None:
        from rich.text import Text

        etiqueta = PASOS_DEPLOY[indice][0]
        estilos = {
            "curso": ("[>>]", "cyan"),
            "hecho": ("[OK]", "bold green"),
            "fallo": ("[--]", "yellow"),
            "error": ("[X]", "bold red"),
        }
        simbolo, estilo = estilos.get(estado, ("[ ]", ""))
        texto = Text(f"{simbolo}  {etiqueta}")
        texto.stylize(estilo, 0, len(simbolo))
        self.query_one(f"#dep_{indice}", Static).update(texto)

    def on_mount(self) -> None:
        self.app.sub_title = f"{self.app.cfg.dominio} · Despliegue completo"
        self.query_one("#btn_iniciar", Button).focus()

    def action_volver(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn_volver":
            self.action_volver()
        elif evento.button.id == "btn_iniciar":
            self.secuencia("Despliegue", PASOS_DEPLOY, marcar=self._marcar)


class FirewallMenu(PantallaConBitacora):
    BINDINGS = [Binding("escape", "volver", "Volver")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("== Firewall (ufw) ==", id="titulo")
        with Horizontal(id="principal"):
            with VerticalScroll(id="pasos_col"):
                yield Static(
                    "[b]Firewall local (ufw)[/]\n"
                    "El runbook del curso recomienda deshabilitarlo en laboratorios\n"
                    "para evitar el bloqueo de tráfico (DNS 53, DHCP 67, SMTP 25...).",
                    id="intro",
                )
                yield Label("[b]Acciones[/b]")
                yield Button("Ver estado (ufw status)", id="btn_fw_estado")
                yield Button("Desactivar (ufw disable)", id="btn_fw_off", variant="warning")
            with VerticalScroll(id="extras_col"):
                yield Label("[b]Navegación[/b]")
                yield Button("Volver (Esc)", id="btn_volver", variant="error")
        yield Bitacora(id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.app.sub_title = f"{self.app.cfg.dominio} · Firewall"
        self.query_one("#btn_fw_estado", Button).focus()

    def action_volver(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn_volver":
            self.action_volver()
        elif evento.button.id == "btn_fw_estado":
            self.ejecutar("Estado del firewall", red._firewall, "estado")
        elif evento.button.id == "btn_fw_off":
            self.ejecutar("Desactivar firewall", red._firewall, "desactivar")


class Topologia(Screen):
    BINDINGS = [
        Binding("escape", "volver", "Volver"),
        Binding("q", "volver", "Volver"),
        Binding("p", "refrescar", "Sondear"),
        Binding("c", "parametros", "Configurar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("== Topología y roles ==", id="titulo")
        with Horizontal(id="principal"):
            with VerticalScroll(id="lista_pasos"):
                yield Static(
                    "[b]SERVIDOR/HOST[/] = PC con la IP del servicio (.10/.12/.13): instala y atiende.\n"
                    "[b]RECEPTORES[/] = demás PCs (rango DHCP o IP fija): solo consultan y prueban.\n"
                    "La columna 'Esta máq.' dice qué es ESTA máquina.",
                    id="intro_dep",
                )
                yield DataTable(id="topologia")
                yield Static(id="nota")
            with VerticalScroll(id="menu"):
                yield Label("[b]Acciones[/b]")
                yield Button("Sondear de nuevo (p)", id="btn_sondear")
                yield Button("Configurar topología (c)", id="btn_conf")
                yield Button("Volver (Esc)", id="btn_volver", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.app.sub_title = f"{self.app.cfg.dominio} · Topología y roles"
        tabla = self.query_one("#topologia", DataTable)
        tabla.add_columns("Rol", "Host", "IP", "Estado desde aquí", "Esta máq.")
        self.query_one("#btn_sondear", Button).focus()
        self.refrescar()

    def refrescar(self) -> None:
        self.run_worker(self._sondear, thread=True, exclusive=True)

    def _sondear(self) -> None:
        cfg = self.app.cfg
        solo = [ip for _, ip in _ipv4_locales()]
        filas = [
            (d["largo"], d["host"], d["ip"], estado_verbose(d),
             "SÍ - esta máquina" if d["ip"] in solo else "")
            for d in sondear_topologia(cfg)
        ]
        filas.append(
            (
                "RECEPTORES (clientes)",
                "PCs del laboratorio",
                f"{cfg.rango_inicio} - {cfg.rango_fin}",
                "solo consultan servicios",
                "",
            )
        )
        self.app.call_from_thread(self._pintar, filas)

    def _pintar(self, filas) -> None:
        tabla = self.query_one("#topologia", DataTable)
        tabla.clear()
        for fila in filas:
            tabla.add_row(*fila)
        self.query_one("#nota", Static).update(
            "Para cambiar dominio, IPs o rango: pulse c (Parámetros). "
            "Al volver, la tabla se actualiza sola."
        )

    def action_volver(self) -> None:
        self.app.pop_screen()

    def action_refrescar(self) -> None:
        self.refrescar()

    def action_parametros(self) -> None:
        self.app.push_screen(Parametros(self.app.cfg))

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn_volver":
            self.action_volver()
        elif evento.button.id == "btn_sondear":
            self.action_refrescar()
        elif evento.button.id == "btn_conf":
            self.action_parametros()


CAMPOS_PARAMETROS = (
    ("dominio", "Dominio del laboratorio", "texto"),
    ("interfaz", "Interfaz de red (eth0 / auto)", "texto"),
    ("ip_dns", "IP del servidor DNS+DHCP (ej. 192.168.1.10)", "ip"),
    ("ip_www", "IP del servidor web", "ip"),
    ("ip_correo", "IP del servidor de correo", "ip"),
    ("gateway", "Puerta de enlace", "ip"),
    ("forwarders", "DNS externos (coma)", "texto"),
    ("rango", "Rango DHCP (inicio-fin)", "rango"),
    ("lease_default", "Arriendo por defecto (s)", "int"),
    ("lease_max", "Arriendo máximo (s)", "int"),
)


class Parametros(PantallaConBitacora):
    BINDINGS = [Binding("escape", "volver", "Volver")]

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("== Parámetros del laboratorio ==", id="titulo")
        with VerticalScroll(id="form"):
            yield Static(
                "[b]Parámetros del laboratorio[/] - se guardan en ~/.config/servidores-cli/config.json\n"
                "Enter salta al siguiente campo; con Tab llega a los botones.",
                id="intro",
            )
            for campo, etiqueta, _ in CAMPOS_PARAMETROS:
                yield Label(etiqueta)
                yield Input(value=self._valor(campo), id=f"in_{campo}")
        with Horizontal(id="menu"):
            yield Button("Guardar", id="btn_guardar", variant="primary")
            yield Button("Volver sin guardar (Esc)", id="btn_volver", variant="error")
        yield Bitacora(id="log")
        yield Footer()

    def _valor(self, campo: str) -> str:
        if campo == "forwarders":
            return ",".join(self.cfg.forwarders)
        if campo == "rango":
            return f"{self.cfg.rango_inicio}-{self.cfg.rango_fin}"
        return str(getattr(self.cfg, campo))

    def on_mount(self) -> None:
        self.app.sub_title = f"{self.app.cfg.dominio} · Parámetros"
        self.query_one("#in_dominio", Input).focus()

    def action_volver(self) -> None:
        self.app.pop_screen()

    def _validar(self, valores: dict) -> None:
        for campo, _, tipo in CAMPOS_PARAMETROS:
            valor = valores[campo].strip()
            if not valor:
                raise ValueError(f"{campo} vacío")
            if tipo == "ip":
                ipaddress.ip_address(valor)
            elif tipo == "int":
                if int(valor) <= 0:
                    raise ValueError("el arriendo debe ser mayor que 0")
            elif tipo == "rango":
                inicio, _, fin = valor.partition("-")
                ipaddress.ip_address(inicio)
                ipaddress.ip_address(fin)

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        if evento.button.id == "btn_volver":
            self.action_volver()
            return
        if evento.button.id != "btn_guardar":
            return
        valores = {
            campo: self.query_one(f"#in_{campo}", Input).value
            for campo, _, _ in CAMPOS_PARAMETROS
        }
        try:
            self._validar(valores)
        except ValueError as e:
            self.app.notify(f"Valor inválido: {e}", severity="error")
            return
        cfg = self.app.cfg
        cfg.dominio = valores["dominio"].strip()
        cfg.interfaz = valores["interfaz"].strip()
        cfg.ip_dns = valores["ip_dns"].strip()
        cfg.ip_www = valores["ip_www"].strip()
        cfg.ip_correo = valores["ip_correo"].strip()
        cfg.gateway = valores["gateway"].strip()
        cfg.forwarders = tuple(p.strip() for p in valores["forwarders"].split(",") if p.strip())
        inicio, _, fin = valores["rango"].partition("-")
        cfg.rango_inicio = inicio.strip()
        cfg.rango_fin = fin.strip()
        cfg.lease_default = int(valores["lease_default"])
        cfg.lease_max = int(valores["lease_max"])
        if cfg.interfaz == "auto":
            from .config import detectar_interfaz

            cfg.interfaz = detectar_interfaz()
        ruta = guardar_config(cfg)
        self.app.notify(f"Parámetros guardados en {ruta}")
        self.app.pop_screen()


class ServidoresApp(App):
    TITLE = "Servidores - Comunicaciones y Laboratorio (UdeA)"
    CSS = CSS

    BINDINGS = [
        Binding("q", "salir", "Salir"),
        Binding("x", "toggle_dry", "Dry-run on/off"),
    ]

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.dry_run = cfg.dry_run

    def get_default_screen(self):
        return Panel()

    def action_salir(self) -> None:
        self.exit()

    def action_toggle_dry(self) -> None:
        self.dry_run = not self.dry_run
        estado = "ACTIVADO (no se ejecuta nada)" if self.dry_run else "DESACTIVADO"
        self.notify(f"Dry-run: {estado}")
        self.sub_title = (
            f"{self.cfg.dominio} · {self.cfg.red}"
            f"{' · DRY-RUN' if self.dry_run else ''}"
            f"{' · SIN ROOT' if os.geteuid() != 0 else ''}"
        )


def lanzar_tui(cfg: Config) -> None:
    aplicar_config(cfg, cargar_config())
    ServidoresApp(cfg).run()


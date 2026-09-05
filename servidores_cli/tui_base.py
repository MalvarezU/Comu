import threading

from rich.text import Text
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import RichLog

from .commands import dhcp, dns, mail, red, web
from .runner import Contexto, Runner

ESTILOS = {
    "cmd": "cyan",
    "ok": "green",
    "warn": "yellow",
    "error": "red",
    "info": "white",
    "dry": "magenta",
    "salida": "white",
    "detalle": "dim",
}
PREFIJOS = {"cmd": "$ ", "ok": "[OK] ", "warn": "[!] ", "error": "[X] ", "info": ":: "}


class Bitacora(RichLog):
    def __init__(self, **kwargs):
        super().__init__(max_lines=1000, **kwargs)

    def escribir(self, texto, nivel="salida"):
        estilo = ESTILOS.get(nivel, "white")
        prefijo = PREFIJOS.get(nivel, "")
        self.write(Text(prefijo + str(texto), style=estilo))


SERVICIOS = {
    "dns": {
        "titulo": "DNS - Bind9",
        "intro": (
            "[b]Servidor de Nombres de Dominio[/] - UDP 53 (TCP para transferencias de zona)\n"
            "Traduce nombres (www.{dominio}) a IPs y viceversa (PTR).\n"
            "Se generan: forwarders, zona directa e inversa para {dominio}."
        ),
        "pasos": (
            ("Instalar bind9 + dnsutils", dns._instalar),
            ("Configurar zonas y forwarders", dns._configurar),
            ("Reiniciar bind9", dns._iniciar),
        ),
        "extras": (
            ("Estado del servicio", dns._estado),
            ("Probar con dig (A, PTR, MX, NS)", dns._probar),
        ),
    },
    "dhcp": {
        "titulo": "DHCP - isc-dhcp-server",
        "intro": (
            "[b]Dynamic Host Configuration Protocol[/] - UDP 67 (servidor) / 68 (cliente)\n"
            "Flujo: Discover - Offer - Request - ACK.\n"
            "Entrega IPs del rango {rango} a los nodos de la red."
        ),
        "pasos": (
            ("Instalar isc-dhcp-server", dhcp._instalar),
            ("Configurar subred y rango", dhcp._configurar),
            ("Reiniciar el servicio", dhcp._iniciar),
        ),
        "extras": (
            ("Estado del servicio", dhcp._estado),
            ("Probar (activo + puerto 67/UDP)", dhcp._probar),
            ("Renovar IP de ESTA máquina (cliente)", lambda ctx: dhcp._renovar(ctx, confirmar=False)),
        ),
    },
    "correo": {
        "titulo": "Correo - Postfix + Dovecot",
        "intro": (
            "[b]Correo electrónico[/] - SMTP TCP 25 (envío) | POP3 110 / IMAP 143 (lectura)\n"
            "MTA: Postfix. Acceso a buzones: Dovecot (imap + pop3).\n"
            "Crea los usuarios {u1} y {u2} para probar el flujo completo."
        ),
        "pasos": (
            ("Instalar Postfix + Dovecot + mailx", mail._instalar),
            ("Configurar hosts, protocolos y dominio", mail._configurar),
            ("Crear usuarios de correo", lambda ctx: mail._usuarios(ctx, mail.USUARIO1, mail.USUARIO2, mail.CLAVE)),
            ("Reiniciar postfix y dovecot", mail._iniciar),
        ),
        "extras": (
            ("Estado de los servicios", mail._estado),
            ("Probar: enviar SMTP y leer IMAP", lambda ctx: mail._probar(ctx, "localhost", mail.USUARIO1, mail.USUARIO2, mail.CLAVE)),
        ),
    },
    "web": {
        "titulo": "Web - Apache2",
        "intro": (
            "[b]Servidor Web del lab CL_03[/] - HTTP TCP 80\n"
            "Publica una página inicial en /var/www/html para generar tráfico HTTP\n"
            "y estudiarlo con Wireshark."
        ),
        "pasos": (
            ("Instalar Apache2", web._instalar),
            ("Escribir página inicial", web._configurar),
            ("Reiniciar Apache2", web._iniciar),
        ),
        "extras": (
            ("Estado del servicio", web._estado),
            ("Probar peticion HTTP (localhost)", lambda ctx: web._probar(ctx, "localhost")),
        ),
    },
}


PASOS_DEPLOY = (
    ("Configurar red (IP estática + gateway)", red._configurar),
    ("DNS: instalar", dns._instalar),
    ("DNS: configurar zonas", dns._configurar),
    ("DNS: reiniciar", dns._iniciar),
    ("DHCP: instalar", dhcp._instalar),
    ("DHCP: configurar subred", dhcp._configurar),
    ("DHCP: reiniciar", dhcp._iniciar),
    ("Correo: instalar", mail._instalar),
    ("Correo: configurar", mail._configurar),
    ("Correo: crear usuarios", lambda ctx: mail._usuarios(ctx, mail.USUARIO1, mail.USUARIO2, mail.CLAVE)),
    ("Correo: reiniciar", mail._iniciar),
    ("Web: instalar Apache2", web._instalar),
    ("Web: página inicial", web._configurar),
    ("Web: reiniciar", web._iniciar),
    ("Prueba DNS (dig)", dns._probar),
    ("Prueba DHCP (activo + 67/UDP)", dhcp._probar),
    ("Prueba de correo (SMTP + IMAP)", lambda ctx: mail._probar(ctx, "localhost", mail.USUARIO1, mail.USUARIO2, mail.CLAVE)),
    ("Prueba web (HTTP)", lambda ctx: web._probar(ctx, "localhost")),
)


CSS = """
Screen { layout: vertical; }
#principal { height: 1fr; }
#panel_info { width: 1fr; border: solid $primary; padding: 0 1; }
#menu { width: 34; border: solid $accent; padding: 0 1; }
#pasos_col { width: 1fr; border: solid $primary; padding: 0 1; }
#extras_col { width: 44; border: solid $accent; padding: 0 1; }
#rol { height: auto; padding: 0 1; border: solid $success; margin-bottom: 0; }
#intro, #intro_dep { height: auto; padding: 1; border: solid $secondary; margin-bottom: 1; }
#topologia { height: auto; max-height: 10; margin: 0; }
#leyenda { height: auto; padding: 0 1; }
#titulo { text-style: bold; height: auto; margin-bottom: 0; }
#menu Label, #extras_col Label { margin: 1 0; }
Button { width: 100%; margin-bottom: 1; }
Bitacora { height: 20%; border: solid $accent; margin-top: 1; }
#lista_pasos { width: 1fr; border: solid $primary; padding: 0 1; }
#lista_pasos Static { height: auto; padding: 0 1; }
#form { width: 1fr; padding: 0 1; }
#form Input { margin-bottom: 1; }
#form Label { margin: 1 0 0 0; }
"""


class PantallaConBitacora(Screen):
    BINDINGS = [Binding("l", "limpiar", "Limpiar log")]

    def _salida(self, bitacora):
        app = self.app

        def on_line(texto, nivel):
            if threading.current_thread() is threading.main_thread():
                bitacora.escribir(texto, nivel)
            else:
                app.call_from_thread(bitacora.escribir, texto, nivel)

        return on_line

    def _hilo(self):
        app = self.app
        bitacora = self.query_one("#log", Bitacora)
        return bitacora, self._salida(bitacora)

    def action_limpiar(self) -> None:
        self.query_one("#log", Bitacora).clear()

    def ejecutar(self, etiqueta, funcion, *args, **kwargs):
        app = self.app
        bitacora, on_line = self._hilo()
        bitacora.escribir(f"--- {etiqueta} ---", "info")

        def tarea():
            ctx = Contexto(cfg=app.cfg, run=Runner(dry_run=app.dry_run, on_line=on_line))
            try:
                funcion(ctx, *args, **kwargs)
                app.call_from_thread(bitacora.escribir, f"[{etiqueta}] completado", "ok")
            except Exception as e:
                app.call_from_thread(bitacora.escribir, str(e) or repr(e), "error")

        self.run_worker(tarea, thread=True, exclusive=True)

    def secuencia(self, titulo, pasos, marcar=None):
        app = self.app
        bitacora, on_line = self._hilo()

        def tarea():
            ctx = Contexto(cfg=app.cfg, run=Runner(dry_run=app.dry_run, on_line=on_line))
            total = len(pasos)
            ok_n = 0
            fallo_n = 0
            abortado = False
            for i, (etiqueta, funcion) in enumerate(pasos, 1):
                if marcar is not None:
                    app.call_from_thread(marcar, i - 1, "curso")
                app.call_from_thread(bitacora.escribir, f"--- Paso {i}/{total}: {etiqueta} ---", "info")
                try:
                    resultado = funcion(ctx)
                except Exception as e:
                    if marcar is not None:
                        app.call_from_thread(marcar, i - 1, "error")
                    app.call_from_thread(bitacora.escribir, f"Detenido en el paso {i}: {e}", "error")
                    abortado = True
                    break
                if marcar is not None:
                    app.call_from_thread(marcar, i - 1, "hecho" if resultado is not False else "fallo")
                if resultado is False:
                    fallo_n += 1
                    app.call_from_thread(bitacora.escribir, f"El paso {i} reportó fallos (se continúa)", "warn")
                else:
                    ok_n += 1
            resumen = f"{titulo}: Resumen: {ok_n} OK, {fallo_n} con fallos"
            if abortado:
                resumen += " (abortado)"
            app.call_from_thread(
                bitacora.escribir, resumen, "ok" if fallo_n == 0 and not abortado else "warn"
            )

        self.run_worker(tarea, thread=True, exclusive=True)

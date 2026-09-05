import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime

import click

from .config import Config


@dataclass
class Contexto:
    cfg: Config
    run: "Runner"


class Runner:
    def __init__(self, dry_run: bool = False, on_line=None):
        self.dry_run = dry_run
        self.on_line = on_line

    def _texto(self, cmd) -> str:
        return cmd if isinstance(cmd, str) else " ".join(cmd)

    def _decir(self, texto: str, nivel: str = "info") -> None:
        if self.on_line is not None:
            self.on_line(texto, nivel)
            return
        prefijo = {"ok": "[OK] ", "warn": "[!] ", "error": "[X] ", "info": ":: "}.get(nivel, "")
        color = {"ok": "green", "warn": "yellow", "error": "red", "info": "cyan", "cmd": "cyan", "dry": "magenta"}.get(
            nivel, None
        )
        click.secho(f"{prefijo}{texto}", fg=color, err=(nivel == "error"), dim=(nivel == "detalle"))

    def _cmd(self, cmd) -> None:
        self._decir(f"$ {self._texto(cmd)}", "cmd")

    def linea(self, texto: str) -> None:
        self._decir(str(texto), "salida")

    def detalle(self, texto: str) -> None:
        self._decir(str(texto), "detalle")

    def dry(self, msg: str) -> None:
        self._decir(msg, "dry")

    def ok(self, msg: str) -> None:
        self._decir(msg, "ok")

    def info(self, msg: str) -> None:
        self._decir(msg, "info")

    def warn(self, msg: str) -> None:
        self._decir(msg, "warn")

    def error(self, msg: str) -> None:
        self._decir(msg, "error")

    def check_root(self) -> None:
        if self.dry_run:
            self._decir("[dry-run] se omite la verificación de root", "dry")
            return
        if os.geteuid() != 0:
            raise click.ClickException(
                "Este comando requiere permisos de root. Ejecute con: sudo servidores ..."
            )

    def _env(self) -> dict:
        env = dict(os.environ)
        env.setdefault("DEBIAN_FRONTEND", "noninteractive")
        return env

    def _ejecutar_en_hilo(self, cmd, shell: bool = False) -> subprocess.CompletedProcess:
        try:
            proc = subprocess.Popen(
                cmd,
                shell=shell,
                env=self._env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            raise click.ClickException(f"Comando no encontrado: {self._texto(cmd)}")
        salida = []
        for linea in proc.stdout:
            salida.append(linea)
            self.on_line(linea.rstrip("\n"), "salida")
        proc.wait()
        return subprocess.CompletedProcess(cmd, proc.returncode, "".join(salida), "")

    def run(self, cmd, check: bool = False, timeout: float = None) -> subprocess.CompletedProcess:
        self._cmd(cmd)
        if self.dry_run:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        try:
            if self.on_line is not None:
                res = self._ejecutar_en_hilo(cmd)
            else:
                res = subprocess.run(cmd, env=self._env(), text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise click.ClickException(f"Tiempo agotado: {self._texto(cmd)}")
        except FileNotFoundError:
            raise click.ClickException(f"Comando no encontrado: {self._texto(cmd)}")
        if check and res.returncode != 0:
            raise click.ClickException(
                f"Falló (rc={res.returncode}): {self._texto(cmd)}"
            )
        return res

    def run_shell(self, cmd: str, check: bool = False, timeout: float = None) -> subprocess.CompletedProcess:
        self._cmd(cmd)
        if self.dry_run:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        try:
            if self.on_line is not None:
                res = self._ejecutar_en_hilo(cmd, shell=True)
            else:
                res = subprocess.run(cmd, shell=True, env=self._env(), text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise click.ClickException(f"Tiempo agotado: {cmd}")
        if check and res.returncode != 0:
            raise click.ClickException(f"Falló (rc={res.returncode}): {cmd}")
        return res

    def consultar(self, cmd, timeout: float = 60) -> subprocess.CompletedProcess:
        self._cmd(cmd)
        if self.dry_run:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        try:
            return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess(cmd, 127, "", "error al ejecutar el comando")

    def escribir(self, ruta: str, contenido: str) -> None:
        if self.dry_run:
            self._decir(f"[dry-run] escribiría {ruta}:", "dry")
            self._decir(contenido, "salida")
            return
        if os.path.exists(ruta):
            marca = datetime.now().strftime("%Y%m%d%H%M%S")
            respaldo = f"{ruta}.bak-{marca}"
            shutil.copy2(ruta, respaldo)
            self._decir(f"[respaldo] {ruta} -> {respaldo}", "warn")
        carpeta = os.path.dirname(ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        self._decir(f"[escrito] {ruta}", "ok")

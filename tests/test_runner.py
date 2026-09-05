import subprocess

import pytest

from servidores_cli.runner import Contexto, Runner


class TestDryRun:
    def test_run_no_ejecuta_nada(self):
        run = Runner(dry_run=True)
        res = run.run(["comando-que-no-existe", "x"], check=True)
        assert res.returncode == 0

    def test_run_shell_no_ejecuta_nada(self):
        run = Runner(dry_run=True)
        assert run.run_shell("salir 1", check=True).returncode == 0

    def test_escribir_no_toca_disco(self, tmp_path):
        run = Runner(dry_run=True)
        ruta = str(tmp_path / "archivo.conf")
        run.escribir(ruta, "contenido")
        import os

        assert not os.path.exists(ruta)

    def test_consultar_retorna_fallo(self):
        run = Runner(dry_run=True)
        assert run.consultar(["dig", "x"]).returncode == 1

    def test_check_root_se_omite(self):
        Runner(dry_run=True).check_root()  # no debe lanzar


class TestReal:
    def test_run_echo(self):
        run = Runner()
        res = run.run(["echo", "hola"])
        assert res.returncode == 0

    def test_run_check_falla(self):
        run = Runner()
        with pytest.raises(Exception, match="rc=1"):
            run.run(["false"], check=True)

    def test_comando_inexistente(self):
        run = Runner()
        with pytest.raises(Exception, match="Comando no encontrado"):
            run.run(["no-existe-12345"])

    def test_on_line_recibe_salida(self):
        lineas = []
        run = Runner(on_line=lambda texto, nivel: lineas.append((texto, nivel)))
        run.run(["echo", "hola-mundo"])
        assert ("hola-mundo", "salida") in lineas

    def test_on_line_run_check(self):
        lineas = []
        run = Runner(on_line=lambda texto, nivel: lineas.append((texto, nivel)))
        with pytest.raises(Exception, match="rc=1"):
            run.run(["sh", "-c", "echo salida; exit 1"], check=True)
        assert ("salida", "salida") in lineas


class TestTexto:
    def test_str(self):
        assert Runner()._texto("echo hola") == "echo hola"

    def test_lista(self):
        assert Runner()._texto(["echo", "hola"]) == "echo hola"


class TestContexto:
    def test_campos(self):
        from servidores_cli.config import Config

        cfg = Config()
        ctx = Contexto(cfg=cfg, run=Runner())
        assert ctx.cfg is cfg
        assert isinstance(ctx.run, Runner)


class TestEscribir:
    def test_escribe_y_respalda(self, tmp_path):
        run = Runner()
        ruta = tmp_path / "conf.txt"
        ruta.write_text("original", encoding="utf-8")
        run.escribir(str(ruta), "nuevo")
        assert ruta.read_text(encoding="utf-8") == "nuevo"
        respaldos = list(tmp_path.glob("conf.txt.bak-*"))
        assert len(respaldos) == 1
        assert respaldos[0].read_text(encoding="utf-8") == "original"

    def test_crea_carpetas(self, tmp_path):
        run = Runner()
        ruta = tmp_path / "a" / "b" / "conf.txt"
        run.escribir(str(ruta), "x")
        assert ruta.read_text(encoding="utf-8") == "x"

"""Tests del instalador: configs de las apps en carpetas temporales, nunca las reales."""

import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from ucursos_mcp import instalador, launcher


def test_codex_crea_config_y_es_idempotente(tmp_path):
    ruta = tmp_path / ".codex" / "config.toml"
    for _ in range(2):
        r = instalador.instalar_codex(r"C:\Users\ana\ucursos-mcp.exe", [], ruta)
        assert r.ok
    datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    assert datos["mcp_servers"]["ucursos"]["command"] == r"C:\Users\ana\ucursos-mcp.exe"
    assert ruta.read_text(encoding="utf-8").count("[mcp_servers.ucursos]") == 1


def test_codex_conserva_el_resto_y_actualiza_la_ruta(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text(
        'model = "o3"\n\n[mcp_servers.otro]\ncommand = "x"\n\n'
        '[mcp_servers.ucursos]\ncommand = "viejo"\n\n[tui]\ntheme = "dark"\n',
        encoding="utf-8",
    )
    assert instalador.instalar_codex("nuevo", ["-m", "ucursos_mcp"], ruta).ok
    datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    assert datos["model"] == "o3"
    assert datos["mcp_servers"]["otro"] == {"command": "x"}
    assert datos["mcp_servers"]["ucursos"] == {"command": "nuevo", "args": ["-m", "ucursos_mcp"]}
    assert datos["tui"] == {"theme": "dark"}
    assert (tmp_path / "config.toml.ucursos.bak").exists()


def test_codex_no_toca_un_toml_roto(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text("esto = [no es toml", encoding="utf-8")
    assert not instalador.instalar_codex("x", [], ruta).ok
    assert ruta.read_text(encoding="utf-8") == "esto = [no es toml"


def test_desinstalar_codex_quita_solo_lo_nuestro(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text('[mcp_servers.otro]\ncommand = "x"\n', encoding="utf-8")
    instalador.instalar_codex("y", [], ruta)
    assert instalador.desinstalar_codex(ruta).ok
    assert tomllib.loads(ruta.read_text(encoding="utf-8")) == {"mcp_servers": {"otro": {"command": "x"}}}


def test_json_solo_si_la_app_esta_instalada(tmp_path):
    assert instalador._editar_json("Cursor", tmp_path / "no_existe" / "mcp.json", "c", [], False) is None


def test_json_agrega_y_quita(tmp_path):
    ruta = tmp_path / "mcp.json"
    ruta.write_text(json.dumps({"mcpServers": {"otro": {"command": "x"}}, "k": 1}), encoding="utf-8")
    assert instalador._editar_json("Cursor", ruta, "c", ["a"], quitar=False).ok
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["mcpServers"]["ucursos"] == {"command": "c", "args": ["a"]}
    assert datos["mcpServers"]["otro"] == {"command": "x"} and datos["k"] == 1
    assert instalador._editar_json("Cursor", ruta, "", [], quitar=True).ok
    assert "ucursos" not in json.loads(ruta.read_text(encoding="utf-8"))["mcpServers"]


def test_json_formato_inesperado_no_se_toca(tmp_path):
    ruta = tmp_path / "mcp.json"
    ruta.write_text("[1, 2]", encoding="utf-8")
    assert not instalador._editar_json("Cursor", ruta, "c", [], quitar=False).ok
    assert ruta.read_text(encoding="utf-8") == "[1, 2]"


def test_launcher_sin_args_desde_codigo_fuente_arranca_el_server(monkeypatch):
    llamado = []
    monkeypatch.setattr("ucursos_mcp.server.main", lambda: llamado.append(True))
    launcher.main([])
    assert llamado


def test_launcher_doble_clic_instala(monkeypatch, capsys):
    monkeypatch.setattr(instalador, "empaquetado", lambda: True)
    monkeypatch.setattr("ucursos_mcp.ventana.elegir", lambda d: ["chatgpt"])
    monkeypatch.setattr(instalador, "instalar", lambda ids=None: [instalador.Resultado("X", True, "ok")])
    monkeypatch.setattr(launcher, "_pausar", lambda: None)
    monkeypatch.setattr("sys.stdin", type("T", (), {"isatty": lambda self: True})())
    with pytest.raises(SystemExit) as salida:
        launcher.main([])
    assert salida.value.code == 0
    salida = capsys.readouterr().out
    assert "Qué sigue" in salida and "ventana de U-Cursos" in salida


def test_launcher_doble_clic_ofrece_iniciar_sesion(monkeypatch, capsys):
    monkeypatch.setattr(instalador, "empaquetado", lambda: True)
    monkeypatch.setattr("ucursos_mcp.ventana.elegir", lambda d: ["chatgpt"])
    monkeypatch.setattr(instalador, "instalar", lambda ids=None: [instalador.Resultado("X", True, "ok")])
    monkeypatch.setattr(launcher, "_pausar", lambda: None)
    monkeypatch.setattr("ucursos_mcp.ventana.ofrecer_login", lambda: True)
    monkeypatch.setattr(launcher.login_ventana, "disponible", lambda: True)
    monkeypatch.setattr(launcher.login_ventana, "lanzar", lambda: object())
    monkeypatch.setattr(launcher.login_ventana, "esperar", lambda proc, seg: launcher.login_ventana.SALIDA_OK)
    monkeypatch.setattr("sys.stdin", type("T", (), {"isatty": lambda self: True})())
    with pytest.raises(SystemExit):
        launcher.main([])
    assert "ya quedó guardada" in capsys.readouterr().out


def test_launcher_ventana_login_sale_con_el_codigo_de_la_ventana(monkeypatch):
    monkeypatch.setattr(launcher.login_ventana, "correr", lambda: 4)
    with pytest.raises(SystemExit) as salida:
        launcher.main(["ventana-login"])
    assert salida.value.code == 4


@pytest.fixture
def casa(tmp_path, monkeypatch):
    """HOME falso: ninguna app instalada salvo lo que cada test cree."""
    for var in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(var, str(tmp_path))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return tmp_path


def test_instalar_sin_ids_usa_las_detectadas(casa):
    (casa / ".cursor").mkdir()
    r = instalador.instalar(copiar=False)
    assert {x.app for x in r} == {"ChatGPT de escritorio / Codex", "Cursor"}  # Claude no esta


def test_instalar_con_ids_respeta_la_eleccion_y_crea_la_config(casa):
    r = instalador.instalar(["claude"], copiar=False)
    assert [x.app for x in r] == ["Claude Desktop"] and r[0].ok
    assert not (casa / ".codex").exists()
    assert "ucursos" in json.loads(instalador.ruta_claude_desktop().read_text(encoding="utf-8"))["mcpServers"]


def _exe_falso(tmp_path, contenido):
    exe = tmp_path / "origen" / "nuevo.exe"
    exe.parent.mkdir(exist_ok=True)
    exe.write_bytes(contenido)
    return exe


def test_instalar_actualiza_la_version_anterior(casa, monkeypatch):
    destino = instalador.carpeta_instalacion() / instalador.EXE
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b"viejo")
    (destino.parent / "VERSION").write_text("0.7.0")
    monkeypatch.setattr(sys, "executable", str(_exe_falso(casa, b"nuevo")))
    monkeypatch.setattr(instalador, "version_actual", lambda: "0.8.0")
    r = instalador.instalar(["claude"], copiar=True)
    assert r[0].app == "Programa" and "actualizado de la versión 0.7.0 a la 0.8.0" in r[0].detalle
    assert destino.read_bytes() == b"nuevo"
    assert (destino.parent / "VERSION").read_text() == "0.8.0"


def test_instalar_con_programa_en_uso_lo_aparta_y_pone_el_nuevo(casa, monkeypatch):
    """En Windows el .exe en uso no se puede sobrescribir, pero sí renombrar."""
    destino = instalador.carpeta_instalacion() / instalador.EXE
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b"viejo")
    monkeypatch.setattr(sys, "executable", str(_exe_falso(casa, b"nuevo")))
    copia_real = shutil.copy2
    intentos = []

    def copia_bloqueada(origen, dest, *a, **k):
        if Path(dest) == destino and not intentos:
            intentos.append(1)  # el primer intento choca con el programa en uso
            raise PermissionError("en uso")
        return copia_real(origen, dest, *a, **k)

    monkeypatch.setattr(shutil, "copy2", copia_bloqueada)
    r = instalador.instalar(["claude"], copiar=True)
    assert r[0].ok and "anterior" in r[0].detalle  # instalación sin archivo VERSION
    assert destino.read_bytes() == b"nuevo"
    assert destino.with_name(destino.name + ".viejo").read_bytes() == b"viejo"


def test_primera_instalacion_lo_dice(casa, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(_exe_falso(casa, b"nuevo")))
    r = instalador.instalar(["claude"], copiar=True)
    assert "instalado" in r[0].detalle and "actualizado" not in r[0].detalle

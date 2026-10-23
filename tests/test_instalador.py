"""Tests del instalador: configs de las apps en carpetas temporales, nunca las reales."""

import json
import tomllib

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
    monkeypatch.setattr(instalador, "instalar", lambda: [instalador.Resultado("X", True, "ok")])
    monkeypatch.setattr(launcher, "_pausar", lambda: None)
    monkeypatch.setattr("sys.stdin", type("T", (), {"isatty": lambda self: True})())
    with pytest.raises(SystemExit) as salida:
        launcher.main([])
    assert salida.value.code == 0
    assert "Siguiente paso" in capsys.readouterr().out

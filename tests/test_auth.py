"""Tests del login por importación de cookies, con un browser_cookie3 falso."""

import json
import sys
import types
from http.cookiejar import Cookie

import pytest

from ucursos_mcp import auth


def _cookie(name, value, domain):
    return Cookie(0, name, value, None, False, domain, True, domain.startswith("."),
                  "/", True, False, None, False, None, None, {})


def _fake_bc3(mapa):
    """Módulo browser_cookie3 falso: mapa = {navegador: {dominio: [Cookie, ...]}}."""
    mod = types.ModuleType("browser_cookie3")
    for nav in ("edge", "chrome", "brave", "vivaldi", "opera", "chromium", "firefox"):
        def fn(domain_name="", _nav=nav):
            if _nav not in mapa:
                raise RuntimeError(f"{_nav} no instalado")
            return [c for c in mapa[_nav].get(domain_name, [])]
        setattr(mod, nav, fn)
    return mod


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "SESSION_PATH", tmp_path / "sesion.json")
    monkeypatch.setattr(auth, "LOGIN_LOG", tmp_path / "login.log")
    monkeypatch.delenv("UCURSOS_BROWSER", raising=False)
    return tmp_path


def _instala(mapa, monkeypatch):
    monkeypatch.setitem(sys.modules, "browser_cookie3", _fake_bc3(mapa))


def test_importa_cookies_del_navegador(entorno, monkeypatch):
    _instala({"edge": {"u-cursos.cl": [_cookie("sesn", "abc", "www.u-cursos.cl")],
                        "uchile.cl": [_cookie("oidc", "xyz", ".uchile.cl")]}}, monkeypatch)
    n = auth.importar_sesion(entorno / "sesion.json")
    assert n == 2
    estado = json.loads((entorno / "sesion.json").read_text())
    nombres = {c["name"] for c in estado["cookies"]}
    assert nombres == {"sesn", "oidc"}


def test_prefiere_el_primer_navegador_con_cookies(entorno, monkeypatch):
    # Edge no tiene cookies de U-Cursos; Chrome sí. Debe tomar las de Chrome.
    _instala({"edge": {}, "chrome": {"u-cursos.cl": [_cookie("sesn", "deChrome", "www.u-cursos.cl")]}}, monkeypatch)
    auth.importar_sesion(entorno / "sesion.json")
    estado = json.loads((entorno / "sesion.json").read_text())
    assert estado["cookies"][0]["value"] == "deChrome"


def test_sin_cookies_de_ucursos_avisa(entorno, monkeypatch):
    _instala({"firefox": {"u-cursos.cl": [], "uchile.cl": []}}, monkeypatch)
    with pytest.raises(auth.LoginError, match="No encontré cookies"):
        auth.importar_sesion(entorno / "sesion.json")


def test_sin_navegadores_legibles_avisa(entorno, monkeypatch):
    _instala({}, monkeypatch)  # ningún navegador instalado
    with pytest.raises(auth.LoginError, match="ningún navegador"):
        auth.importar_sesion(entorno / "sesion.json")


def test_variable_fuerza_un_navegador(entorno, monkeypatch):
    monkeypatch.setenv("UCURSOS_BROWSER", "firefox")
    _instala({"edge": {"u-cursos.cl": [_cookie("noDebe", "edge", "www.u-cursos.cl")]},
              "firefox": {"u-cursos.cl": [_cookie("si", "firefox", "www.u-cursos.cl")]}}, monkeypatch)
    auth.importar_sesion(entorno / "sesion.json")
    estado = json.loads((entorno / "sesion.json").read_text())
    assert [c["name"] for c in estado["cookies"]] == ["si"]

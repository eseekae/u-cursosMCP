"""Tests del login por importación de cookies, con perfiles falsos y un browser_cookie3 falso."""

import json
import sqlite3
import sys
import time
import types
from http.cookiejar import Cookie

import pytest

from ucursos_mcp import auth, navegadores
from ucursos_mcp.navegadores import Perfil


def _cookie(name, value, domain):
    return Cookie(0, name, value, None, False, domain, True, domain.startswith("."),
                  "/", True, False, None, False, None, None, {})


def _fake_bc3(por_archivo, errores=None):
    """browser_cookie3 falso: por_archivo = {ruta_cookies: [Cookie, ...]}, errores = {ruta: Exception}."""
    mod = types.ModuleType("browser_cookie3")
    for nav in navegadores.NAVEGADORES:
        def fn(cookie_file=None, domain_name="", key_file=None):
            if errores and cookie_file in errores:
                raise errores[cookie_file]
            return [c for c in por_archivo.get(cookie_file, []) if domain_name in c.domain]
        setattr(mod, nav, fn)
    return mod


def _perfil_chromium(tmp_path, nav="edge", nombre="Default"):
    carpeta = tmp_path / nav / nombre
    (carpeta / "Network").mkdir(parents=True)
    archivo = carpeta / "Network" / "Cookies"
    archivo.write_bytes(b"")
    return Perfil(nav, nombre, carpeta, archivo)


def _perfil_firefox(tmp_path, nav="zen", nombre="Default (release)", cookies=(), wal_abierto=False):
    """Perfil de Firefox/Zen con un cookies.sqlite real.

    Con wal_abierto, las cookies quedan solo en cookies.sqlite-wal (como pasa justo después
    de iniciar sesión) y se devuelve la conexión para mantenerlo así durante el test.
    """
    carpeta = tmp_path / nav / nombre
    carpeta.mkdir(parents=True)
    archivo = carpeta / "cookies.sqlite"
    con = sqlite3.connect(archivo)
    con.execute("CREATE TABLE moz_cookies (host, path, isSecure, expiry, name, value, lastAccessed, originAttributes)")
    con.commit()
    if wal_abierto:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
    for host, name, value in cookies:
        con.execute("INSERT INTO moz_cookies VALUES (?, '/', 1, ?, ?, ?, 1, '')",
                    (host, int(time.time()) + 3600, name, value))
    con.commit()
    perfil = Perfil(nav, nombre, carpeta, archivo)
    if wal_abierto:
        return perfil, con
    con.close()
    return perfil


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "SESSION_PATH", tmp_path / "sesion.json")
    monkeypatch.setattr(auth, "LOGIN_LOG", tmp_path / "login.log")
    monkeypatch.delenv("UCURSOS_BROWSER", raising=False)
    monkeypatch.setattr(navegadores, "por_defecto", lambda: None)
    return tmp_path


def _instala(monkeypatch, perfiles, por_archivo=None, errores=None):
    """perfiles = {navegador: [Perfil, ...]}."""
    monkeypatch.setattr(navegadores, "perfiles", lambda nav, filtro=None: [
        p for p in perfiles.get(nav, []) if not filtro or filtro.lower() in p.nombre.lower()])
    monkeypatch.setitem(sys.modules, "browser_cookie3", _fake_bc3(
        {str(k): v for k, v in (por_archivo or {}).items()},
        {str(k): v for k, v in (errores or {}).items()}))


def _guardado(entorno):
    return json.loads((entorno / "sesion.json").read_text())


def test_importa_cookies_y_recuerda_el_navegador(entorno, monkeypatch):
    edge = _perfil_chromium(entorno)
    _instala(monkeypatch, {"edge": [edge]}, {edge.cookies: [
        _cookie("sesn", "abc", "www.u-cursos.cl"), _cookie("oidc", "xyz", ".uchile.cl")]})
    cand = auth.importar_sesion()
    assert cand.perfil.navegador == "edge"
    estado = _guardado(entorno)
    assert {c["name"] for c in estado["cookies"]} == {"sesn", "oidc"}
    assert estado["origen"] == {"navegador": "edge", "perfil": "Default"}
    assert auth.navegador_guardado() == "edge"


def test_no_se_queda_con_el_primer_navegador_si_u_cursos_lo_rechaza(entorno, monkeypatch):
    # Bug reportado: Edge tenía cookies viejas y siempre se importaban esas.
    edge = _perfil_chromium(entorno)
    zen = _perfil_firefox(entorno, cookies=[("www.u-cursos.cl", "sesn", "nueva")])
    _instala(monkeypatch, {"edge": [edge], "zen": [zen]},
             {edge.cookies: [_cookie("sesn", "vieja", "www.u-cursos.cl")]})
    validar = lambda cookies: None if cookies[0]["value"] == "nueva" else "pide login"
    cand = auth.importar_sesion(validar=validar)
    assert cand.perfil.navegador == "zen"
    assert _guardado(entorno)["cookies"][0]["value"] == "nueva"


def test_lee_zen_con_las_cookies_que_siguen_en_el_wal(entorno, monkeypatch):
    # Justo después del login, Firefox/Zen tienen las cookies nuevas solo en cookies.sqlite-wal.
    zen, con = _perfil_firefox(entorno, cookies=[("www.u-cursos.cl", "sesn", "recien")], wal_abierto=True)
    try:
        assert (zen.carpeta / "cookies.sqlite-wal").stat().st_size > 0
        _instala(monkeypatch, {"zen": [zen]})
        cand = auth.importar_sesion("zen")
    finally:
        con.close()
    assert [c["value"] for c in cand.cookies] == ["recien"]


def test_navegador_pedido_se_prueba_solo(entorno, monkeypatch):
    edge = _perfil_chromium(entorno)
    zen = _perfil_firefox(entorno, cookies=[("www.u-cursos.cl", "si", "zen")])
    _instala(monkeypatch, {"edge": [edge], "zen": [zen]},
             {edge.cookies: [_cookie("noDebe", "edge", "www.u-cursos.cl")]})
    cand = auth.importar_sesion("Zen Browser")
    assert [c["name"] for c in cand.cookies] == ["si"]


def test_variable_fuerza_un_navegador(entorno, monkeypatch):
    monkeypatch.setenv("UCURSOS_BROWSER", "firefox")
    edge = _perfil_chromium(entorno)
    ff = _perfil_firefox(entorno, nav="firefox", cookies=[("www.u-cursos.cl", "si", "ff")])
    _instala(monkeypatch, {"edge": [edge], "firefox": [ff]},
             {edge.cookies: [_cookie("noDebe", "edge", "www.u-cursos.cl")]})
    cand = auth.importar_sesion()
    assert [c["name"] for c in cand.cookies] == ["si"]


def test_elige_perfil(entorno, monkeypatch):
    p1 = _perfil_firefox(entorno, nav="firefox", nombre="trabajo", cookies=[("www.u-cursos.cl", "a", "1")])
    p2 = _perfil_firefox(entorno, nav="firefox", nombre="uni", cookies=[("www.u-cursos.cl", "b", "2")])
    _instala(monkeypatch, {"firefox": [p1, p2]})
    cand = auth.importar_sesion("firefox", perfil="uni")
    assert cand.perfil.nombre == "uni"


def test_diagnostico_dice_navegador_perfil_y_cookies(entorno, monkeypatch):
    edge = _perfil_chromium(entorno, nombre="Persona 1")
    zen = _perfil_firefox(entorno, cookies=[("www.u-cursos.cl", "sesn", "valorSecreto1"), (".uchile.cl", "oidc", "valorSecreto2")])
    chrome = _perfil_chromium(entorno, nav="chrome")
    _instala(monkeypatch, {"edge": [edge], "zen": [zen], "chrome": [chrome]},
             {chrome.cookies: [_cookie("solo", "u", ".uchile.cl")]},
             errores={edge.cookies: RuntimeError("Unable to get key for cookie decryption")})
    with pytest.raises(auth.LoginError) as e:
        auth.importar_sesion(validar=lambda c: "respondió con la página de inicio de sesión")
    msg = str(e.value)
    assert 'Microsoft Edge (perfil "Persona 1"): no pude descifrar' in msg
    assert 'Zen Browser (perfil "Default (release)"): 2 cookies: 1 de u-cursos.cl (sesn)' in msg
    assert "página de inicio de sesión" in msg
    assert "ninguna de u-cursos.cl" in msg
    assert "Firefox o Zen" in msg
    assert "valorSecreto" not in msg  # nunca muestra valores
    assert (entorno / "login.log").read_text(encoding="utf-8") == msg


def test_navegador_no_instalado_avisa(entorno, monkeypatch):
    _instala(monkeypatch, {})
    with pytest.raises(auth.LoginError, match="Brave: no lo encontré instalado"):
        auth.importar_sesion("brave")


def test_navegador_desconocido():
    with pytest.raises(navegadores.NavegadorDesconocido, match="zen"):
        navegadores.normalizar("netscape")


def test_navegador_preferido_usa_el_guardado(entorno, monkeypatch):
    (entorno / "sesion.json").write_text(json.dumps({"cookies": [], "origen": {"navegador": "zen"}}))
    monkeypatch.setattr(navegadores, "por_defecto", lambda: "edge")
    assert auth.navegador_preferido() == "zen"
    assert auth.navegador_preferido("Opera GX") == "opera_gx"


# ---------------------------------------------------------------- navegadores


def test_perfiles_firefox_lee_profiles_ini(tmp_path):
    base = tmp_path / "zen"
    for d in ("Profiles/abc.Default (release)", "Profiles/xyz.Otro"):
        (base / d).mkdir(parents=True)
        (base / d / "cookies.sqlite").write_bytes(b"")
    (base / "profiles.ini").write_text(
        "[Profile1]\nName=Otro\nIsRelative=1\nPath=Profiles/xyz.Otro\n\n"
        "[Profile0]\nName=Default (release)\nIsRelative=1\nPath=Profiles/abc.Default (release)\n\n"
        "[Install123]\nDefault=Profiles/abc.Default (release)\n",
        encoding="utf-8",
    )
    ps = navegadores._perfiles_firefox("zen", base)
    assert [p.nombre for p in ps] == ["Default (release)", "Otro"]


def test_perfiles_chromium_primero_el_ultimo_usado(tmp_path):
    base = tmp_path / "Edge"
    for d in ("Default", "Profile 1"):
        (base / d / "Network").mkdir(parents=True)
        (base / d / "Network" / "Cookies").write_bytes(b"")
    (base / "Local State").write_text(json.dumps({"profile": {
        "last_used": "Profile 1", "info_cache": {"Profile 1": {"name": "Universidad"}}}}))
    ps = navegadores._perfiles_chromium("edge", base)
    assert [p.nombre for p in ps] == ["Universidad", "Default"]
    assert ps[0].llave == base / "Local State"


@pytest.mark.parametrize("exe, esperado", [
    (r"C:\Program Files\Zen Browser\zen.exe", "zen"),
    (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "edge"),
    (r"C:\Users\a\AppData\Local\Programs\Opera GX\opera.exe", "opera_gx"),
    (r"C:\x\notepad.exe", None),
])
def test_navegador_de_exe(exe, esperado):
    assert navegadores._navegador_de_exe(exe) == esperado


def test_navegador_de_desktop():
    assert navegadores._navegador_de_desktop("app.zen_browser.zen.desktop") == "zen"
    assert navegadores._navegador_de_desktop("google-chrome.desktop") == "chrome"

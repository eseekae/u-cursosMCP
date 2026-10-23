"""Tests del inicio de sesión en ventana, con un pywebview falso (sin abrir nada real)."""

import json
import subprocess
import sys
import types
from http.cookies import SimpleCookie

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from ucursos_mcp import auth, login_ventana, server


def _simple(nombre, valor, dominio="", path="/", expires="", secure=True):
    c = SimpleCookie()
    c[nombre] = valor
    c[nombre]["domain"] = dominio
    c[nombre]["path"] = path
    c[nombre]["expires"] = expires
    if secure:
        c[nombre]["secure"] = True
    return c


def test_a_cookies_filtra_dominios_y_completa_lo_que_falta():
    cookies = login_ventana.a_cookies([
        _simple("PHPSESSID", "abc"),  # sin dominio: es de U-Cursos
        _simple("sl-session", "x", ".uchile.cl", expires="Wed, 21 Oct 2026 07:28:00 GMT"),
        _simple("_ga", "ga", ".google.com"),  # ajena a la sesión
    ])
    por_nombre = {c["name"]: c for c in cookies}
    assert set(por_nombre) == {"PHPSESSID", "sl-session"}
    assert por_nombre["PHPSESSID"]["domain"] == ".u-cursos.cl"
    assert por_nombre["PHPSESSID"]["expires"] == -1  # cookie de sesión
    assert por_nombre["sl-session"]["expires"] > 0
    assert por_nombre["PHPSESSID"]["value"] == "abc"


class _Evento:
    def __init__(self):
        self.manejadores = []

    def __iadd__(self, fn):
        self.manejadores.append(fn)
        return self


class _VentanaFalsa:
    def __init__(self, urls, cookies):
        self.urls, self.cookies = list(urls), cookies
        self.events = types.SimpleNamespace(closed=_Evento())
        self.html = None
        self.destruida = False

    def get_current_url(self):
        return self.urls.pop(0) if len(self.urls) > 1 else self.urls[0]

    def get_cookies(self):
        return self.cookies

    def load_html(self, html):
        self.html = html

    def destroy(self):
        self.destruida = True
        for fn in self.events.closed.manejadores:
            fn()


def _webview_falso(monkeypatch, ventana, cierra_el_usuario=False):
    mod = types.ModuleType("webview")
    mod.create_window = lambda *a, **k: ventana

    def start(func, arg, **kw):
        if cierra_el_usuario:
            ventana.destroy()
        func(arg)

    mod.start = start
    monkeypatch.setitem(sys.modules, "webview", mod)


@pytest.fixture
def rapido(monkeypatch, tmp_path):
    monkeypatch.setattr(login_ventana, "SONDEO_S", 0.01)
    monkeypatch.setattr(login_ventana, "PAUSA_FINAL_S", 0.01)
    monkeypatch.setattr(login_ventana, "PERFIL_VENTANA", tmp_path / "perfil")
    return tmp_path / "sesion.json"


HASH = "a" * 32


def test_guarda_la_sesion_cuando_el_usuario_entra(monkeypatch, rapido):
    ventana = _VentanaFalsa(
        ["https://www.u-cursos.cl/", f"https://www.u-cursos.cl/usuario/{HASH}/mis_canales/"],
        [_simple("PHPSESSID", "abc")],
    )
    _webview_falso(monkeypatch, ventana)
    assert login_ventana.correr(validar=lambda c: None, session_path=rapido) == login_ventana.SALIDA_OK
    guardado = json.loads(rapido.read_text())
    assert guardado["cookies"][0]["name"] == "PHPSESSID"
    assert guardado["origen"]["navegador"] == "ventana"
    assert ventana.destruida and "Ya iniciaste sesión" in ventana.html


def test_no_guarda_si_u_cursos_rechaza_las_cookies(monkeypatch, rapido):
    ventana = _VentanaFalsa([f"https://www.u-cursos.cl/usuario/{HASH}/"], [_simple("PHPSESSID", "mala")])
    _webview_falso(monkeypatch, ventana)
    monkeypatch.setattr(login_ventana, "ESPERA_MAX_S", 0.05)
    codigo = login_ventana.correr(validar=lambda c: "rechazadas", session_path=rapido, timeout_s=0.05)
    assert codigo == login_ventana.SALIDA_TIEMPO
    assert not rapido.exists()


def test_cerrar_la_ventana_sin_entrar(monkeypatch, rapido):
    ventana = _VentanaFalsa(["https://www.u-cursos.cl/"], [])
    _webview_falso(monkeypatch, ventana, cierra_el_usuario=True)
    assert login_ventana.correr(validar=lambda c: None, session_path=rapido) == login_ventana.SALIDA_CERRADA
    assert not rapido.exists()


def test_sin_pywebview_se_usa_el_navegador(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", None)  # import falla
    assert login_ventana.correr(validar=lambda c: None) == login_ventana.SALIDA_NO_DISPONIBLE


def test_si_falla_al_abrir_se_usa_el_navegador(monkeypatch, rapido):
    mod = types.ModuleType("webview")

    def explota(*a, **k):
        raise RuntimeError("sin WebView2")

    mod.create_window = explota
    monkeypatch.setitem(sys.modules, "webview", mod)
    assert login_ventana.correr(validar=lambda c: None, session_path=rapido) == login_ventana.SALIDA_NO_DISPONIBLE


# ---------------------------------------------------------------- tools del server


class _Proceso:
    """Popen falso: `codigo` None = la ventana sigue abierta."""

    def __init__(self, codigo):
        self.codigo = codigo

    def wait(self, timeout=None):
        if self.codigo is None:
            raise subprocess.TimeoutExpired("x", timeout)
        return self.codigo

    def poll(self):
        return self.codigo


@pytest.fixture
def servidor(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_ventana", None)
    monkeypatch.setattr(server, "SESSION_PATH", tmp_path / "sesion.json")
    monkeypatch.setattr(login_ventana, "disponible", lambda: True)
    monkeypatch.setattr(server, "ESPERA_VENTANA_S", 0.01)
    return tmp_path


def test_iniciar_sesion_abre_la_ventana_y_avisa_que_sigue_abierta(servidor, monkeypatch):
    monkeypatch.setattr(login_ventana, "lanzar", lambda: _Proceso(None))
    msg = server.iniciar_sesion()
    assert "ventana" in msg and "estado_sesion" in msg


def test_iniciar_sesion_no_abre_dos_ventanas(servidor, monkeypatch):
    lanzadas = []
    monkeypatch.setattr(login_ventana, "lanzar", lambda: lanzadas.append(1) or _Proceso(None))
    server.iniciar_sesion()
    server.iniciar_sesion()
    assert len(lanzadas) == 1


def test_estado_sesion_confirma_cuando_la_ventana_termina(servidor, monkeypatch):
    monkeypatch.setattr(server, "_ventana", _Proceso(login_ventana.SALIDA_OK))
    assert "Sesión activa" in server.estado_sesion()
    assert server._ventana is None


def test_estado_sesion_sigue_esperando_mientras_la_ventana_esta_abierta(servidor, monkeypatch):
    monkeypatch.setattr(server, "_ventana", _Proceso(None))
    assert "sigue abierta" in server.estado_sesion()


def test_estado_sesion_si_cierra_la_ventana_pide_decidir(servidor, monkeypatch):
    monkeypatch.setattr(server, "_ventana", _Proceso(login_ventana.SALIDA_CERRADA))
    with pytest.raises(ToolError, match="cerró la ventana"):
        server.estado_sesion()


def test_iniciar_sesion_cae_al_navegador_si_la_ventana_no_esta_disponible(servidor, monkeypatch):
    monkeypatch.setattr(login_ventana, "lanzar", lambda: _Proceso(login_ventana.SALIDA_NO_DISPONIBLE))
    monkeypatch.setattr(auth, "navegador_preferido", lambda n=None: "firefox")
    monkeypatch.setattr(auth, "abrir_ucursos", lambda nav: "Firefox")
    msg = server.iniciar_sesion()
    assert "Se abrió U-Cursos en Firefox" in msg and 'estado_sesion(navegador="firefox")' in msg


def test_con_navegador_explicito_no_se_usa_la_ventana(servidor, monkeypatch):
    monkeypatch.setattr(login_ventana, "lanzar", lambda: pytest.fail("no debía abrir la ventana"))
    monkeypatch.setattr(auth, "navegador_preferido", lambda n=None: n)
    monkeypatch.setattr(auth, "abrir_ucursos", lambda nav: "Zen")
    assert "Zen" in server.iniciar_sesion("zen")


def test_estado_sesion_sin_ventana_usa_la_sesion_guardada_si_sirve(servidor, monkeypatch):
    (servidor / "sesion.json").write_text(json.dumps({"cookies": [{"name": "a", "value": "b"}]}))
    monkeypatch.setattr(server, "validar_cookies", lambda c: None)
    monkeypatch.setattr(auth, "importar_sesion", lambda *a, **k: pytest.fail("no debía leer navegadores"))
    assert "Sesión activa" in server.estado_sesion()

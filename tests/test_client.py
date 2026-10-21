"""Tests de validar_cookies: cómo se distingue una sesión buena de una rechazada, sin red."""

import httpx
import pytest

from ucursos_mcp import client

HASH = "0123456789abcdef0123456789abcdef"
COOKIES = [{"name": "sesn", "value": "x", "domain": "www.u-cursos.cl", "path": "/"}]


@pytest.fixture
def servidor(monkeypatch):
    """Reemplaza la red por un handler: servidor(handler) instala la respuesta falsa."""
    monkeypatch.setattr(client, "MIN_INTERVAL_S", 0)
    original = httpx.Client

    def instala(handler):
        monkeypatch.setattr(client.httpx, "Client",
                            lambda **kw: original(transport=httpx.MockTransport(handler), **kw))

    return instala


def _html(cuerpo):
    return httpx.Response(200, html=cuerpo, headers={"content-type": "text/html; charset=iso-8859-1"})


def test_sesion_valida_por_redireccion_a_usuario(servidor):
    def handler(req):
        if req.url.path == "/":
            return httpx.Response(302, headers={"location": f"/usuario/{HASH}/"})
        return _html("<html>hola</html>")

    servidor(handler)
    assert client.validar_cookies(COOKIES) is None


def test_sesion_valida_por_link_en_portada(servidor):
    servidor(lambda req: _html(f'<a href="/usuario/{HASH}/mis_canales/">Mis cursos</a>'))
    assert client.validar_cookies(COOKIES) is None


def test_boton_login_es_rechazo(servidor):
    servidor(lambda req: _html('<a id="boton_login">Ingresar</a>'))
    assert "inicio de sesión" in client.validar_cookies(COOKIES)


def test_redireccion_a_cuenta_uchile_es_rechazo(servidor):
    def handler(req):
        if req.url.host == "www.u-cursos.cl":
            return httpx.Response(302, headers={"location": "https://oauth2.uchile.cl/authorize"})
        return _html("<html>login</html>")

    servidor(handler)
    assert "inicio de sesión" in client.validar_cookies(COOKIES)


def test_portada_sin_usuario_sugiere_cambio_de_html(servidor):
    servidor(lambda req: _html("<html>portada nueva</html>"))
    assert "arreglar-parser" in client.validar_cookies(COOKIES)


def test_sin_red_lo_dice(servidor):
    def handler(req):
        raise httpx.ConnectError("sin red", request=req)

    servidor(handler)
    assert "no pude conectar" in client.validar_cookies(COOKIES)

"""Tests de la capa MCP: que los errores esperables lleguen legibles a Claude."""

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from ucursos_mcp.client import SessionExpired
from ucursos_mcp.server import errores_legibles


def _falla_con(exc):
    @errores_legibles
    def tool():
        raise exc

    return tool


def test_sesion_expirada_sugiere_iniciar_sesion():
    with pytest.raises(ToolError, match="iniciar_sesion"):
        _falla_con(SessionExpired("La sesión de U-Cursos expiró."))()


@pytest.mark.parametrize("code, texto", [(403, "negó el acceso"), (404, "No existe"), (500, "respondió 500")])
def test_errores_http(code, texto):
    req = httpx.Request("GET", "https://www.u-cursos.cl/ingenieria/2026/2/CC1002/7/notas/")
    exc = httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))
    with pytest.raises(ToolError, match=texto):
        _falla_con(exc)()


class ClienteFalso:
    """Imita a UCursosClient: un curso inscrito y un archivo de texto largo."""

    def home(self):
        return '<a href="https://www.u-cursos.cl/ingenieria/2026/2/MA2001/3/">Cálculo en Varias Variables MA2001-3</a>'

    def get_bytes(self, ruta):
        self.ultima_ruta = ruta
        return ("abcdefghij" * 3).encode(), "apunte.txt"


@pytest.fixture
def falso(monkeypatch):
    from ucursos_mcp import server

    c = ClienteFalso()
    monkeypatch.setattr(server, "client", lambda: c)
    monkeypatch.setattr(server, "_inscritos", None)
    return c


def test_curso_no_inscrito_se_rechaza(falso):
    from ucursos_mcp import server

    assert server.curso_inscrito("/ingenieria/2026/2/MA2001/3/") == "ingenieria/2026/2/MA2001/3"
    with pytest.raises(ToolError, match="no está entre los cursos inscritos"):
        server.curso_inscrito("ingenieria/2026/2/MA2001/1")


@pytest.mark.parametrize("descarga", [
    "https://evil.example.com/ingenieria/2026/2/MA2001/3/x",
    "/ingenieria/2026/2/CC1002/7/material_docente/bajar?id=1",
    "https://www.u-cursos.cl/ingenieria/2026/2/MA2001/1/material_docente/bajar?id=1",
])
def test_descarga_fuera_del_curso_se_rechaza(descarga):
    from ucursos_mcp import server

    with pytest.raises(ToolError):
        server.ruta_descarga("ingenieria/2026/2/MA2001/3", descarga)


def test_descarga_relativa_queda_dentro_del_curso():
    from ucursos_mcp import server

    assert server.ruta_descarga("ingenieria/2026/2/MA2001/3", "bajar?id=9") == "/ingenieria/2026/2/MA2001/3/material_docente/bajar?id=9"


def test_leer_material_por_partes(falso):
    from ucursos_mcp import server

    r = server.leer_material("ingenieria/2026/2/MA2001/3", "bajar?id=1", max_caracteres=12)
    assert (r["texto"], r["quedan"], r["siguiente_desde"]) == ("abcdefghijab", 18, 12)
    r = server.leer_material("ingenieria/2026/2/MA2001/3", "bajar?id=1", desde=24, max_caracteres=12)
    assert (r["texto"], r["quedan"], r["siguiente_desde"]) == ("efghij", 0, None)
    assert falso.ultima_ruta == "/ingenieria/2026/2/MA2001/3/material_docente/bajar?id=1"


def test_conserva_firma_de_la_tool():
    @errores_legibles
    def tool(curso_path: str, limite: int = 10) -> list:
        return [curso_path, limite]

    import inspect

    assert list(inspect.signature(tool).parameters) == ["curso_path", "limite"]
    assert tool("a", limite=3) == ["a", 3]

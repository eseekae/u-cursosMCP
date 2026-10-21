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


def test_conserva_firma_de_la_tool():
    @errores_legibles
    def tool(curso_path: str, limite: int = 10) -> list:
        return [curso_path, limite]

    import inspect

    assert list(inspect.signature(tool).parameters) == ["curso_path", "limite"]
    assert tool("a", limite=3) == ["a", 3]

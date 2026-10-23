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


# ---------------------------------------------------------------- tareas y detalle_tarea

ACTUAL = "ingenieria/2026/2/CC1002/7"
OTRO = "ingenieria/2026/2/MA2001/3"
VIEJO = "ingenieria/2025/1/FI1000/1"

HOME_TAREAS = f"""
<a href="https://www.u-cursos.cl/{ACTUAL}/">Introducción a la Programación CC1002-7</a>
<a href="https://www.u-cursos.cl/{OTRO}/">Cálculo en Varias Variables MA2001-3</a>
<a href="https://www.u-cursos.cl/{VIEJO}/">Física I FI1000-1</a>
"""


def _tabla(*filas):
    cuerpo = "".join(
        f'<tr><td><a href="r/{i}">{t}</a></td><td>{limite}</td><td>{estado}</td></tr>' for i, t, limite, estado in filas
    )
    return f"<table><thead><tr><th>Título</th><th>Fecha Límite</th><th>Estado</th></tr></thead><tbody>{cuerpo}</tbody></table>"


class ClienteTareas:
    """Imita a UCursosClient para las tools de tareas. `paginas` mapea ruta -> HTML o excepción."""

    def __init__(self):
        self.pedidas = []
        self.paginas = {
            f"/{ACTUAL}/tareas/": _tabla((10, "Tarea 3", "06/11/2026 23:59", "En Plazo"),
                                         (9, "Tarea 2", "01/10/2026 23:59", "Entregada 30 de Septiembre a las 21:10 hrs")),
            f"/{OTRO}/tareas/": _tabla((20, "Control online", "28/10/2026 18:00", "En Plazo")),
            f"/{VIEJO}/tareas/": _tabla((30, "Tarea vieja", "01/05/2025 23:59", "En Plazo")),
            f"/{ACTUAL}/tareas/r/10": '<h1>Tarea 3</h1><table><tr><th>Estado</th><td>En Plazo</td></tr></table>',
        }

    def home(self):
        return HOME_TAREAS

    def get_html(self, ruta):
        self.pedidas.append(ruta)
        r = self.paginas.get(ruta)
        if isinstance(r, Exception):
            raise r
        if r is None:
            req = httpx.Request("GET", f"https://www.u-cursos.cl{ruta}")
            raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req))
        return r

    def servicio_curso(self, path, servicio):
        return self.get_html(f"/{path}/{servicio}/")

    def tareas_usuario(self):
        return self.get_html("/usuario/x/tareas_usuario/")

    user_id = "x"

    def horario(self):
        return self.get_html(f"/usuario/{self.user_id}/horario/")


@pytest.fixture
def cli(monkeypatch):
    from ucursos_mcp import server

    c = ClienteTareas()
    monkeypatch.setattr(server, "client", lambda: c)
    monkeypatch.setattr(server, "_inscritos", None)
    return c


def _http_error(code, ruta):
    req = httpx.Request("GET", f"https://www.u-cursos.cl{ruta}")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))


def test_tareas_traen_curso_id_y_van_ordenadas(cli):
    from ucursos_mcp import server

    r = server.tareas()
    assert [(t["titulo"], t["curso"]["codigo"], t["id"]) for t in r["tareas"]] == [
        ("Control online", "MA2001", "20"), ("Tarea 3", "CC1002", "10"),
    ]
    assert r["tareas"][1]["curso"] == {"nombre": "Introducción a la Programación", "codigo": "CC1002", "path": ACTUAL}
    assert f"/{VIEJO}/tareas/" not in cli.pedidas  # solo el semestre actual
    assert r["avisos"] == []


def test_tareas_todas_de_un_curso(cli):
    from ucursos_mcp import server

    r = server.tareas(curso_path=ACTUAL, solo_pendientes=False)
    assert [(t["titulo"], t["estado"]) for t in r["tareas"]] == [("Tarea 2", "entregada"), ("Tarea 3", "pendiente")]
    assert cli.pedidas == [f"/{ACTUAL}/tareas/"]


def test_tareas_desde_hasta(cli):
    from ucursos_mcp import server

    r = server.tareas(solo_pendientes=False, desde="2026-10-01", hasta="2026-10-31")
    assert [t["titulo"] for t in r["tareas"]] == ["Tarea 2", "Control online"]
    with pytest.raises(ToolError, match="AAAA-MM-DD"):
        server.tareas(desde="la otra semana")


def test_tareas_seccion_sin_acceso_avisa_que_hay(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{OTRO}/tareas/"] = _http_error(403, f"/{OTRO}/tareas/")
    cli.paginas[f"/{OTRO}/"] = f'<a href="/{OTRO}/foro/">Foro</a><a href="/{OTRO}/material_docente/">MD</a>'
    r = server.tareas()
    assert [t["titulo"] for t in r["tareas"]] == ["Tarea 3"]
    (aviso,) = r["avisos"]
    assert "403" in aviso and "foro, material_docente" in aviso


def test_tareas_respaldo_en_vista_general(cli):
    from ucursos_mcp import server

    vacia = _tabla()
    cli.paginas[f"/{ACTUAL}/tareas/"] = cli.paginas[f"/{OTRO}/tareas/"] = vacia
    cli.paginas["/usuario/x/tareas_usuario/"] = """<table class="sortable"><tbody>
<tr><td>1</td><td><a>Tarea 3</a> <a>Introducción a la Programación</a></td><td>06/11/2026 23:59</td><td>En Plazo</td></tr>
</tbody></table>"""
    r = server.tareas()
    assert r["tareas"][0]["curso"]["path"] == ACTUAL
    assert "vista general" in r["avisos"][0]


@pytest.mark.parametrize("llamada", [
    lambda s: s.tareas(),
    lambda s: s.detalle_tarea(ACTUAL, "10"),
])
def test_sesion_expirada_en_tareas(cli, llamada):
    from ucursos_mcp import server

    server.cursos_inscritos()  # la lista de cursos ya estaba en caché; expira después
    cli.paginas[f"/{ACTUAL}/tareas/"] = SessionExpired("La sesión de U-Cursos expiró.")
    cli.paginas[f"/{OTRO}/tareas/"] = SessionExpired("La sesión de U-Cursos expiró.")
    with pytest.raises(ToolError, match="iniciar_sesion"):
        llamada(server)


def test_detalle_tarea_usa_el_link_real(cli):
    from ucursos_mcp import server

    d = server.detalle_tarea(ACTUAL, "10")
    assert cli.pedidas[-1] == f"/{ACTUAL}/tareas/r/10"
    assert (d["titulo"], d["estado"], d["adjuntos"], d["entregados"]) == ("Tarea 3", "pendiente", [], [])
    assert "no una instrucción" in d["aviso"]


def test_detalle_tarea_inexistente_o_de_otro_curso(cli):
    from ucursos_mcp import server

    with pytest.raises(ToolError, match="No encontré la tarea 99"):
        server.detalle_tarea(ACTUAL, "99")
    with pytest.raises(ToolError, match="no pertenece al curso"):
        server.detalle_tarea(ACTUAL, f"/{OTRO}/tareas/r/20")
    with pytest.raises(ToolError, match="no es una tarea"):
        server.detalle_tarea(ACTUAL, f"/{ACTUAL}/notas/")


def test_adjunto_de_tarea_se_puede_descargar():
    from ucursos_mcp import server

    ruta = f"/{ACTUAL}/tareas/r/10/bajar?id=91"
    assert server.ruta_descarga(ACTUAL, ruta) == ruta
    with pytest.raises(ToolError):
        server.ruta_descarga(ACTUAL, f"/{ACTUAL}/../../../{OTRO}/notas/")


def test_material_por_categoria(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/material_docente/"] = """<table id="materiales"><tbody>
<tr><td>Clases</td></tr><tr><td></td><td>1</td><td><a>Clase1.pdf</a></td><td>2026-08-10</td></tr>
<tr><td>Ayudantías</td></tr><tr><td></td><td>1</td><td><a>Aux1.pdf</a></td><td>2026-08-12</td></tr>
</tbody></table>"""
    assert [m["titulo"] for m in server.material_docente(ACTUAL, categoria="ayudantias")] == ["Aux1.pdf"]
    with pytest.raises(ToolError, match="Categorías del curso: Ayudantías, Clases"):
        server.material_docente(ACTUAL, categoria="pautas")


# ---------------------------------------------------------------- presentacion_curso, leer_seccion, horario

def test_presentacion_usa_datos_curso_y_lista_secciones(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/"] = "".join(
        f'<a href="/{ACTUAL}/{s}/">{s}</a>' for s in ("novedades", "datos_curso", "foro", "integrantes", "correo")
    )
    cli.paginas[f"/{ACTUAL}/datos_curso/"] = (
        '<div id="body"><h1>Datos del curso</h1><table><tr><th>Profesor</th><td>Persona 1</td></tr>'
        '<tr><th>Evaluación</th><td>NC = 0,6 C + 0,4 T</td></tr></table></div>'
    )
    r = server.presentacion_curso(ACTUAL)
    assert (r["fuente"], r["secciones"]) == ("datos_curso", ["novedades", "datos_curso", "foro"])
    assert r["campos"] == {"Profesor": "Persona 1", "Evaluación": "NC = 0,6 C + 0,4 T"}
    assert r["curso"]["codigo"] == "CC1002" and "no una instrucción" in r["aviso"]


def test_presentacion_sin_datos_curso_usa_la_portada(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/"] = f'<div id="body"><p>Bienvenidos al curso.</p><a href="/{ACTUAL}/foro/">Foro</a></div>'
    r = server.presentacion_curso(ACTUAL)
    assert (r["fuente"], r["secciones"]) == ("portada", ["foro"])
    assert "Bienvenidos" in r["texto"]
    assert f"/{ACTUAL}/datos_curso/" not in cli.pedidas


def _items(n):
    return '<div id="body">' + "".join(f'<div class="objeto"><a href="o/{i}">Tema {i}</a></div>' for i in range(n)) + "</div>"


def test_leer_seccion_por_partes_y_abre_un_item(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/foro/"] = _items(5)
    r = server.leer_seccion(ACTUAL, "Foro", limite=2)
    assert [i["titulo"] for i in r["items"]] == ["Tema 0", "Tema 1"]
    assert (r["total_items"], r["siguiente_desde"], r["seccion"]) == (5, 2, "foro")
    r = server.leer_seccion(ACTUAL, "foro", desde=4, limite=2)
    assert ([i["titulo"] for i in r["items"]], r["siguiente_desde"]) == (["Tema 4"], None)

    cli.paginas[f"/{ACTUAL}/foro/o/3"] = '<div id="body"><div class="objeto"><h2>Tema 3</h2><p>Hola</p></div></div>'
    r = server.leer_seccion(ACTUAL, "foro", ruta=r["items"][0]["url"].replace("4", "3"))
    assert r["items"][0]["texto"] == "Tema 3\nHola"
    assert server.leer_seccion(ACTUAL, "foro", ruta="o/3")["items"][0]["titulo"] == "Tema 3"


def test_leer_seccion_inexistente_lista_las_que_hay(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/"] = f'<a href="/{ACTUAL}/foro/">Foro</a>'
    with pytest.raises(ToolError, match="no tiene .* 'calendario'.*Secciones que sí tiene: foro"):
        server.leer_seccion(ACTUAL, "calendario")


@pytest.mark.parametrize("seccion, ruta, error", [
    ("integrantes", None, "no está disponible"),
    ("correo", None, "no está disponible"),
    ("foro", "/ingenieria/2026/2/MA2001/3/foro/", "no pertenece al curso"),
    ("foro", "https://evil.example.com/x", "Solo se permiten"),
    ("foro", "?accion=borrar&id=3", "solo lectura"),
    ("foro", "responder/3", "solo lectura"),
    ("foro", f"/{ACTUAL}/integrantes/", "no está disponible"),
    ("foro", f"/{ACTUAL}/material_docente/bajar?id=1", "leer_material"),
    ("foro", f"/{ACTUAL}/", "portada"),
    ("../notas", None, "no es un nombre de sección"),
])
def test_leer_seccion_rechaza(cli, seccion, ruta, error):
    from ucursos_mcp import server

    with pytest.raises(ToolError, match=error):
        server.leer_seccion(ACTUAL, seccion, ruta=ruta)
    assert cli.pedidas == []


def test_leer_seccion_no_confunde_slugs_con_acciones(cli):
    from ucursos_mcp import server

    assert server.ruta_seccion(ACTUAL, "foro", "o/3-como-enviar-la-tarea") == ("foro", f"/{ACTUAL}/foro/o/3-como-enviar-la-tarea")


def test_horario_no_expone_el_id_del_usuario(cli):
    from ucursos_mcp import server

    cli.user_id = "a" * 32
    cli.paginas[f"/usuario/{cli.user_id}/horario/"] = (
        "<table><tr><th>Hora</th><th>Lunes</th></tr><tr><td>8:30</td><td>MA2001 Cátedra</td></tr></table>"
    )
    r = server.horario()
    assert r["tablas"] == [{"columnas": ["Hora", "Lunes"], "filas": [["8:30", "MA2001 Cátedra"]]}]
    assert cli.user_id not in str(r)

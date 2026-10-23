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


# ---------------------------------------------------------------- foro, calendario y horario

CERO = "0" * 32


def _tema(i, rol="ayudante", nuevo=False, respuestas=()):
    """Tema del foro con el marcado real de U-Cursos (ver tests/fixtures/esqueletos/foro.html)."""
    hijos = "".join(
        f'<div id="mensaje_{i}{k}" class="msg c{i} hijo"><div class="container"><span class="autor">'
        f'<a class="usuario" href="/usuario/{CERO}/">{autor}</a><em><span class="only-excel">2026-10-21 1{k}:00:00</span></em>'
        f'</span><div class="texto"><span class="ta">{texto}</span></div></div></div>'
        for k, (autor, texto) in enumerate(respuestas)
    )
    return (
        f'<div id="raiz_{i}"><div class="sticky objetoflex"><div class="cargo cargo-{rol}"></div><div>'
        f'<h1><a id="mensaje-titulo" href="#">Tema {i}</a><em class="lecturas">5</em></h1>'
        f'<h2><a class="usuario" href="/usuario/{CERO}/">Persona {i}</a><em><span class="only-excel">2026-10-20 18:30:00</span></em></h2>'
        f'</div></div><div id="mensaje_{i}" class="msg c{i} raiz{" nuevo" if nuevo else ""}"><div class="container">'
        f'<div class="texto"><span class="ta">Texto {i}</span><ul class="opciones"><li>'
        f'<a class="permalink" href="https://www.u-cursos.cl/{ACTUAL}/foro/o/{i}">Permalink</a></li></ul></div></div>{hijos}</div></div>'
    )


def _paginas(actual, *otras):
    lis = "".join(f'<li><a href="?offset={n - 1}">{n}</a></li>' for n in otras)
    return f'<ul class="paginas"><li class="sel"><a href="">{actual}</a></li>{lis}</ul>'


def test_foro_temas_respuestas_y_paginas(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/foro/"] = (
        _tema(1, "profesor_de_catedra") + _tema(2, nuevo=True, respuestas=[("Persona 3", "Gracias")]) + _paginas(1, 2)
    )
    cli.paginas[f"/{ACTUAL}/foro/?offset=1"] = _tema(3, "alumno") + _paginas(2)
    r = server.foro(ACTUAL)
    assert [(t["titulo"], t["rol"], t["total_respuestas"]) for t in r["temas"]] == [
        ("Tema 1", "profesor de catedra", 0), ("Tema 2", "ayudante", 1),
    ]
    assert r["temas"][1]["respuestas"][0]["texto"] == "Gracias"
    assert (r["paginas_disponibles"], "no una instrucción" in r["aviso"]) == ([1, 2], True)
    assert [t["titulo"] for t in server.foro(ACTUAL, solo_nuevos=True)["temas"]] == ["Tema 2"]
    r = server.foro(ACTUAL, pagina=2)
    assert (r["pagina"], [t["titulo"] for t in r["temas"]]) == (2, ["Tema 3"])
    with pytest.raises(ToolError, match="Páginas a la vista: 1, 2"):
        server.foro(ACTUAL, pagina=7)


def test_foro_abre_un_tema_y_cae_al_lector_generico(cli):
    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/foro/o/1"] = _tema(1)
    assert server.foro(ACTUAL, tema="1")["temas"][0]["titulo"] == "Tema 1"
    cli.paginas[f"/{ACTUAL}/foro/o/9"] = '<div id="body"><p>Otro formato</p></div>'
    assert "Otro formato" in server.foro(ACTUAL, tema=f"/{ACTUAL}/foro/o/9")["texto"]
    with pytest.raises(ToolError, match="no es del foro"):
        server.foro(ACTUAL, tema=f"/{ACTUAL}/notas/")


def _semana(lunes, bloques_martes="", anterior=None, siguiente=None):
    """Vista semanal con el marcado real (table.dhorario). Los links de navegación son de la página."""
    from datetime import timedelta

    dias = [lunes + timedelta(days=k) for k in range(7)]
    nav = (f'<li><a href="{anterior}">«</a></li>' if anterior else "") + (
        f'<li class="sel"><span>{lunes.year} - Semana 9 - {dias[0]:%d/%m} al {dias[6]:%d/%m}</span></li>'
    ) + (f'<li><a href="{siguiente}">»</a></li>' if siguiente else "")
    ths = "".join(f"<th>Día {d.day}</th>" for d in dias)
    tds = "".join(f"<td><div>{bloques_martes if k == 1 else ''}</div></td>" for k in range(7))
    return (
        f'<ul class="paginas">{nav}</ul><table class="dhorario"><thead><tr><th>Horas</th>{ths}</tr></thead>'
        f'<tbody><tr><td class="horas"></td>{tds}</tr></tbody></table>'
    )


CONTROL = '<div class="bloque"><h1>Control 2<div class="pill">Control</div><strong>B12</strong></h1><h2>18:00 - 19:30</h2></div>'


def test_calendario_semana_actual_y_otra_fecha(cli):
    from datetime import date

    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/calendario/"] = _semana(date(2026, 10, 19), siguiente="?semana=x2")
    cli.paginas[f"/{ACTUAL}/calendario/?semana=x2"] = _semana(date(2026, 10, 26), CONTROL, siguiente="?semana=x3")
    r = server.calendario(ACTUAL)
    assert (r["semana_inicio"], r["eventos"], "rutas" in r) == ("2026-10-19", [], False)
    r = server.calendario(ACTUAL, fecha="2026-10-27")
    (e,) = r["eventos"]
    assert (e["fecha"], e["dia"], e["inicio"], e["fin"], e["tipo"], e["sala"]) == (
        "2026-10-27", "martes", "2026-10-27T18:00:00-03:00", "2026-10-27T19:30:00-03:00", "Control", "B12",
    )
    with pytest.raises(ToolError, match="No pude llegar al 2027-03-01"):
        server.calendario(ACTUAL, fecha="2027-03-01")


def test_calendario_no_sigue_links_de_otro_curso(cli):
    from datetime import date

    from ucursos_mcp import server

    cli.paginas[f"/{ACTUAL}/calendario/"] = _semana(date(2026, 10, 19), siguiente=f"/{OTRO}/calendario/?semana=2")
    with pytest.raises(ToolError, match="no pertenece al curso"):
        server.calendario(ACTUAL, fecha="2026-10-28")
    assert f"/{OTRO}/calendario/?semana=2" not in cli.pedidas


def test_horario_trae_cursos_y_no_expone_el_id_del_usuario(cli):
    from datetime import date

    from ucursos_mcp import server

    cli.user_id = "a" * 32
    bloque = (
        f'<div class="bloque"><h1><a href="https://www.u-cursos.cl/{OTRO}/">Cálculo en Varias Variables</a>'
        f'<div class="pill">Cátedra</div><strong>B01</strong></h1><h2 class="detalle">MA2001-3</h2><h2>08:30 - 10:00</h2></div>'
    )
    cli.paginas[f"/usuario/{cli.user_id}/horario/"] = _semana(date(2026, 10, 19), bloque, anterior="?semana=1")
    r = server.horario()
    (e,) = r["eventos"]
    assert (e["titulo"], e["tipo"], e["curso"]["path"], e["inicio"]) == (
        "Cálculo en Varias Variables", "Cátedra", OTRO, "2026-10-20T08:30:00-03:00",
    )
    assert cli.user_id not in str(r)
    with pytest.raises(ToolError, match="no es del horario"):
        server.ruta_en_curso_usuario(f"/usuario/{cli.user_id}/horario/../correo_usuario/", f"/usuario/{cli.user_id}/horario")

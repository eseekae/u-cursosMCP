"""
Capa de extracción: HTML de U-Cursos -> modelos limpios.

Es la ÚNICA capa que conoce el HTML. Si U-Cursos cambia su diseño, se arregla aquí.

Selectores basados en el reconocimiento del 19/10/2026:
  - Cursos:        links /{inst}/{año}/{sem}/{código}/{sección}/ en la barra lateral
  - Tareas:        /usuario/<id>/tareas_usuario/  -> table.sortable  (N°, Tarea, Fecha Límite, Estado)
  - Material:      .../material_docente/          -> table#materiales (Descargar, N°, Título, Por)
  - Notas:         .../notas/                     -> tabla con encabezado "Evaluación"
  - Novedades:     .../novedades/                 -> div.post.objeto
Los marcados con TODO son suposiciones razonables que hay que validar con HTML real.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .models import Curso, Material, Novedad, TablaNotas, Tarea

CURSO_URL_RE = re.compile(
    r"^(?:https://www\.u-cursos\.cl)?/(?P<inst>[a-z]+)/(?P<anio>\d{4})/(?P<sem>\d)/"
    r"(?P<codigo>[A-Z0-9]+)/(?P<seccion>\d+)/?$"
)
FECHA_HORA_RE = re.compile(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?")
FECHA_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _txt(el: Tag | None) -> str:
    """Texto de un nodo con espacios normalizados."""
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


# ---------------------------------------------------------------- cursos

def parse_cursos(html: str) -> list[Curso]:
    cursos: dict[str, Curso] = {}
    for a in _soup(html).find_all("a", href=True):
        m = CURSO_URL_RE.match(a["href"])
        if not m:
            continue
        path = "/".join(m.group("inst", "anio", "sem", "codigo", "seccion"))
        if path in cursos:
            continue
        # El texto viene como "Introducción a la Programación CC1002-7 6 Material Docente 6":
        # nos quedamos con lo que está antes de "CODIGO-SECCION".
        texto = _txt(a)
        nombre = texto.split(f"{m['codigo']}-{m['seccion']}")[0].strip() or texto
        cursos[path] = Curso(
            nombre=nombre,
            codigo=m["codigo"],
            seccion=m["seccion"],
            institucion=m["inst"],
            anio=int(m["anio"]),
            semestre=int(m["sem"]),
            path=path,
        )
    return list(cursos.values())


# ---------------------------------------------------------------- tareas

def parse_tareas_usuario(html: str) -> list[Tarea]:
    tabla = _soup(html).select_one("table.sortable")
    if tabla is None:
        return []
    tareas: list[Tarea] = []
    for tr in tabla.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        celda = tds[1]
        links = celda.find_all("a")
        # TODO validar: suponemos primer link = título de la tarea, último = curso.
        titulo = _txt(links[0]) if links else _txt(celda)
        curso = _txt(links[-1]) if len(links) > 1 else ""
        fecha = FECHA_HORA_RE.search(_txt(tds[2]))
        tareas.append(
            Tarea(
                titulo=titulo,
                curso=curso,
                fecha_limite=fecha.group(0) if fecha else _txt(tds[2]),
                estado=_txt(tds[3]),
            )
        )
    return tareas


# ---------------------------------------------------------------- material

def parse_material(html: str) -> list[Material]:
    tabla = _soup(html).select_one("table#materiales")
    if tabla is None:
        return []
    out: list[Material] = []
    for tr in tabla.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:  # filas de categoría ("Administrativo", etc.)
            continue
        titulo_a = tds[2].find("a")
        bajar = tr.find("a", href=re.compile(r"bajar"))
        autor_a = tds[3].find("a")
        fecha = FECHA_ISO_RE.search(_txt(tds[3]))
        out.append(
            Material(
                numero=_txt(tds[1]),
                titulo=_txt(titulo_a) if titulo_a else _txt(tds[2]),
                autor=_txt(autor_a),
                fecha=fecha.group(0) if fecha else "",
                descarga=bajar["href"] if bajar else None,
            )
        )
    return out


# ---------------------------------------------------------------- notas

def parse_notas(html: str) -> list[TablaNotas]:
    """Devuelve todas las tablas de notas del curso (puede haber varias)."""
    tablas: list[TablaNotas] = []
    for tabla in _soup(html).find_all("table"):
        columnas = [_txt(th) for th in tabla.find_all("th")]
        if not any("Evaluaci" in c for c in columnas):
            continue
        filas = [
            [_txt(td) for td in tr.find_all(["td", "th"])]
            for tr in tabla.select("tbody tr")
        ]
        tablas.append(TablaNotas(columnas=columnas, filas=[f for f in filas if any(f)]))
    return tablas


# ---------------------------------------------------------------- novedades

def parse_novedades(html: str, limite: int = 10) -> list[Novedad]:
    out: list[Novedad] = []
    for post in _soup(html).select("div.post.objeto")[:limite]:
        # TODO validar selectores de título y cuerpo con HTML real.
        titulo = post.find(["h1", "h2", "h3"]) or post.find("a")
        autor = post.find("a", href=re.compile(r"/usuario/"))
        fecha = FECHA_ISO_RE.search(_txt(post))
        out.append(
            Novedad(
                titulo=_txt(titulo),
                autor=_txt(autor),
                fecha=fecha.group(0) if fecha else "",
                resumen=_txt(post)[:500],
            )
        )
    return out

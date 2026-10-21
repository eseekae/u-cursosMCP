"""
Tests de parsers.

Dos niveles:
  1. HTML sintético (abajo), armado según el reconocimiento. Siempre corre.
  2. Fixtures reales anonimizados en tests/fixtures/<nombre>.html, capturados con
     scripts/capturar_html.py. Si existen, se verifica que el parser saque datos.
"""

from pathlib import Path

import pytest

from ucursos_mcp import parsers

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- sintéticos

HOME = """
<a href="https://www.u-cursos.cl/ingenieria/2026/2/CC1002/7/">Introducción a la Programación CC1002-7 6 Material Docente 6</a>
<a href="https://www.u-cursos.cl/ingenieria/2026/2/CC1002/7/material_docente/">Material Docente 6</a>
<a href="https://www.u-cursos.cl/bachillerato/2026/2/BA29/1/">Cálculo 2 BA29-1</a>
<a href="https://www.u-cursos.cl/uchile/4/foro_institucion/">Foro</a>
"""

TAREAS = """
<table class="sortable"><thead><tr><th>N°</th><th>Tarea</th><th>Fecha Límite</th><th>Estado</th></tr></thead>
<tbody><tr><td>1</td><td><a>Tarea 3</a> Tareas <a>Introducción a la Programación</a></td>
<td>06/11/2026 23:59 18 días</td><td>En Plazo</td></tr></tbody></table>
"""

MATERIAL = """
<table id="materiales"><tbody>
<tr><td>Administrativo</td></tr>
<tr><td></td><td>1</td><td><a href="detalle">Calendario_v2.pdf</a> Descargado</td>
<td><a href="/usuario/x/">Persona 1</a> 28 Ago 2026-08-28</td><td><a href="bajar?id=1">b</a></td></tr>
</tbody></table>
"""

NOTAS = """
<table><thead><tr><th>Evaluación</th><th>P1</th><th>Prom.</th></tr></thead>
<tbody><tr><td>C1</td><td>5.5</td><td>5.5</td></tr></tbody></table>
<table><thead><tr><th>Otra cosa</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>
"""


def test_cursos():
    cursos = parsers.parse_cursos(HOME)
    assert [c.path for c in cursos] == ["ingenieria/2026/2/CC1002/7", "bachillerato/2026/2/BA29/1"]
    assert cursos[0].nombre == "Introducción a la Programación"
    assert cursos[1].semestre == 2


def test_tareas():
    (t,) = parsers.parse_tareas_usuario(TAREAS)
    assert t.titulo == "Tarea 3"
    assert t.curso == "Introducción a la Programación"
    assert t.fecha_limite == "06/11/2026 23:59"
    assert t.estado == "En Plazo"


def test_material_salta_categorias():
    (m,) = parsers.parse_material(MATERIAL)
    assert m.titulo == "Calendario_v2.pdf"
    assert m.fecha == "2026-08-28"
    assert m.descarga == "bajar?id=1"


def test_notas_solo_tablas_de_evaluacion():
    (tabla,) = parsers.parse_notas(NOTAS)
    assert tabla.columnas == ["Evaluación", "P1", "Prom."]
    assert tabla.filas == [["C1", "5.5", "5.5"]]


def test_html_vacio_no_explota():
    for fn in (parsers.parse_cursos, parsers.parse_tareas_usuario, parsers.parse_material,
               parsers.parse_notas, parsers.parse_novedades):
        assert fn("<html></html>") == []


# ---------------------------------------------------------------- fixtures reales

REALES = {
    "home": parsers.parse_cursos,
    "tareas_usuario": parsers.parse_tareas_usuario,
    "material_docente": parsers.parse_material,
    "notas": parsers.parse_notas,
    "novedades": parsers.parse_novedades,
}


@pytest.mark.parametrize("nombre,parser", REALES.items())
def test_fixture_real(nombre, parser):
    archivo = FIXTURES / f"{nombre}.html"
    if not archivo.exists():
        pytest.skip(f"Falta {archivo.name}: captúralo con scripts/capturar_html.py")
    assert parser(archivo.read_text(encoding="utf-8")), f"{nombre}: el parser no sacó nada"

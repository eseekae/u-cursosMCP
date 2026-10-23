"""El esqueleto de una página no debe dejar datos personales, pero sí servirle a los parsers."""

import importlib.util
from pathlib import Path

from ucursos_mcp import parsers

_spec = importlib.util.spec_from_file_location("capturar_html", Path(__file__).parent.parent / "scripts" / "capturar_html.py")
capturar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capturar)

HASH = "abcdef0123456789abcdef0123456789"
PAGINA = f"""<html><head><title>Foro MA2001</title><meta name="csrf" content="tok123secreto">
<style>.x{{}}</style></head><body>
<div id="usuario">Hola, Sebastián Ramírez <a href="/usuario/{HASH}/">Sebastián Ramírez</a></div>
<div id="menu"><a href="/ingenieria/2026/2/MA2001/3/">Cálculo en Varias Variables MA2001-3</a>
<a href="/ingenieria/2026/2/CC1002/7/">Introducción a la Programación CC1002-7</a></div>
<div id="body"><!-- comentario con tok -->
<table><tr><th>Profesor</th><td>Juana Pérez, juana.perez@uchile.cl</td></tr></table>
<div class="objeto" data-autor="juana"><h3><a href="o/31-duda-de-juana">Duda de Juana sobre el control</a></h3>
<span class="fecha">24 de Agosto a las 22:26 hrs</span><p>Mi RUT es 12.345.678-9 y mi fono +56 9 8765 4321.</p>
<a href="https://drive.google.com/file/d/privado">apunte</a>
<a href="../material_docente/bajar?id=5&amp;token=abc">Pauta de Juana.pdf</a>
<a href="/archivos/juana-perez.pdf">otro</a><img src="https://fotos.cl/juana.jpg" alt="Juana"></div>
<p><strong>Sala:</strong> B-212</p>
<ul><li id="widget_perfil" class="usuario {HASH}"></li><li id="curso.1349697"></li></ul>
<div id="mensaje_555555" class="msg c555555 raiz"></div><div id="mensaje_777777" class="msg c555555 hijo"></div>
<td class="semana-202602"></td>
</div></body></html>"""


def test_esqueleto_no_deja_datos():
    out = capturar.esqueleto(PAGINA)
    for dato in ("Sebastián", "Ramírez", "Juana", "juana", "Pérez", "MA2001", "CC1002", "Cálculo", HASH,
                 "12.345.678-9", "8765", "drive.google", "privado", "tok", "fotos.cl", "data-autor", "Varias",
                 "1349697", "555555", "777777"):
        assert dato not in out, dato
    assert capturar.sospechosos(out) == []


def test_ids_falsos_mantienen_las_relaciones():
    out = capturar.esqueleto(PAGINA)
    assert 'class="msg c10002 raiz" id="mensaje_10002"' in out  # el mismo id real da el mismo falso
    assert 'class="msg c10002 hijo" id="mensaje_10003"' in out
    assert 'class="semana-202602"' in out and f'class="usuario {"0" * 32}"' in out
    assert capturar.limpiar_ids(out) == out  # se puede pasar de nuevo sin cambiar nada


def test_sospechosos_detecta_hashes():
    assert capturar.sospechosos(f'<li class="usuario {HASH}">') == [HASH]


def test_esqueleto_conserva_estructura_fechas_y_etiquetas():
    out = capturar.esqueleto(PAGINA)
    for queda in ('class="objeto"', 'id="body"', "Profesor", "Sala:", "24 de Agosto a las 22:26 hrs", "B-212".replace("B", "X"),
                  "/ingenieria/2026/2/CURSO1/3/", "CURSO1-3", "material_docente/bajar", "o/x", "/archivos/archivo.pdf",
                  "persona@ejemplo.cl", "11.111.111-1"):
        assert queda in out, queda


def test_parsers_funcionan_sobre_el_esqueleto():
    cursos = parsers.parse_cursos(capturar.esqueleto(PAGINA))
    assert [(c.codigo, c.path) for c in cursos] == [("CURSO1", "ingenieria/2026/2/CURSO1/3"), ("CURSO2", "ingenieria/2026/2/CURSO2/7")]
    c = parsers.parse_contenido(capturar.esqueleto(PAGINA), "/ingenieria/2026/2/CURSO1/3/foro/", 2026, "ingenieria/2026/2/CURSO1/3")
    (item,) = c.items
    assert item.fecha == "2026-08-24T22:26:00-04:00"
    assert item.url == "/ingenieria/2026/2/CURSO1/3/foro/o/x"
    assert list(c.campos) == ["Profesor", "Sala"]
    assert [a.descarga for a in c.archivos] == ["/ingenieria/2026/2/CURSO1/3/material_docente/bajar?id=5"]

"""
Capa de extracción: HTML de U-Cursos -> modelos limpios.

Es la ÚNICA capa que conoce el HTML. Si U-Cursos cambia su diseño, se arregla aquí.

Selectores basados en el reconocimiento del 19/10/2026:
  - Cursos:        links /{inst}/{año}/{sem}/{código}/{sección}/ en la barra lateral
  - Tareas:        /usuario/<id>/tareas_usuario/ y .../tareas/ -> tabla con th "Tarea" (o "Título"),
                   "Fecha Límite" y "Estado". Las columnas se ubican por su encabezado.
  - Detalle tarea: la página a la que apunta el link de cada tarea (pares etiqueta/valor y archivos)
  - Material:      .../material_docente/          -> table#materiales (Descargar, N°, Título, Por)
  - Notas:         .../notas/                     -> tabla con encabezado "Evaluación"
  - Novedades:     .../novedades/                 -> div.post.objeto
  - Otras secciones (datos_curso, calendario, foro, clases, horario, ...): parse_contenido, genérico.
Los marcados con TODO son suposiciones razonables que hay que validar con HTML real.

Todo el texto que sale de aquí (enunciados, comentarios, novedades) lo escribió alguien del
curso: es un dato, no una instrucción para el modelo.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from .models import (
    Archivo,
    Contenido,
    Curso,
    CursoRef,
    DetalleTarea,
    Enlace,
    Item,
    Material,
    Novedad,
    Tabla,
    TablaNotas,
    Tarea,
)

SANTIAGO = ZoneInfo("America/Santiago")

CURSO_URL_RE = re.compile(
    r"^(?:https://www\.u-cursos\.cl)?/(?P<inst>[a-z]+)/(?P<anio>\d{4})/(?P<sem>\d)/"
    r"(?P<codigo>[A-Z0-9]+)/(?P<seccion>\d+)/?$"
)
# Prefijo de curso en cualquier ruta (para saber de qué curso es un link a una tarea).
CURSO_PREFIJO_RE = re.compile(r"^/(?P<path>[a-z]+/\d{4}/\d/(?P<codigo>[A-Z0-9]+)/\d+)/")
FECHA_HORA_RE = re.compile(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?")
FECHA_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _txt(el: Tag | None) -> str:
    """Texto de un nodo con espacios normalizados."""
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def _parrafos(el: Tag | None) -> str:
    """Texto de un nodo conservando los saltos de línea (para enunciados y novedades)."""
    if el is None:
        return ""
    lineas = (" ".join(linea.split()) for linea in el.get_text("\n").splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def sin_tildes(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar etiquetas y estados."""
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _ruta(base: str, href: str) -> str:
    """Resuelve un href contra la página donde apareció. Devuelve ruta + query, sin dominio."""
    u = urlparse(urljoin(f"https://www.u-cursos.cl{base}", href))
    return u.path + (f"?{u.query}" if u.query else "")


def _es_u_cursos(href: str) -> bool:
    host = urlparse(href).hostname
    return host is None or host in ("www.u-cursos.cl", "u-cursos.cl")


# ---------------------------------------------------------------- fechas

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
_HORA = r"(?:\s*(?:,|a\s+las|-)?\s*(?P<h>\d{1,2}):(?P<mi>\d{2}))?"
FECHA_NUM_RE = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<a>\d{4})" + _HORA)
FECHA_ISO_FULL_RE = re.compile(r"\b(?P<a>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?:[T\s]+(?P<h>\d{2}):(?P<mi>\d{2}))?")
FECHA_TEXTO_RE = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?:de\s+)?(?P<mes>ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?"
    r"(?:\s+(?:de(?:l)?\s+)?(?P<a>\d{4}))?" + _HORA
)


def fechas_en(texto: str, anio: int | None = None) -> list[datetime | date]:
    """Todas las fechas de un texto, en el orden en que aparecen.

    Entiende "06/11/2026 23:59", "2026-08-28" y "24 de Agosto a las 22:26 hrs" (si falta el
    año se usa `anio`, o el actual). Con hora -> datetime con zona de Santiago; sin hora -> date.
    """
    t = sin_tildes(texto)
    anio = anio or datetime.now(SANTIAGO).year
    encontradas: list[tuple[int, datetime | date]] = []
    for regex in (FECHA_NUM_RE, FECHA_ISO_FULL_RE, FECHA_TEXTO_RE):
        for m in regex.finditer(t):
            g = m.groupdict()
            mes = MESES[g["mes"]] if g.get("mes") else int(g["m"])
            try:
                d = date(int(g["a"]) if g["a"] else anio, mes, int(g["d"]))
                if g["h"]:
                    f: datetime | date = datetime(d.year, d.month, d.day, int(g["h"]), int(g["mi"]), tzinfo=SANTIAGO)
                else:
                    f = d
            except ValueError:  # 31/02, 25:00, etc.
                continue
            encontradas.append((m.start(), f))
    return [f for _, f in sorted(encontradas, key=lambda x: x[0])]


def fecha_iso(texto: str, anio: int | None = None) -> str | None:
    """La fecha más precisa del texto en ISO 8601 (prefiere la que trae hora). None si no hay."""
    fechas = fechas_en(texto, anio)
    if not fechas:
        return None
    con_hora = [f for f in fechas if isinstance(f, datetime)]
    return (con_hora or fechas)[0].isoformat()


def normalizar_estado(texto: str, anio: int | None = None) -> tuple[str, str | None, bool | None]:
    """Texto de estado de U-Cursos -> (estado, fecha_entrega, con_atraso).

    estado: entregada (hay entrega; con_atraso dice si fue fuera de plazo), pendiente (en plazo,
    sin entregar), atrasada (plazo vencido pero aún se puede entregar con atraso), cerrada (ya no
    acepta entregas) o desconocido.
    """
    t = sin_tildes(texto)
    atraso = bool(re.search(r"atras|fuera de plazo|tardi", t))
    no_entregada = bool(re.search(r"\bno\s+(?:ha\s+)?(?:entregad|enviad)|sin entrega", t))
    if not no_entregada and re.search(r"entregad|enviad|recibid|entrega realizada", t):
        return "entregada", fecha_iso(texto, anio), atraso
    if re.search(r"cerrad|vencid|finalizad|expirad|no acepta", t):
        return "cerrada", None, None
    if atraso:
        return "atrasada", None, None
    if no_entregada or re.search(r"plazo|pendiente|abierta|por entregar|disponible", t):
        return "pendiente", None, None
    return "desconocido", None, None


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


def parse_servicios(html: str, curso_path: str) -> list[str]:
    """Secciones (servicios) que la portada de un curso o comunidad enlaza: material_docente, foro, ..."""
    prefijo = re.compile(rf"^(?:https://www\.u-cursos\.cl)?/{re.escape(curso_path.strip('/'))}/([a-z0-9_]+)/")
    vistos: dict[str, None] = {}
    for a in _soup(html).find_all("a", href=True):
        m = prefijo.match(a["href"])
        if m:
            vistos.setdefault(m.group(1))
    return list(vistos)


# ---------------------------------------------------------------- tareas

TAREA_ID_RE = re.compile(r"/tareas/(?:[a-z_]+/)*(\d+)(?:/|$|\?)|[?&]id(?:_tarea)?=(\d+)")

# Columna -> palabras de su encabezado (sin tildes, en minúsculas). Se busca en orden.
COLUMNAS_TAREA = {
    "titulo": ("tarea", "titulo", "nombre"),
    "limite": ("limite", "plazo", "cierre", "termino", "fecha de entrega"),
    "estado": ("estado",),
}


def _columnas(tabla: Tag) -> dict[str, int]:
    """Ubica las columnas de una tabla de tareas leyendo sus <th>."""
    fila = tabla.select_one("thead tr") or tabla.find("tr")
    ths = [sin_tildes(_txt(th)) for th in fila.find_all(["th", "td"])] if fila else []
    cols: dict[str, int] = {}
    for campo, claves in COLUMNAS_TAREA.items():
        for clave in claves:
            i = next((i for i, th in enumerate(ths) if clave in th and i not in cols.values()), None)
            if i is not None:
                cols[campo] = i
                break
    return cols


def _tabla_tareas(soup: BeautifulSoup) -> tuple[Tag, dict[str, int]] | None:
    for tabla in soup.find_all("table"):
        cols = _columnas(tabla)
        if "titulo" in cols and ("limite" in cols or "estado" in cols):
            return tabla, cols
    # Vista general antigua: table.sortable con N°, Tarea, Fecha Límite, Estado.
    tabla = soup.select_one("table.sortable")
    return (tabla, {"titulo": 1, "limite": 2, "estado": 3}) if tabla else None


def _id_tarea(ruta: str) -> str | None:
    m = TAREA_ID_RE.search(ruta)
    return (m.group(1) or m.group(2)) if m else None


def parse_tareas(html: str, base: str = "/", anio: int | None = None) -> list[Tarea]:
    """Tareas de una tabla de U-Cursos (vista general tareas_usuario o la sección tareas de un curso).

    `base` es la ruta de la página (para resolver los links); `anio`, el año del curso, para las
    fechas que vienen sin año. El curso de cada tarea se saca de su link si se puede; si no, del
    texto de un link a un curso en la misma celda (la tool completa el resto).
    """
    encontrada = _tabla_tareas(_soup(html))
    if encontrada is None:
        return []
    tabla, cols = encontrada
    filas = tabla.select("tbody tr") or tabla.find_all("tr")[1:]
    tareas: list[Tarea] = []
    for tr in filas:
        tds = tr.find_all("td")
        if len(tds) <= max(cols.values()):
            continue
        celda = tds[cols["titulo"]]
        links = celda.find_all("a")
        link = next((a for a in links if "tareas" in a.get("href", "")), links[0] if links else None)
        titulo = _txt(link) if link else _txt(celda)
        if not titulo:
            continue
        url = _ruta(base, link["href"]) if link is not None and link.get("href") and _es_u_cursos(link["href"]) else None

        curso = None
        if url and (m := CURSO_PREFIJO_RE.match(url)):
            curso = CursoRef(path=m["path"], codigo=m["codigo"])
        elif len(links) > 1:
            # TODO validar: en tareas_usuario el último link de la celda sería el curso.
            ultimo = links[-1]
            m = CURSO_PREFIJO_RE.match(_ruta(base, ultimo.get("href", "")) + "/") if ultimo.get("href") else None
            curso = CursoRef(nombre=_txt(ultimo), path=m["path"] if m else "", codigo=m["codigo"] if m else "")

        estado_txt = _txt(tds[cols["estado"]]) if "estado" in cols else ""
        estado, entrega, atraso = normalizar_estado(estado_txt, anio)
        limite_txt = _txt(tds[cols["limite"]]) if "limite" in cols else ""
        tareas.append(
            Tarea(
                id=_id_tarea(url) if url else None,
                titulo=titulo,
                curso=curso,
                url=url,
                fecha_limite=fecha_iso(limite_txt, anio),
                estado=estado,
                fecha_entrega=entrega,
                con_atraso=atraso,
                estado_texto=estado_txt,
            )
        )
    return tareas


def parse_tareas_usuario(html: str) -> list[Tarea]:
    """Vista general /usuario/<id>/tareas_usuario/ (todas las tareas, de todos los cursos)."""
    return parse_tareas(html)


# ---------------------------------------------------------------- detalle de tarea

ETIQUETAS = ("th", "dt", "label", "strong", "b")
ARCHIVO_RE = re.compile(
    r"bajar|descargar|download|/archivo|"
    r"\.(?:pdf|docx?|pptx?|xlsx?|odt|zip|rar|7z|tar|gz|txt|md|csv|py|ipynb|java|c|cpp|h|m|r|jl|tex|png|jpe?g)(?:\?|$)",
    re.I,
)
# Encabezados que anuncian los archivos que entregó el usuario (no los del enunciado).
ENTREGADOS_RE = re.compile(r"entregad|enviad|respuesta|\b(?:mi|mis|tu|tus|su|sus)\b.*entrega|^entregas?$")
ETIQUETAS_DETALLE = {
    "enunciado": ("descripcion", "enunciado", "instrucciones", "indicaciones"),
    "apertura": ("apertura", "inicio", "publicacion", "publicada", "disponible desde"),
    "cierre": ("fecha limite", "limite", "cierre", "plazo", "termino", "fecha de entrega"),
    "estado": ("estado",),
    "nota": ("nota", "calificacion", "puntaje"),
    "comentarios": ("comentario", "observacion", "retroalimentacion", "feedback", "correccion"),
}


def _pares(soup: BeautifulSoup | Tag) -> dict[str, str]:
    """Pares "etiqueta: valor" de la página: dl/dt-dd, filas th-td y <strong>Etiqueta:</strong> valor."""
    pares: dict[str, str] = {}

    def agrega(etiqueta: str, valor: str) -> None:
        etiqueta = etiqueta.strip().rstrip(":").strip()
        if etiqueta and valor and len(etiqueta) <= 60 and etiqueta not in pares:
            pares[etiqueta] = valor

    for dt in soup.find_all("dt"):
        agrega(_txt(dt), _parrafos(dt.find_next_sibling("dd")))
    for tr in soup.find_all("tr"):
        celdas = tr.find_all(["th", "td"], recursive=False)
        # El valor es td: una fila th + th es el encabezado de una tabla, no un par.
        if len(celdas) == 2 and celdas[1].name == "td" and (celdas[0].name == "th" or _txt(celdas[0]).endswith(":")):
            agrega(_txt(celdas[0]), _parrafos(celdas[1]))
    for et in soup.find_all(["strong", "b", "label"]):
        texto = _txt(et)
        if texto.endswith(":") and et.parent is not None:
            resto = _txt(et.parent).removeprefix(texto).strip()
            agrega(texto, resto)
    return pares


def _buscar(pares: dict[str, str], claves: tuple[str, ...]) -> str | None:
    for clave in claves:
        for etiqueta, valor in pares.items():
            if clave in sin_tildes(etiqueta):
                return valor
    return None


def _es_entregado(a: Tag) -> bool:
    for anc in a.parents:
        marca = " ".join([anc.get("id", ""), *anc.get("class", [])]) if isinstance(anc, Tag) else ""
        if re.search(r"entrega|respuesta", marca, re.I):
            return True
    previo = a.find_previous(["h1", "h2", "h3", "h4", "h5", "legend", *ETIQUETAS])
    return bool(previo and ENTREGADOS_RE.search(sin_tildes(_txt(previo))))


def parse_detalle_tarea(html: str, base: str, anio: int | None = None) -> DetalleTarea:
    """Página de una tarea -> enunciado, fechas, estado, nota, comentarios y archivos.

    TODO validar con HTML real: no hay fixture todavía. Se buscan etiquetas por texto
    ("Fecha Límite", "Estado", "Nota", ...) en vez de posiciones, y `campos` trae todos los
    pares encontrados para que nada se pierda si una etiqueta no calza.
    """
    soup = _soup(html)
    for basura in soup.find_all(["script", "style", "noscript"]):
        basura.decompose()
    cuerpo = soup.select_one("div.objeto, div.tarea, #body, #contenido, main") or soup
    pares = _pares(cuerpo)

    titulo_el = cuerpo.find(["h1", "h2", "h3"])
    enunciado = _buscar(pares, ETIQUETAS_DETALLE["enunciado"])
    if not enunciado:
        bloques = cuerpo.find_all("div", class_=re.compile(r"texto|descripcion|enunciado|cuerpo|contenido"))
        enunciado = max((_parrafos(b) for b in bloques), key=len, default="")

    adjuntos: dict[str, Archivo] = {}
    entregados: dict[str, Archivo] = {}
    for a in cuerpo.find_all("a", href=True):
        href = a["href"]
        if not ARCHIVO_RE.search(href) or not _es_u_cursos(href):
            continue
        descarga = _ruta(base, href)
        nombre = _txt(a) or urlparse(descarga).path.rstrip("/").rsplit("/", 1)[-1]
        destino = entregados if _es_entregado(a) else adjuntos
        destino.setdefault(descarga, Archivo(nombre=nombre, descarga=descarga))

    estado_txt = _buscar(pares, ETIQUETAS_DETALLE["estado"]) or ""
    estado, entrega, atraso = normalizar_estado(estado_txt, anio)
    if estado != "entregada" and entregados:
        estado, atraso = "entregada", bool(re.search(r"atras|fuera de plazo", sin_tildes(estado_txt)))
    apertura = _buscar(pares, ETIQUETAS_DETALLE["apertura"])
    cierre = _buscar(pares, ETIQUETAS_DETALLE["cierre"])
    return DetalleTarea(
        id=_id_tarea(base),
        titulo=_txt(titulo_el),
        url=base,
        enunciado=enunciado,
        fecha_apertura=fecha_iso(apertura, anio) if apertura else None,
        fecha_cierre=fecha_iso(cierre, anio) if cierre else None,
        estado=estado,
        estado_texto=estado_txt,
        fecha_entrega=entrega,
        con_atraso=atraso,
        nota=_buscar(pares, ETIQUETAS_DETALLE["nota"]),
        comentarios=_buscar(pares, ETIQUETAS_DETALLE["comentarios"]),
        adjuntos=list(adjuntos.values()),
        entregados=list(entregados.values()),
        campos=pares,
    )


# ---------------------------------------------------------------- material

def parse_material(html: str) -> list[Material]:
    tabla = _soup(html).select_one("table#materiales")
    if tabla is None:
        return []
    out: list[Material] = []
    categoria = ""
    for tr in tabla.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            # Filas de categoría ("Administrativo", "Ayudantías", ...): agrupan lo que sigue.
            if texto := _txt(tr):
                categoria = texto
            continue
        titulo_a = tds[2].find("a")
        bajar = tr.find("a", href=re.compile(r"bajar"))
        autor_a = tds[3].find("a")
        fecha = FECHA_ISO_RE.search(_txt(tds[3]))
        out.append(
            Material(
                categoria=categoria,
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

MAX_TEXTO_NOVEDAD = 8_000


def parse_novedades(html: str, limite: int = 10, base: str = "/") -> list[Novedad]:
    out: list[Novedad] = []
    for post in _soup(html).select("div.post.objeto")[:limite]:
        # TODO validar selectores de título y cuerpo con HTML real.
        titulo = post.find(["h1", "h2", "h3"]) or post.find("a")
        autor = post.find("a", href=re.compile(r"/usuario/"))
        fecha = FECHA_ISO_RE.search(_txt(post))
        enlaces: dict[str, None] = {}
        for a in post.find_all("a", href=True):
            href = a["href"]
            if "/usuario/" in href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            enlaces.setdefault(_ruta(base, href) if _es_u_cursos(href) else href)
        out.append(
            Novedad(
                titulo=_txt(titulo),
                autor=_txt(autor),
                fecha=fecha.group(0) if fecha else "",
                texto=_parrafos(post)[:MAX_TEXTO_NOVEDAD],
                enlaces=list(enlaces),
            )
        )
    return out


# ---------------------------------------------------------------- secciones genéricas

MAX_TEXTO_ITEM = 4_000
MAX_TEXTO_PAGINA = 15_000
MAX_FILAS = 200
MAX_ENLACES = 40
# TODO validar con HTML real: dónde está el contenido (sin la barra lateral ni el menú).
CONTENEDORES = ("#body", "#contenido", "#content", "main", "div#cuerpo")
BASURA = ["script", "style", "noscript", "nav", "iframe", "textarea", "select", "input", "button"]
EXTENSION_RE = re.compile(
    r"\.(?:pdf|docx?|pptx?|xlsx?|odt|zip|rar|7z|tar|gz|txt|md|csv|py|ipynb|java|c|cpp|h|m|r|jl|tex|png|jpe?g)$", re.I
)


def es_descarga(ruta: str) -> bool:
    """True si el link baja un archivo (no es una página). Más estricto que ARCHIVO_RE: la
    sección `archivos` de una comunidad es una página, no una descarga."""
    u = urlparse(ruta)
    return bool(re.search(r"bajar|descargar|download", f"{u.path}?{u.query}", re.I) or EXTENSION_RE.search(u.path))


def _enlace_util(href: str, base: str, curso: str | None) -> str | None:
    """Ruta (interna) o URL (externa) de un link que vale la pena mostrar; None si es navegación.

    Con `curso` solo quedan los links internos de ese curso; sin él, los de cualquier curso.
    """
    if href.startswith(("#", "javascript:", "mailto:", "tel:")) or "/usuario/" in href:
        return None
    if not _es_u_cursos(href):
        return href if href.startswith(("http://", "https://")) else None
    ruta = _ruta(base, href)
    if curso is not None:
        return ruta if ruta.startswith(f"/{curso}/") else None
    return ruta if CURSO_PREFIJO_RE.match(ruta) else None


def _item(el: Tag, base: str, anio: int | None, curso: str | None) -> Item:
    texto = _parrafos(el)
    url = link_url = None
    enlaces: dict[str, None] = {}
    for a in el.find_all("a", href=True):
        u = _enlace_util(a["href"], base, curso)
        if u is None or es_descarga(u):
            continue
        if url is None and u.startswith("/"):
            url, link_url = u, a
        else:
            enlaces.setdefault(u)
    titulo_el = el.find(["h1", "h2", "h3", "h4"]) or link_url
    autor = el.find("a", href=re.compile(r"/usuario/"))
    fecha_el = el.find("time") or el.find(class_=re.compile(r"fecha|date|hora"))
    fecha = fecha_iso(fecha_el.get("datetime") or _txt(fecha_el), anio) if fecha_el else None
    return Item(
        titulo=_txt(titulo_el) or texto.split("\n", 1)[0][:120],
        autor=_txt(autor),
        fecha=fecha or fecha_iso(_txt(el), anio),
        texto=texto[:MAX_TEXTO_ITEM],
        url=url,
        enlaces=list(enlaces),
    )


def _celdas(tabla: Tag) -> list[list[Tag]]:
    """Celdas de cada fila de la tabla (sin las de tablas anidadas)."""
    return [tr.find_all(["th", "td"], recursive=False) for tr in tabla.find_all("tr") if tr.find_parent("table") is tabla]


def _es_de_pares(tabla: Tag) -> bool:
    """Tabla de pares etiqueta/valor (th + td en cada fila): esos van a `campos`."""
    celdas = _celdas(tabla)
    return bool(celdas) and all(len(c) == 2 and c[0].name == "th" for c in celdas)


def _tabla_generica(tabla: Tag) -> Tabla | None:
    """Tabla con encabezados (columnas) y filas. None si no tiene datos o si es de pares etiqueta/valor."""
    celdas = _celdas(tabla)
    if not celdas or _es_de_pares(tabla):
        return None
    encabezado = next((c for c in celdas if c and all(x.name == "th" for x in c)), None)
    datos = [[_txt(x) for x in c] for c in celdas if c is not encabezado and any(_txt(x) for x in c)]
    if not datos:
        return None
    return Tabla(columnas=[_txt(x) for x in encabezado] if encabezado else [], filas=datos[:MAX_FILAS])


def parse_contenido(html: str, base: str, anio: int | None = None, curso: str | None = None) -> Contenido:
    """Cualquier página de U-Cursos -> contenido ordenado, sin conocer el diseño de cada sección.

    Sirve para las secciones sin parser propio (datos_curso, calendario, foro, clases, enlaces,
    horario, ...): los objetos (`.objeto`, como los posts de novedades) van a `items`, las tablas
    a `tablas`, los pares "Etiqueta: valor" a `campos`, los archivos a `archivos` y lo que queda a
    `texto`. `curso` deja solo los links de ese curso (los demás no se pueden abrir).
    TODO validar con HTML real de cada sección; si alguna se usa mucho, darle un parser propio.
    """
    soup = _soup(html)
    for basura in soup.find_all(BASURA):
        basura.decompose()
    cuerpo = next((el for sel in CONTENEDORES if (el := soup.select_one(sel)) is not None), None) or soup.body or soup

    archivos: dict[str, Archivo] = {}
    for a in cuerpo.find_all("a", href=True):
        u = _enlace_util(a["href"], base, curso)
        if u is not None and u.startswith("/") and es_descarga(u):
            nombre = _txt(a) or urlparse(u).path.rstrip("/").rsplit("/", 1)[-1]
            archivos.setdefault(u, Archivo(nombre=nombre, descarga=u))

    # Objetos de primer nivel (un tr.objeto se queda en su tabla).
    objetos = [e for e in cuerpo.select(".objeto") if e.name != "tr" and e.find_parent(class_="objeto") is None]
    items = [_item(e, base, anio, curso) for e in objetos]
    for e in objetos:
        e.extract()

    titulo_el = cuerpo.find(["h1", "h2"]) or soup.find("title")
    campos = _pares(cuerpo)
    enlaces: dict[str, Enlace] = {}
    for a in cuerpo.find_all("a", href=True):
        u = _enlace_util(a["href"], base, curso)
        if u is not None and not es_descarga(u) and len(enlaces) < MAX_ENLACES:
            enlaces.setdefault(u, Enlace(texto=_txt(a)[:120], url=u))

    tablas: list[Tabla] = []
    for t in [t for t in cuerpo.find_all("table") if t.find_parent("table") is None]:
        tabla = _tabla_generica(t)
        if tabla is not None:
            tablas.append(tabla)
        if tabla is not None or _es_de_pares(t):
            t.extract()  # ya quedó en `tablas` o en `campos`; no se repite en `texto`

    return Contenido(
        titulo=_txt(titulo_el),
        url=base,
        campos=campos,
        items=items,
        tablas=tablas,
        texto=_parrafos(cuerpo)[:MAX_TEXTO_PAGINA],
        archivos=list(archivos.values()),
        enlaces=list(enlaces.values()),
    )

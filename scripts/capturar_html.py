"""
Captura una página de U-Cursos con tu sesión y guarda dos versiones:

  tests/fixtures/<nombre>.html             la página casi completa. Queda en tu PC (.gitignore).
  tests/fixtures/esqueletos/<nombre>.html  solo la estructura, sin datos tuyos ni de nadie: esta se sube.

Uso:
    uv run python scripts/capturar_html.py <ruta> <nombre>
    uv run python scripts/capturar_html.py --esqueleto [archivos.html ...]

Ejemplos:
    uv run python scripts/capturar_html.py /usuario/me/tareas_usuario/ tareas_usuario
    uv run python scripts/capturar_html.py ingenieria/2026/2/CC1002/7/notas/ notas
    uv run python scripts/capturar_html.py --esqueleto      # rehace los esqueletos de todo tests/fixtures/*.html

`/usuario/me/` se reemplaza por tu hash real.

Anonimización de la versión local (no es suficiente para publicarla):
  - hashes de usuario (/usuario/<hash32>/) -> 000...0
  - query strings: se quitan los parámetros con tokens (csrf, etc.) y los valores que no son
    números cortos quedan como "x"
  - nombres en links a perfiles de usuario -> "Persona N"
  - scripts inline -> se eliminan (pueden traer tokens)

Esqueleto (lo que se publica): además de lo anterior
  - todo texto escrito por personas -> "Xxxxx xxx" del mismo largo. Se conservan los números,
    las fechas (meses, días, "de", "a las", "hrs"), los encabezados de tablas (th, dt, label) y
    las etiquetas cortas que terminan en ":" ("Profesor:")
  - códigos de curso -> CURSO1, CURSO2, ... (en links y texto); links externos -> ejemplo.cl
  - correos, RUT y teléfonos -> valores falsos
  - hashes de usuario en cualquier parte (también en clases CSS) -> 000...0, e ids numéricos
    largos de cursos y mensajes -> números falsos
  - se borran meta, link, style, svg, comentarios y todo atributo salvo id, class, href,
    colspan, rowspan, datetime y type
Revisa igual el esqueleto antes de subirlo (ábrelo en el navegador: solo debería verse "xxxx").
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
ESQUELETOS = FIXTURES / "esqueletos"
HASH_RE = re.compile(r"/usuario/[0-9a-f]{32}/")
FALSO = "/usuario/" + "0" * 32 + "/"


TOKEN_RE = re.compile(r"csrf|token|hash|key|sesion|session|auth|firma|sig", re.I)


def _sin_tokens(href: str) -> str:
    """Query sin tokens: se conservan los nombres de los parámetros (sirven para saber cómo pagina
    U-Cursos) con valores numéricos cortos; el resto de los valores queda como "x"."""
    base, _, query = href.partition("?")
    pares = [
        (k, v if re.fullmatch(r"\d{1,8}", v) else "x")
        for k, v in parse_qsl(query, keep_blank_values=True)
        if not TOKEN_RE.search(k)
    ]
    return base + (f"?{urlencode(pares)}" if pares else "")


def anonimizar(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.find_all("script"):
        s.decompose()

    personas: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = HASH_RE.search(href)
        # Link a un perfil (/usuario/<hash>/ sin servicio): reemplazar el nombre visible.
        if m and href.rstrip("/").endswith(m.group(0).rstrip("/")):
            nombre = a.get_text(strip=True)
            if nombre:
                personas.setdefault(nombre, f"Persona {len(personas) + 1}")
                a.string = personas[nombre]
        a["href"] = _sin_tokens(href)

    for tag in soup.find_all(["form", "input"]):
        for attr in ("action", "value"):
            if tag.has_attr(attr) and len(str(tag[attr])) > 20:
                tag[attr] = ""

    out = HASH_RE.sub(FALSO, str(soup))
    # Nombres de personas que aparecen como texto suelto fuera de los links.
    for real, falso in personas.items():
        out = out.replace(real, falso)
    return out


# ---------------------------------------------------------------- esqueleto

ATRIBUTOS = {"id", "class", "href", "colspan", "rowspan", "datetime", "type"}
BORRAR = ["script", "style", "noscript", "meta", "link", "svg", "template", "iframe", "img"]
# Texto que se conserva entero: encabezados y etiquetas de la página, no lo que escribió alguien.
ETIQUETAS = {"th", "dt", "label", "legend", "caption"}
# Palabras que se conservan dentro de cualquier texto: sirven para entender las fechas.
PALABRAS = {
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
    "octubre", "noviembre", "diciembre", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep",
    "sept", "set", "oct", "nov", "dic", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
    "domingo", "lun", "mie", "jue", "vie", "sab", "dom", "de", "del", "a", "las", "el", "la", "hrs", "hr",
    "am", "pm", "hoy", "ayer", "persona", "ejemplo", "cl",
}
CURSO_RE = re.compile(r"^/(?P<inst>[a-z]+)/(?P<anio>\d{4})/(?P<sem>\d)/(?P<codigo>[A-Za-z0-9]+)/(?P<sec>\d+)(?=/|$)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RUT_RE = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b")
FONO_RE = re.compile(r"\+?\b56\s?9?\s?\d{4}\s?\d{4}\b|\b9\s?\d{4}\s?\d{4}\b")
SEGMENTO_RE = re.compile(r"^[a-z0-9_]{1,32}$")  # servicios, ids y el hash falso


def _sin_tildes(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


class _Esqueleto:
    def __init__(self) -> None:
        self.codigos: dict[str, str] = {}
        self.externos: dict[str, str] = {}

    def codigo(self, real: str) -> str:
        return self.codigos.setdefault(real, f"CURSO{len(self.codigos) + 1}")

    def datos(self, texto: str) -> str:
        """Correos, RUT, teléfonos y códigos de curso -> valores falsos."""
        texto = EMAIL_RE.sub("persona@ejemplo.cl", texto)
        texto = RUT_RE.sub("11.111.111-1", texto)
        texto = FONO_RE.sub("+56 9 1111 1111", texto)
        for real, falso in self.codigos.items():
            texto = re.sub(rf"\b{re.escape(real)}\b", falso, texto)
        return texto

    def tapar(self, texto: str) -> str:
        """Texto escrito por alguien -> letras cambiadas por x, salvo números y palabras de fechas."""

        def palabra(m: re.Match) -> str:
            w = m.group(0)
            if _sin_tildes(w) in PALABRAS or re.fullmatch(r"CURSO\d*", w):
                return w
            return "".join("X" if c.isupper() else "x" for c in w)

        return re.sub(r"[^\W\d_]+", palabra, self.datos(texto))

    def href(self, href: str) -> str:
        if href.startswith("mailto:"):
            return "mailto:persona@ejemplo.cl"
        if href.startswith(("#", "javascript:")):
            return "#"
        u = urlparse(href)
        if u.hostname and u.hostname not in ("www.u-cursos.cl", "u-cursos.cl"):
            return self.externos.setdefault(href, f"https://ejemplo.cl/enlace-{len(self.externos) + 1}")
        ruta = HASH_RE.sub(FALSO, u.path)
        fijos = 0  # segmentos que no se revisan: /inst/año/sem/CURSOn/sección
        if m := CURSO_RE.match(ruta):
            ruta = f"/{m['inst']}/{m['anio']}/{m['sem']}/{self.codigo(m['codigo'])}/{m['sec']}" + ruta[m.end():]
            fijos = 6
        partes = []
        for i, seg in enumerate(ruta.split("/")):
            if i < fijos or not seg or seg in (".", "..") or SEGMENTO_RE.match(seg):
                partes.append(seg)
            elif "." in seg:
                partes.append("archivo." + seg.rsplit(".", 1)[1][:5])
            else:
                partes.append("x")
        prefijo = f"{u.scheme}://{u.hostname}" if u.hostname else ""
        return prefijo + "/".join(partes) + (f"?{u.query}" if u.query else "")  # anonimizar ya le sacó los tokens

    def __call__(self, html: str) -> str:
        soup = BeautifulSoup(anonimizar(html), "html.parser")
        for basura in soup.find_all(BORRAR):
            basura.decompose()
        for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
            c.extract()
        # Primero se recorren los links: así los códigos de curso ya se conocen al tapar el texto.
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr not in ATRIBUTOS:
                    del tag[attr]
            if tag.has_attr("href"):
                tag["href"] = self.href(tag["href"])
        for s in soup.find_all(string=True):
            if not isinstance(s, NavigableString) or isinstance(s, Comment) or not s.strip():
                continue
            es_etiqueta = any(p.name in ETIQUETAS for p in s.parents) or (len(s.strip()) <= 40 and s.strip().endswith(":"))
            s.replace_with(self.datos(s) if es_etiqueta else self.tapar(s))
        return str(soup)


HASH32_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")
# Ids internos (cursos, mensajes, instituciones): con ellos se puede saber qué ramos tomas.
# semana-AAAASS es año y semana del calendario: no identifica a nadie y el parser lo necesita.
ID_NUMERICO_RE = re.compile(r"(?<!semana-)(?<!\d)\d{5,}(?!\d)")
ATRIBUTO_RE = re.compile(r'\b(id|class|href)="([^"]*)"')


def limpiar_ids(html: str) -> str:
    """Hashes de usuario (en links, clases o donde sea) -> 000...0 e ids numéricos largos de los
    atributos -> números falsos, siempre el mismo para el mismo id (así se ve qué responde a qué)."""
    falsos: dict[str, str] = {}

    def numero(m: re.Match) -> str:
        n = m.group(0)
        return n if set(n) == {"0"} else falsos.setdefault(n, str(10001 + len(falsos)))

    def atributo(m: re.Match) -> str:
        return f'{m.group(1)}="{ID_NUMERICO_RE.sub(numero, m.group(2))}"'

    return ATRIBUTO_RE.sub(atributo, HASH32_RE.sub("0" * 32, html))


def esqueleto(html: str) -> str:
    """Página -> solo su estructura, apta para publicar (ver el docstring del módulo)."""
    return limpiar_ids(_Esqueleto()(html))


def sospechosos(html: str) -> list[str]:
    """Correos, RUT o hashes de usuario que hayan sobrevivido (no debería haber ninguno)."""
    encontrados = EMAIL_RE.findall(html) + RUT_RE.findall(html) + HASH32_RE.findall(html)
    return [x for x in encontrados if x not in ("persona@ejemplo.cl", "11.111.111-1", "0" * 32)]


def _guardar_esqueleto(nombre: str, html: str) -> None:
    ESQUELETOS.mkdir(parents=True, exist_ok=True)
    destino = ESQUELETOS / f"{nombre}.html"
    out = esqueleto(html)
    destino.write_text(out, encoding="utf-8")
    print(f"Esqueleto en {destino}")
    if raros := sospechosos(out):
        print(f"  OJO: quedaron datos que parecen correos o RUT: {', '.join(sorted(set(raros)))}. Bórralos antes de subirlo.")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--esqueleto":
        archivos = [Path(a) for a in sys.argv[2:]] or sorted(FIXTURES.glob("*.html"))
        if not archivos:
            print(f"No hay archivos .html en {FIXTURES}.")
        for archivo in archivos:
            _guardar_esqueleto(archivo.stem, archivo.read_text(encoding="utf-8"))
        return
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    ruta, nombre = sys.argv[1], sys.argv[2]

    from ucursos_mcp.client import UCursosClient

    client = UCursosClient()
    ruta = ruta.replace("/usuario/me/", f"/usuario/{client.user_id}/")
    if not ruta.startswith("/"):
        ruta = "/" + ruta

    crudo = client.get_html(ruta)
    html = anonimizar(crudo)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    destino = FIXTURES / f"{nombre}.html"
    destino.write_text(html, encoding="utf-8")
    print(f"Guardado en {destino} ({len(html):,} caracteres). Queda solo en tu PC.")
    _guardar_esqueleto(nombre, crudo)


if __name__ == "__main__":
    main()

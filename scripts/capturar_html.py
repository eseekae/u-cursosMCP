"""
Captura una página de U-Cursos con tu sesión y la guarda anonimizada como fixture de test.

Uso:
    uv run python scripts/capturar_html.py <ruta> <nombre>

Ejemplos:
    uv run python scripts/capturar_html.py /usuario/me/tareas_usuario/ tareas_usuario
    uv run python scripts/capturar_html.py ingenieria/2026/2/CC1002/7/notas/ notas

`/usuario/me/` se reemplaza por tu hash real. Guarda en tests/fixtures/<nombre>.html.

Anonimización (revisa igual el archivo antes de commitearlo):
  - hashes de usuario (/usuario/<hash32>/) -> 000...0
  - query strings con tokens (csrf, etc.) -> se eliminan
  - nombres en links a perfiles de usuario -> "Persona N"
  - scripts inline -> se eliminan (pueden traer tokens)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from ucursos_mcp.client import UCursosClient

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
HASH_RE = re.compile(r"/usuario/[0-9a-f]{32}/")
FALSO = "/usuario/" + "0" * 32 + "/"


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
        a["href"] = href.split("?")[0]

    for tag in soup.find_all(["form", "input"]):
        for attr in ("action", "value"):
            if tag.has_attr(attr) and len(str(tag[attr])) > 20:
                tag[attr] = ""

    out = HASH_RE.sub(FALSO, str(soup))
    # Nombres de personas que aparecen como texto suelto fuera de los links.
    for real, falso in personas.items():
        out = out.replace(real, falso)
    return out


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    ruta, nombre = sys.argv[1], sys.argv[2]

    client = UCursosClient()
    ruta = ruta.replace("/usuario/me/", f"/usuario/{client.user_id}/")
    if not ruta.startswith("/"):
        ruta = "/" + ruta

    html = anonimizar(client.get_html(ruta))
    FIXTURES.mkdir(parents=True, exist_ok=True)
    destino = FIXTURES / f"{nombre}.html"
    destino.write_text(html, encoding="utf-8")
    print(f"Guardado en {destino} ({len(html):,} caracteres). Revísalo antes de commitear.")


if __name__ == "__main__":
    main()

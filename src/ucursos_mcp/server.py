"""
Capa MCP: expone tools de SOLO LECTURA sobre U-Cursos.

Patrón Facade (SDK mcp 2.x, MCPServer): Claude solo ve funciones simples (listar_cursos, notas, ...);
el login, el HTTP y el parseo quedan escondidos en auth/client/parsers.

Transporte stdio: el servidor corre local y las cookies nunca salen de tu PC.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from . import auth, documentos, parsers
from .auth import SESSION_PATH
from .client import SessionExpired, UCursosClient

INSTRUCCIONES = """\
Acceso de solo lectura a U-Cursos, la plataforma de cursos de la Universidad de Chile.
Solo funciona con los cursos en que el usuario está inscrito.

Primer paso siempre: listar_cursos. Devuelve el `path` de cada curso
(ej. 'ingenieria/2026/2/CC1002/7' = institución/año/semestre/código/sección), que piden
las demás tools. Si el usuario nombra un ramo ("cálculo", "MA2001"), búscalo en esa lista.

Dónde está cada cosa:
- tareas: tareas de TODOS los cursos con fecha límite y estado. Para "¿qué tengo pendiente?".
- novedades: anuncios del equipo docente (cambios de fecha, materia de controles, avisos).
- material_docente: lista de archivos del curso (apuntes, guías, pautas, enunciados).
- leer_material: el texto de un archivo de esa lista. Úsalo para estudiar, resumir o
  responder preguntas sobre el contenido del ramo.
- notas: notas publicadas del curso.

Cómo responder según lo que pidan:
- "¿Qué entra en el control/examen?": novedades primero (suele anunciarse ahí) y luego
  material_docente para ubicar las clases o guías que correspondan.
- "Ayúdame a estudiar X" o "explícame la materia": material_docente para elegir los
  archivos relevantes por título y fecha, y leer_material para leerlos. Cita de qué archivo
  y página sale cada cosa.
- "¿Cómo voy en el ramo?": notas, y si sirve, tareas.
- "¿Qué tengo esta semana?": tareas y novedades de los cursos que correspondan.

Reglas:
- Si algo no está en U-Cursos, dilo. No inventes fechas, notas ni contenidos.
- Lee solo lo necesario: no recorras todos los cursos ni todos los archivos si no te lo piden.
- Es solo lectura: no puedes entregar tareas, publicar ni enviar nada. Si te lo piden, explícalo.
- Si una tool dice que no hay sesión o que expiró, llama a iniciar_sesion: abre U-Cursos en
  el navegador normal del usuario para que inicie sesión él mismo (su clave nunca pasa por ti).
  Espera a que el usuario diga que ya entró y llama a estado_sesion, que importa esa sesión.
"""

mcp = MCPServer("ucursos", instructions=INSTRUCCIONES)

# Ninguna tool modifica U-Cursos. Las que escriben en el disco local (descargas, archivo
# de sesión) no se marcan readOnly, pero tampoco son destructivas.
SOLO_LECTURA = ToolAnnotations(read_only_hint=True, open_world_hint=True)
ESCRIBE_LOCAL = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True)


def errores_legibles(fn):
    """Convierte fallas esperables en ToolError.

    Sin esto el SDK trata cualquier excepción como crash y Claude solo ve
    "Error executing tool X", sin saber que tiene que pedirte `ucursos-login`.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SessionExpired as e:
            raise ToolError(f"{e} Llama a iniciar_sesion para que el usuario vuelva a entrar.") from e
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (401, 403):
                raise ToolError(f"U-Cursos negó el acceso ({code}) a {e.request.url.path}: el usuario no tiene permiso para ver eso.") from e
            if code == 404:
                raise ToolError(f"No existe {e.request.url.path} (404). Revisa el curso_path con listar_cursos.") from e
            raise ToolError(f"U-Cursos respondió {code} en {e.request.url.path}.") from e
        except httpx.TransportError as e:
            raise ToolError(f"No se pudo conectar con U-Cursos: {e}") from e

    return wrapper


DESCARGAS_DIR = Path(os.environ.get("UCURSOS_DESCARGAS", Path.home() / "Downloads" / "U-Cursos"))

_client: UCursosClient | None = None
_client_mtime: float | None = None


def client() -> UCursosClient:
    """Cliente perezoso: se crea en la primera llamada, así el server arranca aunque no haya sesión.

    Si el archivo de sesión cambió (el usuario volvió a iniciar sesión), se recrea con las cookies nuevas.
    """
    global _client, _client_mtime
    mtime = SESSION_PATH.stat().st_mtime if SESSION_PATH.exists() else None
    if _client is None or mtime != _client_mtime:
        _client = UCursosClient(SESSION_PATH)
        _client_mtime = mtime
    return _client


_inscritos: tuple[UCursosClient, set[str]] | None = None


def curso_inscrito(curso_path: str) -> str:
    """Normaliza curso_path y verifica que sea un curso donde el usuario está inscrito.

    La lista se pide una vez por sesión (se vuelve a pedir si el usuario inicia sesión de nuevo).
    """
    global _inscritos
    c = client()
    if _inscritos is None or _inscritos[0] is not c:
        _inscritos = (c, {x.path for x in parsers.parse_cursos(c.home())})
    path = curso_path.strip("/")
    if path not in _inscritos[1]:
        raise ToolError(f"'{path}' no está entre los cursos inscritos del usuario. Usa listar_cursos para ver los paths válidos.")
    return path


def ruta_descarga(path: str, descarga: str) -> str:
    """Ruta de descarga dentro del curso. Rechaza links a otros sitios o a otros cursos."""
    if descarga.startswith(("http://", "https://")):
        u = urlparse(descarga)
        if u.hostname not in ("www.u-cursos.cl", "u-cursos.cl"):
            raise ToolError("Solo se permiten descargas desde u-cursos.cl.")
        ruta = u.path + (f"?{u.query}" if u.query else "")
    elif descarga.startswith("/"):
        ruta = descarga
    else:
        ruta = f"/{path}/material_docente/{descarga}"
    if not ruta.startswith(f"/{path}/"):
        raise ToolError("Ese archivo no pertenece al curso indicado. Usa el campo `descarga` de material_docente.")
    return ruta


@mcp.tool(annotations=ESCRIBE_LOCAL)
def iniciar_sesion() -> str:
    """Abre U-Cursos en el navegador normal del usuario (Edge, Chrome, Firefox...) para que entre.

    Úsala cuando otra tool diga que no hay sesión o que expiró. El usuario inicia sesión él
    mismo en su navegador de siempre; su clave nunca pasa por ti. No se automatiza el navegador.
    Después de abrirlo, pídele al usuario que te avise cuando ya esté dentro y llama a
    estado_sesion, que importa esa sesión desde el navegador.
    """
    auth.abrir_ucursos()
    return (
        "Se abrió U-Cursos en el navegador por defecto del usuario. Pídele que inicie sesión ahí "
        "como lo hace siempre (su cuenta UChile) y que te avise cuando ya esté dentro; después "
        "llama a estado_sesion para importar la sesión."
    )


@mcp.tool(annotations=ESCRIBE_LOCAL)
@errores_legibles
def estado_sesion() -> str:
    """Importa la sesión desde el navegador del usuario y dice si quedó activa.

    Llámala después de iniciar_sesion (cuando el usuario avise que ya entró) o si una tool
    dice que la sesión expiró: vuelve a leer las cookies del navegador y revalida.
    """
    global _client_mtime
    try:
        n = auth.importar_sesion()
    except auth.LoginError as e:
        raise ToolError(str(e)) from e
    _client_mtime = None  # fuerza recrear el cliente con las cookies nuevas
    try:
        client().user_id  # lanza SessionExpired si las cookies no sirven (no entró o caducaron)
    except SessionExpired as e:
        raise ToolError(
            f"Importé {n} cookies del navegador, pero U-Cursos no las reconoce. "
            "¿El usuario terminó de iniciar sesión? Que entre en el navegador y vuelve a llamarme."
        ) from e
    return "Sesión activa. Ya puedes usar las demás tools."


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def listar_cursos() -> list[dict]:
    """Cursos y comunidades donde estás inscrito. El campo `path` se usa en las demás tools."""
    return [c.model_dump() for c in parsers.parse_cursos(client().home())]


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def tareas(solo_pendientes: bool = True) -> list[dict]:
    """Tareas de todos tus cursos con fecha límite y estado. Por defecto solo las que están en plazo."""
    ts = parsers.parse_tareas_usuario(client().tareas_usuario())
    if solo_pendientes:
        ts = [t for t in ts if "plazo" in t.estado.lower()]
    return [t.model_dump() for t in ts]


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def notas(curso_path: str) -> list[dict]:
    """Tablas de notas de un curso. curso_path ej: 'ingenieria/2026/2/CC1002/7'."""
    html = client().servicio_curso(curso_inscrito(curso_path), "notas")
    return [t.model_dump() for t in parsers.parse_notas(html)]


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def material_docente(curso_path: str) -> list[dict]:
    """Lista el material docente de un curso (título, autor, fecha y campo `descarga`).

    Para leer el contenido de un archivo, pasa su `descarga` a leer_material.
    """
    html = client().servicio_curso(curso_inscrito(curso_path), "material_docente")
    return [m.model_dump() for m in parsers.parse_material(html)]


MAX_CARACTERES = 50_000


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def leer_material(curso_path: str, descarga: str, desde: int = 0, max_caracteres: int = 20_000) -> dict:
    """Lee el texto de un archivo de material docente (PDF, Word .docx, PowerPoint .pptx o texto).

    `descarga` es el campo del mismo nombre que devuelve material_docente. Los documentos
    largos vienen por partes: si `quedan` > 0, vuelve a llamar con `desde` = `siguiente_desde`.
    Los PDF marcan cada página con "--- Página N ---" para que puedas citarla.
    """
    path = curso_inscrito(curso_path)
    contenido, nombre = client().get_bytes(ruta_descarga(path, descarga))
    try:
        tipo, texto = documentos.extraer_texto(nombre, contenido)
    except documentos.DocumentoNoLegible as e:
        raise ToolError(str(e)) from e
    desde = max(0, desde)
    max_caracteres = min(max(1, max_caracteres), MAX_CARACTERES)
    parte = texto[desde : desde + max_caracteres]
    fin = desde + len(parte)
    return {
        "archivo": nombre,
        "tipo": tipo,
        "total_caracteres": len(texto),
        "desde": desde,
        "texto": parte,
        "quedan": len(texto) - fin,
        "siguiente_desde": fin if fin < len(texto) else None,
    }


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def novedades(curso_path: str, limite: int = 10) -> list[dict]:
    """Últimas novedades (anuncios del equipo docente) publicadas en un curso."""
    html = client().servicio_curso(curso_inscrito(curso_path), "novedades")
    return [n.model_dump() for n in parsers.parse_novedades(html, limite)]


@mcp.tool(annotations=ESCRIBE_LOCAL)
@errores_legibles
def descargar_material(curso_path: str, descarga: str) -> str:
    """Descarga un archivo de material docente a la carpeta Descargas/U-Cursos del usuario.

    `descarga` es el campo del mismo nombre que devuelve material_docente. Para leer el
    contenido usa leer_material; esta tool es para cuando el usuario quiere el archivo.
    """
    path = curso_inscrito(curso_path)
    contenido, nombre = client().get_bytes(ruta_descarga(path, descarga))
    DESCARGAS_DIR.mkdir(parents=True, exist_ok=True)
    destino = DESCARGAS_DIR / Path(nombre or "material.bin").name  # .name evita path traversal
    destino.write_bytes(contenido)
    return str(destino.resolve())


def main() -> None:
    mcp.run()  # stdio por defecto


if __name__ == "__main__":
    main()

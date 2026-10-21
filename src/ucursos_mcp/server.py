"""
Capa MCP: expone tools de SOLO LECTURA sobre U-Cursos.

Patrón Facade (SDK mcp 2.x, MCPServer): Claude solo ve funciones simples (listar_cursos, notas, ...);
el login, el HTTP y el parseo quedan escondidos en auth/client/parsers.

Transporte stdio: el servidor corre local y las cookies nunca salen de tu PC.
"""

from __future__ import annotations

import functools
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from . import documentos, parsers
from .auth import DATA_DIR, LOGIN_LOG, SESSION_PATH
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
- Si una tool dice que no hay sesión o que expiró, llama a iniciar_sesion: se abre una
  ventana de Edge o Chrome donde el usuario escribe su clave (tú nunca la ves). Espera a que
  el usuario diga que terminó y llama a estado_sesion antes de reintentar.
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
_login_proc: subprocess.Popen | None = None


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


def _login_en_curso() -> bool:
    return _login_proc is not None and _login_proc.poll() is None


def _cola_log(n: int = 5) -> str:
    try:
        return "\n".join(LOGIN_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


@mcp.tool(annotations=ESCRIBE_LOCAL)
def iniciar_sesion() -> str:
    """Abre una ventana de Edge o Chrome en el computador del usuario para que entre a U-Cursos.

    Úsala cuando otra tool diga que no hay sesión o que expiró. El usuario escribe su clave y
    resuelve el reCAPTCHA en esa ventana; tú nunca la ves. Vuelve de inmediato, sin esperar
    el login: pídele al usuario que te avise cuando termine y luego llama a estado_sesion.
    """
    global _login_proc
    if _login_en_curso():
        return "Ya hay una ventana de login abierta. Pídele al usuario que termine de entrar ahí."

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # sin consola negra en Windows
    with open(LOGIN_LOG, "w", encoding="utf-8") as log:
        # Proceso aparte: el login puede tardar minutos y no debe bloquear el server.
        # stdin/stdout nunca se heredan, porque son el canal MCP con Claude.
        _login_proc = subprocess.Popen(
            [sys.executable, "-m", "ucursos_mcp.auth"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=flags,
        )
    return (
        "Se abrió una ventana del navegador con U-Cursos. Pídele al usuario que inicie sesión ahí "
        "(tiene 5 minutos) y que te avise cuando termine; después llama a estado_sesion."
    )


@mcp.tool(annotations=SOLO_LECTURA)
@errores_legibles
def estado_sesion() -> str:
    """Dice si hay una sesión de U-Cursos válida. Úsala después de iniciar_sesion o si una tool falla."""
    if _login_en_curso():
        return "El login sigue en curso: el usuario todavía no termina de entrar en la ventana del navegador."
    if _login_proc is not None and _login_proc.returncode not in (0, None):
        return f"El último intento de login falló. Detalle:\n{_cola_log()}\nPuedes llamar a iniciar_sesion de nuevo."
    if not SESSION_PATH.exists():
        return "No hay sesión guardada. Llama a iniciar_sesion."
    client().user_id  # lanza SessionExpired si las cookies ya no sirven
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

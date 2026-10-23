"""
Capa de transporte: sesión HTTP autenticada contra U-Cursos.

Responsabilidades (y nada más):
  - Cargar las cookies guardadas por auth.py.
  - Pedir páginas y decodificarlas bien (U-Cursos responde en ISO-8859-1,
    si se decodifica como UTF-8 los tildes y la ñ salen rotos).
  - Detectar sesión expirada y avisar con un error claro.

No sabe nada de HTML: eso es trabajo de parsers.py.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from .auth import BASE_URL, SESSION_PATH

USER_ID_RE = re.compile(r"/usuario/([0-9a-f]{32})/(?:mis_canales|todos_cursos|tareas_usuario)/")
URL_USUARIO_RE = re.compile(r"/usuario/([0-9a-f]{32})/")

# Pausa mínima entre requests: somos un cliente educado, no un crawler.
MIN_INTERVAL_S = 0.5


class SessionExpired(RuntimeError):
    """La sesión guardada ya no sirve: hay que volver a entrar (tool iniciar_sesion o `ucursos-login`)."""


class UsuarioNoEncontrado(SessionExpired):
    """La portada cargó sin pedir login, pero no se reconoció al usuario (¿cambió el HTML?)."""


class UCursosClient:
    def __init__(self, session_path: Path = SESSION_PATH, cookies: list[dict] | None = None) -> None:
        """Usa las cookies guardadas en `session_path`, o la lista `cookies` si se entrega
        (estado_sesion la usa para probar un navegador antes de guardar su sesión)."""
        if cookies is None:
            if not session_path.exists():
                raise SessionExpired(
                    f"No hay sesión guardada en {session_path}."
                )
            cookies = json.loads(session_path.read_text(encoding="utf-8")).get("cookies", [])
        self._http = httpx.Client(
            base_url=BASE_URL,
            cookies=self._jar(cookies),
            headers={"User-Agent": "ucursos-mcp/0.1 (uso personal, solo lectura)"},
            follow_redirects=True,
            timeout=20,
        )
        self._last_request = 0.0
        self._user_id: str | None = None

    # ---------- utilidades internas ----------

    @staticmethod
    def _jar(cookies: list[dict]) -> httpx.Cookies:
        """Convierte la lista de cookies (formato storage_state) en cookies de httpx."""
        jar = httpx.Cookies()
        for c in cookies:
            jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        return jar

    def close(self) -> None:
        self._http.close()

    def _throttle(self) -> None:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    # ---------- API pública ----------

    def _get_pagina(self, path: str) -> tuple[str, str]:
        """GET a una ruta de U-Cursos. Devuelve (HTML decodificado, URL final tras redirecciones)."""
        self._throttle()
        resp = self._http.get(path)
        resp.raise_for_status()

        # Sin sesión, U-Cursos puede mandarnos al login de Cuenta UChile.
        host = resp.url.host or ""
        if not host.endswith("u-cursos.cl"):
            raise SessionExpired(f"U-Cursos redirigió al inicio de sesión ({host}): la sesión no es válida.")

        # El servidor manda Latin-1; respetamos el charset si viene, si no forzamos.
        resp.encoding = resp.charset_encoding or "iso-8859-1"
        html = resp.text

        # Si aparece el botón de login, la sesión murió.
        if 'id="boton_login"' in html:
            raise SessionExpired("La sesión de U-Cursos expiró.")
        return html, str(resp.url)

    def get_html(self, path: str) -> str:
        """GET a una ruta de U-Cursos. Devuelve el HTML ya decodificado."""
        return self._get_pagina(path)[0]

    def get_bytes(self, path: str) -> tuple[bytes, str | None]:
        """Descarga binaria (material docente). Devuelve (contenido, nombre_sugerido)."""
        self._throttle()
        resp = self._http.get(path)
        resp.raise_for_status()
        disp = resp.headers.get("content-disposition", "")
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disp)
        return resp.content, (m.group(1) if m else None)

    @property
    def user_id(self) -> str:
        """Hash de 32 caracteres que identifica al usuario en las URLs (/usuario/<hash>/)."""
        if self._user_id is None:
            html, url = self._get_pagina("/")
            # Con sesión, la portada suele redirigir a /usuario/<hash>/; si no, buscamos los links.
            m = URL_USUARIO_RE.search(url) or USER_ID_RE.search(html)
            if not m:
                raise UsuarioNoEncontrado(
                    "La portada cargó sin botón de login, pero no encontré el link /usuario/<hash>/. "
                    "Puede que U-Cursos cambió su HTML (skill arreglar-parser)."
                )
            self._user_id = m.group(1)
        return self._user_id

    # Atajos a las vistas que mapeamos en el reconocimiento.
    def home(self) -> str:
        return self.get_html(f"/usuario/{self.user_id}/mis_canales/")

    def tareas_usuario(self) -> str:
        return self.get_html(f"/usuario/{self.user_id}/tareas_usuario/")

    def horario(self) -> str:
        return self.get_html(f"/usuario/{self.user_id}/horario/")

    def servicio_curso(self, curso_path: str, servicio: str) -> str:
        """curso_path ej: 'ingenieria/2026/2/CC1002/7'. servicio ej: 'notas', 'material_docente'."""
        return self.get_html(f"/{curso_path.strip('/')}/{servicio.strip('/')}/")


def validar_cookies(cookies: list[dict]) -> str | None:
    """Prueba unas cookies contra U-Cursos. None si sirven; si no, el motivo en palabras simples."""
    try:
        c = UCursosClient(cookies=cookies)
    except SessionExpired as e:
        return str(e)
    try:
        _ = c.user_id  # lanza si U-Cursos no reconoce las cookies
    except UsuarioNoEncontrado as e:
        return str(e)
    except SessionExpired:
        return "respondió con la página de inicio de sesión (cookies vencidas o de una sesión cerrada)"
    except httpx.HTTPError as e:
        return f"no pude conectar con U-Cursos ({type(e).__name__})"
    finally:
        c.close()
    return None

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

# Pausa mínima entre requests: somos un cliente educado, no un crawler.
MIN_INTERVAL_S = 0.5


class SessionExpired(RuntimeError):
    """La sesión guardada ya no sirve: hay que volver a entrar (tool iniciar_sesion o `ucursos-login`)."""


class UCursosClient:
    def __init__(self, session_path: Path = SESSION_PATH) -> None:
        if not session_path.exists():
            raise SessionExpired(
                f"No hay sesión guardada en {session_path}."
            )
        self._http = httpx.Client(
            base_url=BASE_URL,
            cookies=self._load_cookies(session_path),
            headers={"User-Agent": "ucursos-mcp/0.1 (uso personal, solo lectura)"},
            follow_redirects=True,
            timeout=20,
        )
        self._last_request = 0.0
        self._user_id: str | None = None

    # ---------- utilidades internas ----------

    @staticmethod
    def _load_cookies(path: Path) -> httpx.Cookies:
        """Convierte el storage_state de Playwright en cookies de httpx."""
        state = json.loads(path.read_text(encoding="utf-8"))
        jar = httpx.Cookies()
        for c in state.get("cookies", []):
            jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        return jar

    def _throttle(self) -> None:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    # ---------- API pública ----------

    def get_html(self, path: str) -> str:
        """GET a una ruta de U-Cursos. Devuelve el HTML ya decodificado."""
        self._throttle()
        resp = self._http.get(path)
        resp.raise_for_status()

        # El servidor manda Latin-1; respetamos el charset si viene, si no forzamos.
        resp.encoding = resp.charset_encoding or "iso-8859-1"
        html = resp.text

        # Si aparece el botón de login, la sesión murió.
        if 'id="boton_login"' in html:
            raise SessionExpired("La sesión de U-Cursos expiró.")
        return html

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
            m = USER_ID_RE.search(self.get_html("/"))
            if not m:
                raise SessionExpired("No se encontró el usuario en la portada. ¿Sesión válida?")
            self._user_id = m.group(1)
        return self._user_id

    # Atajos a las vistas que mapeamos en el reconocimiento.
    def home(self) -> str:
        return self.get_html(f"/usuario/{self.user_id}/mis_canales/")

    def tareas_usuario(self) -> str:
        return self.get_html(f"/usuario/{self.user_id}/tareas_usuario/")

    def servicio_curso(self, curso_path: str, servicio: str) -> str:
        """curso_path ej: 'ingenieria/2026/2/CC1002/7'. servicio ej: 'notas', 'material_docente'."""
        return self.get_html(f"/{curso_path.strip('/')}/{servicio.strip('/')}/")

"""
Login manual con navegador visible (Playwright) y persistencia de sesión.

Por qué así:
  - U-Cursos delega el login en Cuenta UChile (OAuth2/OIDC en oauth2.uchile.cl)
    y esa página tiene reCAPTCHA, así que automatizar usuario+clave no es viable.
  - Tu clave NUNCA pasa por este código: tú la escribes en la ventana del navegador.
  - Al terminar se guardan solo las cookies (storage_state) en tu carpeta de usuario.

Se usa el Edge o Chrome que ya tienes instalado (channel de Playwright), así que no
hay que descargar ningún navegador. Hay dos formas de abrirlo:
    ucursos-login            # desde la terminal
    tool iniciar_sesion      # desde Claude, sin terminal (lanza este mismo módulo)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BASE_URL = "https://www.u-cursos.cl"

# Datos locales del usuario. Fuera del repo y fuera de la carpeta de la extensión,
# para que la sesión sobreviva a una actualización de la extensión.
DATA_DIR = Path(os.environ.get("UCURSOS_DATA", Path.home() / ".ucursos-mcp"))
SESSION_PATH = Path(os.environ.get("UCURSOS_SESSION", DATA_DIR / "ucursos.storage_state.json"))
LOGIN_LOG = DATA_DIR / "login.log"

# Navegadores a probar, en orden. Edge viene con Windows; Chrome es lo típico en Mac.
# Chromium "pelado" suele gatillar el reCAPTCHA, por eso no está en la lista.
_canal_env = os.environ.get("UCURSOS_BROWSER_CHANNEL")
BROWSER_CHANNELS = [_canal_env] if _canal_env else ["msedge", "chrome"]

# Tras el login, U-Cursos redirige a /usuario/<hash32>/... : esa es la señal de éxito.
LOGGED_IN_URL = re.compile(r"/usuario/[0-9a-f]{32}/")

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutos para escribir la clave y resolver el captcha


def _abrir_navegador(p):
    """Lanza el primer navegador instalado de BROWSER_CHANNELS."""
    errores = []
    for canal in BROWSER_CHANNELS:
        try:
            return p.chromium.launch(headless=False, channel=canal)
        except Exception as exc:  # noqa: BLE001 (probamos el siguiente)
            errores.append(f"{canal}: {exc}")
    raise RuntimeError(
        "No encontré Microsoft Edge ni Google Chrome instalados. Instala uno de los dos.\n"
        + "\n".join(errores)
    )


def login_interactivo(session_path: Path = SESSION_PATH) -> Path:
    """Abre un navegador visible, espera a que el usuario inicie sesión y guarda las cookies."""
    from playwright.sync_api import sync_playwright  # import diferido: solo se necesita aquí

    session_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = _abrir_navegador(p)
        context = browser.new_context(locale="es-CL")
        page = context.new_page()
        page.goto(BASE_URL)

        print("Inicia sesión en la ventana del navegador (usuario, clave y reCAPTCHA).")
        print("Esperando hasta 5 minutos...")
        page.wait_for_url(LOGGED_IN_URL, timeout=LOGIN_TIMEOUT_MS)

        context.storage_state(path=str(session_path))
        browser.close()

    # Restringe permisos del archivo en sistemas tipo Unix (en Windows no aplica).
    try:
        session_path.chmod(0o600)
    except OSError:
        pass

    return session_path


def main() -> None:
    try:
        path = login_interactivo()
    except Exception as exc:  # noqa: BLE001 (CLI: mostramos el error y salimos)
        print(f"No se pudo completar el login: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Sesión guardada en {path}")


if __name__ == "__main__":
    main()

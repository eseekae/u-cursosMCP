"""
Login sin automatizar el navegador: tú entras a U-Cursos en tu navegador de siempre
(Edge, Chrome, Firefox, Brave...) como cualquier día, y el MCP lee esa sesión tuya que
ya quedó guardada en el navegador.

Por qué así:
  - U-Cursos entra por Cuenta UChile, con captcha. Un navegador abierto por un programa
    queda marcado como automatizado y el captcha lo bloquea. Aquí no se automatiza nada:
    inicias sesión tú, como humano, en tu navegador normal (donde el captcha ni aparece).
  - Tu clave NUNCA pasa por este código ni por Claude: la escribes en tu navegador.
  - El MCP solo lee las cookies del dominio de U-Cursos desde el navegador, igual que hace
    un gestor de contraseñas con tus propios datos. Nada sale de tu computador.

Flujo:
  1. iniciar_sesion (o `ucursos-login`) abre U-Cursos en tu navegador por defecto.
  2. Inicias sesión ahí, normal.
  3. estado_sesion importa las cookies desde el navegador y verifica que sirvan.

Variables de entorno:
  UCURSOS_BROWSER   fuerza un solo navegador: edge, chrome, firefox, brave, opera, vivaldi, chromium
"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from http.cookiejar import CookieJar
from pathlib import Path

BASE_URL = "https://www.u-cursos.cl"

# Datos locales del usuario. Fuera del repo y de la carpeta de la extensión, para que la
# sesión sobreviva a una actualización de la extensión.
DATA_DIR = Path(os.environ.get("UCURSOS_DATA", Path.home() / ".ucursos-mcp"))
SESSION_PATH = Path(os.environ.get("UCURSOS_SESSION", DATA_DIR / "ucursos.storage_state.json"))
LOGIN_LOG = DATA_DIR / "login.log"

# Dominios cuyas cookies forman la sesión (U-Cursos y el login de Cuenta UChile).
DOMINIOS_SESION = ("u-cursos.cl", "uchile.cl")

# Navegadores que browser_cookie3 sabe leer, en orden de preferencia.
NAVEGADORES = ("edge", "chrome", "brave", "vivaldi", "opera", "chromium", "firefox")


class LoginError(RuntimeError):
    """No se pudo importar la sesión (no hay cookies, navegador bloqueado, etc.)."""


# ---------------------------------------------------------------- abrir el navegador

def abrir_ucursos(url: str = BASE_URL) -> None:
    """Abre U-Cursos en el navegador por defecto del usuario. No automatiza nada."""
    webbrowser.open(url)


# ---------------------------------------------------------------- importar la sesión

def _cookies_de(navegador: str, dominio: str) -> CookieJar:
    import browser_cookie3

    fn = getattr(browser_cookie3, navegador)
    return fn(domain_name=dominio)


def _leer_cookies() -> list[dict]:
    """Junta las cookies de U-Cursos de todos los navegadores legibles.

    No falla si un navegador no está instalado o no se puede leer: simplemente lo salta.
    La validez real se comprueba después, haciendo una petición a U-Cursos.
    """
    forzado = os.environ.get("UCURSOS_BROWSER")
    navegadores = (forzado,) if forzado else NAVEGADORES

    por_nombre: dict[tuple[str, str], dict] = {}
    errores: list[str] = []
    encontrado_navegador = False
    for nav in navegadores:
        hubo = False
        for dominio in DOMINIOS_SESION:
            try:
                jar = _cookies_de(nav, dominio)
            except Exception as exc:  # noqa: BLE001 (navegador ausente o bloqueado: seguimos)
                errores.append(f"{nav}/{dominio}: {exc}")
                continue
            encontrado_navegador = True
            for c in jar:
                hubo = True
                por_nombre[(c.name, c.domain)] = {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path or "/",
                    "secure": bool(c.secure),
                    "expires": c.expires if c.expires else -1,
                }
        if hubo and forzado is None:
            # Ya encontramos cookies en el navegador más preferente: no mezclamos con otros.
            break

    if not encontrado_navegador:
        LOGIN_LOG.parent.mkdir(parents=True, exist_ok=True)
        LOGIN_LOG.write_text("\n".join(errores), encoding="utf-8")
        raise LoginError(
            "No pude leer cookies de ningún navegador (Edge, Chrome, Firefox...). "
            "Detalle guardado en login.log. Si usas Windows con Chrome o Edge muy nuevos, "
            "prueba iniciar sesión en Firefox, o define UCURSOS_BROWSER=firefox."
        )
    return list(por_nombre.values())


def importar_sesion(session_path: Path = SESSION_PATH) -> int:
    """Lee la sesión desde el navegador y la guarda. Devuelve cuántas cookies encontró."""
    cookies = _leer_cookies()
    if not cookies:
        raise LoginError(
            "No encontré cookies de U-Cursos en tu navegador. Abre U-Cursos (iniciar_sesion), "
            "inicia sesión y vuelve a intentar."
        )
    estado = {"cookies": cookies, "origins": []}

    # Escritura atómica: el server recarga la sesión cuando cambia este archivo.
    session_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = session_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado), encoding="utf-8")
    try:
        tmp.chmod(0o600)  # en Windows no aplica
    except OSError:
        pass
    tmp.replace(session_path)
    return len(cookies)


def main() -> None:
    """CLI `ucursos-login`: abre U-Cursos, espera a que entres y luego importa la sesión."""
    abrir_ucursos()
    print("Se abrió U-Cursos en tu navegador. Inicia sesión ahí.")
    try:
        input("Cuando ya estés dentro, vuelve aquí y presiona Enter...")
    except EOFError:
        pass
    try:
        n = importar_sesion()
    except Exception as exc:  # noqa: BLE001 (CLI: mostramos el error y salimos)
        print(f"No se pudo importar la sesión: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Sesión guardada ({n} cookies) en {SESSION_PATH}")


if __name__ == "__main__":
    main()

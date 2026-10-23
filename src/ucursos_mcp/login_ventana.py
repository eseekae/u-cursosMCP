"""
Inicio de sesión en una ventana propia: la forma habitual de entrar a U-Cursos.

Se abre una ventana (WebView2 en Windows) con U-Cursos. El usuario escribe su clave y resuelve
el captcha él mismo, como en cualquier navegador. Este módulo SOLO mira la URL y, cuando el
usuario ya está dentro (/usuario/<hash>/), lee las cookies de la ventana, las valida contra
U-Cursos y las guarda. No escribe credenciales, no toca el captcha ni controla la página.

La ventana corre en un proceso aparte (`ucursos-mcp ventana-login`) porque necesita el hilo
principal y el server MCP usa stdio: así nada de la interfaz toca la conexión con la IA.

Si la ventana no se puede abrir (falta pywebview o el sistema no tiene motor web), sale con
SALIDA_NO_DISPONIBLE y quien la llamó cae al navegador del usuario (auth.py).
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import auth

# Códigos de salida del proceso de la ventana.
SALIDA_OK = 0  # sesión guardada
SALIDA_CERRADA = 2  # el usuario cerró la ventana sin entrar
SALIDA_NO_DISPONIBLE = 3  # no hay motor web o falló al abrir: usar el navegador
SALIDA_TIEMPO = 4  # pasó demasiado rato sin que entrara

ESPERA_MAX_S = 600
SONDEO_S = 1  # cada cuánto se mira la URL de la ventana
PAUSA_FINAL_S = 2  # cuánto se ve el mensaje "Listo" antes de cerrar
TITULO = "U-Cursos: inicia sesión"
PERFIL_VENTANA = auth.DATA_DIR / "ventana"  # recuerda Cuenta UChile entre inicios de sesión

URL_USUARIO_RE = re.compile(r"/usuario/[0-9a-f]{32}/")

HTML_LISTO = """<!doctype html><meta charset="utf-8"><title>Listo</title>
<body style="font-family:Segoe UI,system-ui,sans-serif;text-align:center;padding:4rem 1.5rem;color:#222">
<h1 style="margin:0 0 .5rem">Listo</h1>
<p>Ya iniciaste sesión. Esta ventana se cierra sola.<br>Vuelve a tu app y sigue conversando.</p>
</body>"""


def disponible() -> bool:
    """True si hay con qué abrir la ventana (pywebview instalado)."""
    return importlib.util.find_spec("webview") is not None


# ---------------------------------------------------------------- lado del server (lanzar y esperar)


def _comando_hijo() -> list[str]:
    if getattr(sys, "frozen", False):  # ejecutable único: él mismo hace de ventana
        return [sys.executable, "ventana-login"]
    return [sys.executable, "-m", "ucursos_mcp", "ventana-login"]


def lanzar() -> subprocess.Popen:
    """Abre la ventana en un proceso aparte, sin tocar la entrada/salida del server MCP."""
    auth.DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}  # el hijo empaquetado se extrae solo
    with open(auth.DATA_DIR / "ventana.log", "w", encoding="utf-8") as log:
        return subprocess.Popen(
            _comando_hijo(),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def esperar(proc: subprocess.Popen, segundos: float | None) -> int | None:
    """Código de salida de la ventana, o None si sigue abierta pasados `segundos`."""
    try:
        return proc.wait(timeout=segundos)
    except subprocess.TimeoutExpired:
        return None


# ---------------------------------------------------------------- lado de la ventana


def a_cookies(del_webview: list) -> list[dict]:
    """Convierte lo que entrega pywebview (SimpleCookie) al formato de la sesión guardada.

    Se quedan solo las cookies de U-Cursos y Cuenta UChile. Una cookie sin dominio es de
    U-Cursos, que es la página que se cargó.
    """
    salida = []
    for simple in del_webview:
        for nombre, morsel in simple.items():
            dominio = morsel["domain"] or ".u-cursos.cl"
            if not any(d in dominio for d in auth.DOMINIOS_SESION):
                continue
            try:
                vence = int(parsedate_to_datetime(morsel["expires"]).timestamp()) if morsel["expires"] else -1
            except (TypeError, ValueError):
                vence = -1
            salida.append({"name": nombre, "value": morsel.value, "domain": dominio,
                           "path": morsel["path"] or "/", "secure": bool(morsel["secure"]), "expires": vence})
    return salida


def correr(
    validar: Callable[[list[dict]], str | None] | None = None,
    session_path: Path | None = None,
    timeout_s: float = ESPERA_MAX_S,
) -> int:
    """Muestra la ventana hasta que el usuario entre. Devuelve un código SALIDA_*."""
    try:
        import webview
    except Exception:  # noqa: BLE001 (sin pywebview o sin su motor: se usa el navegador)
        return SALIDA_NO_DISPONIBLE
    if validar is None:
        from .client import (
            validar_cookies as validar,  # import local: client importa auth
        )

    resultado = {"codigo": SALIDA_CERRADA}
    cerrada = threading.Event()

    def vigilar(ventana) -> None:
        """Espera en segundo plano a que la URL pase a la zona de usuario."""
        espera = 0.0
        while not cerrada.wait(SONDEO_S):
            espera += SONDEO_S
            if espera > timeout_s:
                resultado["codigo"] = SALIDA_TIEMPO
                ventana.destroy()
                return
            try:
                url = ventana.get_current_url() or ""
            except Exception:  # noqa: BLE001 (la ventana se está cerrando)
                return
            if not URL_USUARIO_RE.search(url):
                continue
            cookies = a_cookies(ventana.get_cookies())
            if validar(cookies) is not None:  # puede que las cookies aún no estén listas: reintenta
                continue
            auth.guardar_sesion(cookies, {"navegador": "ventana", "perfil": ""}, session_path)
            resultado["codigo"] = SALIDA_OK
            ventana.load_html(HTML_LISTO)
            cerrada.wait(PAUSA_FINAL_S)
            ventana.destroy()
            return

    try:
        ventana = webview.create_window(TITULO, auth.BASE_URL, width=520, height=780)
        ventana.events.closed += lambda: cerrada.set()
        PERFIL_VENTANA.mkdir(parents=True, exist_ok=True)
        webview.start(vigilar, ventana, private_mode=False, storage_path=str(PERFIL_VENTANA))
    except Exception as exc:  # noqa: BLE001 (cualquier falla de la interfaz => plan B)
        print(f"No pude abrir la ventana: {type(exc).__name__}: {exc}", file=sys.stderr)
        return SALIDA_NO_DISPONIBLE
    return resultado["codigo"]


def comprobar() -> int:
    """Para la CI: 0 si el motor de la ventana carga bien en este ejecutable."""
    try:
        import webview

        if sys.platform == "win32":
            import webview.platforms.winforms  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"La ventana no carga: {type(exc).__name__}: {exc}", file=sys.stderr)
        return SALIDA_NO_DISPONIBLE
    print("La ventana de inicio de sesión carga bien.")
    return SALIDA_OK

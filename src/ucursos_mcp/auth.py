"""
Login sin automatizar el navegador: tú entras a U-Cursos en tu navegador de siempre
(Edge, Chrome, Firefox, Zen, Brave...) como cualquier día, y el MCP lee esa sesión tuya que
ya quedó guardada en el navegador.

Por qué así:
  - U-Cursos entra por Cuenta UChile, con captcha. Un navegador abierto por un programa
    queda marcado como automatizado y el captcha lo bloquea. Aquí no se automatiza nada:
    inicias sesión tú, como humano, en tu navegador normal (donde el captcha ni aparece).
  - Tu clave NUNCA pasa por este código ni por Claude: la escribes en tu navegador.
  - El MCP solo lee las cookies del dominio de U-Cursos desde el navegador, igual que hace
    un gestor de contraseñas con tus propios datos. Nada sale de tu computador.

Flujo:
  1. iniciar_sesion (o `ucursos-login`) abre U-Cursos en un navegador concreto: el que se
     pida, el que funcionó la última vez o el por defecto del sistema.
  2. Inicias sesión ahí, normal.
  3. estado_sesion lee las cookies de ese navegador (o de todos, si no se indica), prueba
     cada perfil contra U-Cursos y guarda el primero que sirva. Si ninguno sirve, explica
     qué encontró en cada navegador y perfil.

Variables de entorno:
  UCURSOS_BROWSER   fuerza un solo navegador (ver navegadores.NAVEGADORES)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import navegadores
from .navegadores import NAVEGADORES, Perfil

BASE_URL = "https://www.u-cursos.cl"

# Datos locales del usuario. Fuera del repo y de la carpeta de la extensión, para que la
# sesión sobreviva a una actualización de la extensión.
DATA_DIR = Path(os.environ.get("UCURSOS_DATA", Path.home() / ".ucursos-mcp"))
SESSION_PATH = Path(os.environ.get("UCURSOS_SESSION", DATA_DIR / "ucursos.storage_state.json"))
LOGIN_LOG = DATA_DIR / "login.log"

# Dominios cuyas cookies forman la sesión (U-Cursos y el login de Cuenta UChile).
DOMINIOS_SESION = ("u-cursos.cl", "uchile.cl")

# Cuántos perfiles con cookies de U-Cursos se prueban contra el servidor, como máximo.
MAX_VALIDACIONES = 5


class LoginError(RuntimeError):
    """No se pudo importar la sesión. El mensaje ya trae el diagnóstico para el usuario."""


@dataclass
class Candidato:
    """Un perfil de un navegador, con lo que se encontró en él."""

    perfil: Perfil
    cookies: list[dict] = field(default_factory=list)
    error: str | None = None  # por qué no se pudieron leer las cookies
    rechazo: str | None = None  # por qué U-Cursos no las aceptó

    @property
    def de_ucursos(self) -> list[dict]:
        return [c for c in self.cookies if c["domain"].lstrip(".").endswith("u-cursos.cl")]


# ---------------------------------------------------------------- abrir el navegador


def navegador_preferido(navegador: str | None = None) -> str | None:
    """El navegador con el que trabajar: el pedido, UCURSOS_BROWSER, el que funcionó la
    última vez o el por defecto del sistema, en ese orden."""
    for opcion in (navegador, os.environ.get("UCURSOS_BROWSER")):
        if opcion:
            return navegadores.normalizar(opcion)
    return navegador_guardado() or navegadores.por_defecto()


def abrir_ucursos(navegador: str | None = None, url: str = BASE_URL) -> str:
    """Abre U-Cursos en ese navegador. No automatiza nada. Devuelve en cuál se abrió."""
    return navegadores.abrir(url, navegador)


# ---------------------------------------------------------------- leer cookies


def _desde_chromium(perfil: Perfil, dominio: str) -> list[dict]:
    import browser_cookie3

    fn = getattr(browser_cookie3, perfil.navegador)
    jar = fn(cookie_file=str(perfil.cookies), domain_name=dominio,
             key_file=str(perfil.llave) if perfil.llave else None)
    return [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path or "/",
         "secure": bool(c.secure), "expires": c.expires if c.expires else -1}
        for c in jar
    ]


def _desde_firefox(perfil: Perfil) -> list[dict]:
    """Cookies de un perfil de Firefox, Zen o LibreWolf.

    No usamos browser_cookie3 aquí: copia solo cookies.sqlite y pierde las cookies recién
    creadas, que Firefox deja un rato en cookies.sqlite-wal. Justo las del login que el
    usuario acaba de hacer. Copiamos ambos archivos y SQLite aplica el WAL al abrir.
    """
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "cookies.sqlite"
        shutil.copyfile(perfil.cookies, copia)
        wal = perfil.cookies.with_name("cookies.sqlite-wal")
        if wal.exists():
            shutil.copyfile(wal, copia.with_name("cookies.sqlite-wal"))
        con = sqlite3.connect(copia)
        try:
            filas = con.execute(
                "SELECT host, path, isSecure, expiry, name, value, lastAccessed FROM moz_cookies"
            ).fetchall()
        finally:
            con.close()

    # Con contenedores puede haber la misma cookie repetida: gana la usada más recientemente.
    por_clave: dict[tuple, tuple] = {}
    for f in filas:
        clave = (f[4], f[0], f[1])
        if clave not in por_clave or (f[6] or 0) > (por_clave[clave][6] or 0):
            por_clave[clave] = f
    cookies = []
    for host, path, secure, expiry, name, value, _ in por_clave.values():
        if expiry and expiry > 10**11:  # versiones nuevas de Firefox la guardan en milisegundos
            expiry //= 1000
        cookies.append({"name": name, "value": value, "domain": host, "path": path or "/",
                        "secure": bool(secure), "expires": expiry or -1})

    # Cookies de sesión que solo viven en el respaldo de la sesión abierta.
    vistas = {(c["name"], c["domain"], c["path"]) for c in cookies}
    for c in _cookies_sessionstore(perfil.carpeta):
        if (c["name"], c["domain"], c["path"]) not in vistas:
            cookies.append(c)
    return cookies


def _cookies_sessionstore(carpeta: Path) -> list[dict]:
    archivo = carpeta / "sessionstore-backups" / "recovery.jsonlz4"
    if not archivo.exists():
        return []
    try:
        import lz4.block

        datos = archivo.read_bytes()
        estado = json.loads(lz4.block.decompress(datos[8:]))  # 8 bytes de cabecera "mozLz40\0"
    except Exception:  # noqa: BLE001 (respaldo opcional: si no se puede leer, seguimos sin él)
        return []
    return [
        {"name": c.get("name", ""), "value": c.get("value", ""), "domain": c.get("host", ""),
         "path": c.get("path") or "/", "secure": bool(c.get("secure")), "expires": -1}
        for c in estado.get("cookies", [])
    ]


def _explicar_error(perfil: Perfil, exc: Exception) -> str:
    """Traduce el error de lectura a algo que el usuario pueda resolver."""
    texto = str(exc)
    etiqueta = NAVEGADORES[perfil.navegador].etiqueta
    if "Unable to get key" in texto or "Failed to decrypt" in texto or "DPAPI" in texto:
        return (
            f"no pude descifrar las cookies. {etiqueta} en Windows las cifra con una llave ligada "
            "a la aplicación (Chrome 127+ y derivados) que este programa no puede leer"
        )
    if "Unable to read database" in texto or isinstance(exc, PermissionError) or "locked" in texto:
        return f"el archivo de cookies está bloqueado, probablemente porque {etiqueta} está abierto"
    return f"no pude leer las cookies ({type(exc).__name__}: {texto})"


def leer_perfil(perfil: Perfil) -> Candidato:
    """Lee las cookies de U-Cursos y Cuenta UChile de un perfil. No lanza: anota el error."""
    cand = Candidato(perfil)
    try:
        if NAVEGADORES[perfil.navegador].motor == "firefox":
            todas = _desde_firefox(perfil)
            cookies = [c for c in todas if any(d in c["domain"] for d in DOMINIOS_SESION)]
        else:
            cookies = [c for d in DOMINIOS_SESION for c in _desde_chromium(perfil, d)]
    except Exception as exc:  # noqa: BLE001 (cualquier falla de un navegador se reporta y seguimos)
        cand.error = _explicar_error(perfil, exc)
        return cand
    por_clave = {(c["name"], c["domain"], c["path"]): c for c in cookies}
    cand.cookies = list(por_clave.values())
    return cand


def candidatos(navegador: str | None = None, perfil: str | None = None) -> tuple[list[Candidato], list[str]]:
    """Lee todos los perfiles relevantes. Devuelve (candidatos, notas sobre navegadores sin perfil).

    Con `navegador`, solo ese. Sin él: el preferido primero y después el resto.
    """
    if navegador or os.environ.get("UCURSOS_BROWSER"):
        orden = [navegador_preferido(navegador)]
    else:
        primero = navegador_preferido()
        orden = ([primero] if primero else []) + [n for n in NAVEGADORES if n != primero]

    lista: list[Candidato] = []
    notas: list[str] = []
    for nombre in orden:
        encontrados = navegadores.perfiles(nombre, perfil)
        if not encontrados and (navegador or os.environ.get("UCURSOS_BROWSER")):
            detalle = f" con un perfil que contenga \"{perfil}\"" if perfil else ""
            notas.append(f"{NAVEGADORES[nombre].etiqueta}: no lo encontré instalado{detalle} en este computador.")
        lista += [leer_perfil(p) for p in encontrados]
    return lista, notas


# ---------------------------------------------------------------- importar y diagnosticar


def _resumen_cookies(cand: Candidato) -> str:
    uc = cand.de_ucursos
    otras = len(cand.cookies) - len(uc)
    if not uc:
        return f"{len(cand.cookies)} cookies, ninguna de u-cursos.cl (solo de uchile.cl)" if otras else "ninguna cookie de U-Cursos"
    ahora = time.time()
    nombres = []
    for c in uc[:8]:
        if c["expires"] == -1:
            nombres.append(f"{c['name']} (de sesión)")
        elif c["expires"] < ahora:
            nombres.append(f"{c['name']} (vencida)")
        else:
            nombres.append(c["name"])
    extra = f" y {len(uc) - 8} más" if len(uc) > 8 else ""
    vacias = sum(1 for c in uc if not c["value"])
    aviso = f"; {vacias} sin valor, posible problema de descifrado" if vacias else ""
    return (f"{len(cand.cookies)} cookies: {len(uc)} de u-cursos.cl ({', '.join(nombres)}{extra}{aviso}) "
            f"y {otras} de uchile.cl")


def diagnostico(lista: list[Candidato], notas: list[str]) -> str:
    """Explica qué se encontró en cada navegador y perfil, y qué hacer."""
    lineas = ["No encontré una sesión válida de U-Cursos. Esto es lo que revisé:"]
    for c in lista:
        if c.error:
            estado = c.error
        elif c.rechazo:
            estado = f"{_resumen_cookies(c)}. U-Cursos no las aceptó: {c.rechazo}"
        else:
            estado = _resumen_cookies(c)
        lineas.append(f"- {c.perfil.descripcion}: {estado}.")
    lineas += [f"- {n}" for n in notas]
    if not lista and not notas:
        lineas.append("- No encontré ningún navegador compatible instalado.")

    sugerencias = []
    if any(c.error and "descifrar" in c.error for c in lista):
        sugerencias.append("Para Chrome, Edge o Brave en Windows: inicia sesión en Firefox o Zen y pide importar desde ese navegador.")
    if any(c.error and "bloqueado" in c.error for c in lista):
        sugerencias.append(
            "Si el archivo está bloqueado: cierra ese navegador por completo (también en segundo plano) e intenta de nuevo. "
            "Si después U-Cursos pide login, su cookie es de sesión y se borra al cerrar: usa Firefox o Zen."
        )
    if any(c.rechazo for c in lista):
        sugerencias.append(
            "Si U-Cursos rechazó las cookies: confirma que iniciaste sesión en ese mismo navegador y perfil, "
            "y espera unos 30 segundos antes de reintentar (Chrome y Edge tardan en guardar las cookies en disco)."
        )
    sugerencias.append(
        "Si iniciaste sesión en otro navegador o perfil, indícalo (navegador y, si tienes varios, perfil). "
        f"Navegadores compatibles: {', '.join(NAVEGADORES)}."
    )
    return "\n".join(lineas + ["", "Qué hacer:"] + [f"- {s}" for s in sugerencias])


def importar_sesion(
    navegador: str | None = None,
    perfil: str | None = None,
    validar: Callable[[list[dict]], str | None] | None = None,
    session_path: Path | None = None,
) -> Candidato:
    """Busca una sesión de U-Cursos en el navegador, la valida y la guarda.

    `validar(cookies)` devuelve None si U-Cursos acepta las cookies, o el motivo del rechazo.
    Sin `validar` se toma el primer perfil que tenga cookies de u-cursos.cl.
    Lanza LoginError con el diagnóstico completo si ningún perfil sirve.
    """
    lista, notas = candidatos(navegador, perfil)
    probados = 0
    for cand in lista:
        if cand.error or not cand.de_ucursos:
            continue
        if probados >= MAX_VALIDACIONES:
            break
        probados += 1
        cand.rechazo = validar(cand.cookies) if validar else None
        if cand.rechazo is None:
            _guardar(cand, session_path or SESSION_PATH)
            return cand

    msg = diagnostico(lista, notas)
    LOGIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    LOGIN_LOG.write_text(msg, encoding="utf-8")
    raise LoginError(msg)


def _guardar(cand: Candidato, session_path: Path) -> None:
    estado = {
        "cookies": cand.cookies,
        "origins": [],
        # De dónde salió, para abrir y leer el mismo navegador la próxima vez.
        "origen": {"navegador": cand.perfil.navegador, "perfil": cand.perfil.nombre},
    }
    # Escritura atómica: el server recarga la sesión cuando cambia este archivo.
    session_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = session_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado), encoding="utf-8")
    try:
        tmp.chmod(0o600)  # en Windows no aplica
    except OSError:
        pass
    tmp.replace(session_path)


def navegador_guardado(session_path: Path | None = None) -> str | None:
    """Navegador del que salió la última sesión que funcionó (solo lee el campo `origen`)."""
    try:
        estado = json.loads((session_path or SESSION_PATH).read_text(encoding="utf-8"))
        nombre = estado.get("origen", {}).get("navegador")
        return nombre if nombre in NAVEGADORES else None
    except (OSError, ValueError, AttributeError):
        return None


def main() -> None:
    """CLI `ucursos-login`: abre U-Cursos, espera a que entres y luego importa la sesión."""
    from .client import validar_cookies  # import local: client importa este módulo

    parser = argparse.ArgumentParser(description="Importa tu sesión de U-Cursos desde tu navegador.")
    parser.add_argument("--navegador", help=f"uno de: {', '.join(NAVEGADORES)}")
    parser.add_argument("--perfil", help="nombre (o parte) del perfil del navegador")
    args = parser.parse_args()

    try:
        nav = navegador_preferido(args.navegador)
    except navegadores.NavegadorDesconocido as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    donde = abrir_ucursos(nav)
    print(f"Se abrió U-Cursos en {donde}. Inicia sesión ahí.")
    try:
        input("Cuando ya estés dentro, vuelve aquí y presiona Enter...")
    except EOFError:
        pass
    try:
        cand = importar_sesion(args.navegador, args.perfil, validar=validar_cookies)
    except LoginError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    print(f"Sesión guardada desde {cand.perfil.descripcion} en {SESSION_PATH}")


if __name__ == "__main__":
    main()

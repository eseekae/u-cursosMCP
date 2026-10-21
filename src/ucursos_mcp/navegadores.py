"""
Conocimiento de navegadores: cuáles hay, dónde guardan sus perfiles, cuál es el por defecto
y cómo abrir U-Cursos en uno en particular.

No sabe nada de cookies ni de U-Cursos: eso es trabajo de auth.py. La idea es que
iniciar_sesion y estado_sesion hablen del MISMO navegador (antes uno abría el navegador por
defecto y el otro leía cookies de una lista fija, y podían no coincidir).

Abrir un navegador aquí es lo mismo que hace webbrowser.open: lanzar el programa con una URL.
No se controla el navegador ni se automatiza nada.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath


@dataclass(frozen=True)
class Navegador:
    nombre: str  # clave que reciben las tools y UCURSOS_BROWSER: "edge", "zen"
    etiqueta: str  # nombre para mostrar: "Microsoft Edge"
    motor: str  # "chromium" o "firefox"
    win: tuple[tuple[str, str], ...] = ()  # carpetas de datos en Windows: (variable de entorno, ruta)
    mac: tuple[str, ...] = ()
    linux: tuple[str, ...] = ()
    exe_win: tuple[str, ...] = ()  # rutas típicas del ejecutable: (variable de entorno\ruta)
    app_mac: tuple[str, ...] = ()
    cmd_linux: tuple[str, ...] = ()


_MAC = "~/Library/Application Support/"

NAVEGADORES: dict[str, Navegador] = {
    n.nombre: n
    for n in (
        Navegador(
            "edge", "Microsoft Edge", "chromium",
            win=(("LOCALAPPDATA", r"Microsoft\Edge\User Data"),),
            mac=(_MAC + "Microsoft Edge",), linux=("~/.config/microsoft-edge",),
            exe_win=(r"ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
                     r"ProgramFiles\Microsoft\Edge\Application\msedge.exe"),
            app_mac=("Microsoft Edge",), cmd_linux=("microsoft-edge", "microsoft-edge-stable"),
        ),
        Navegador(
            "chrome", "Google Chrome", "chromium",
            win=(("LOCALAPPDATA", r"Google\Chrome\User Data"),),
            mac=(_MAC + "Google/Chrome",), linux=("~/.config/google-chrome",),
            exe_win=(r"ProgramFiles\Google\Chrome\Application\chrome.exe",
                     r"ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
                     r"LOCALAPPDATA\Google\Chrome\Application\chrome.exe"),
            app_mac=("Google Chrome",), cmd_linux=("google-chrome", "google-chrome-stable"),
        ),
        Navegador(
            "brave", "Brave", "chromium",
            win=(("LOCALAPPDATA", r"BraveSoftware\Brave-Browser\User Data"),),
            mac=(_MAC + "BraveSoftware/Brave-Browser",), linux=("~/.config/BraveSoftware/Brave-Browser",),
            exe_win=(r"ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe",
                     r"LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe"),
            app_mac=("Brave Browser",), cmd_linux=("brave-browser", "brave"),
        ),
        Navegador(
            "vivaldi", "Vivaldi", "chromium",
            win=(("LOCALAPPDATA", r"Vivaldi\User Data"),),
            mac=(_MAC + "Vivaldi",), linux=("~/.config/vivaldi",),
            exe_win=(r"LOCALAPPDATA\Vivaldi\Application\vivaldi.exe",
                     r"ProgramFiles\Vivaldi\Application\vivaldi.exe"),
            app_mac=("Vivaldi",), cmd_linux=("vivaldi", "vivaldi-stable"),
        ),
        Navegador(
            "opera", "Opera", "chromium",
            win=(("APPDATA", r"Opera Software\Opera Stable"),),
            mac=(_MAC + "com.operasoftware.Opera",), linux=("~/.config/opera",),
            exe_win=(r"LOCALAPPDATA\Programs\Opera\opera.exe",),
            app_mac=("Opera",), cmd_linux=("opera",),
        ),
        Navegador(
            "opera_gx", "Opera GX", "chromium",
            win=(("APPDATA", r"Opera Software\Opera GX Stable"),),
            mac=(_MAC + "com.operasoftware.OperaGX",),
            exe_win=(r"LOCALAPPDATA\Programs\Opera GX\opera.exe",),
            app_mac=("Opera GX",),
        ),
        Navegador(
            "chromium", "Chromium", "chromium",
            win=(("LOCALAPPDATA", r"Chromium\User Data"),),
            mac=(_MAC + "Chromium",), linux=("~/.config/chromium",),
            exe_win=(r"LOCALAPPDATA\Chromium\Application\chrome.exe",),
            app_mac=("Chromium",), cmd_linux=("chromium", "chromium-browser"),
        ),
        Navegador(
            "firefox", "Firefox", "firefox",
            win=(("APPDATA", r"Mozilla\Firefox"),),
            mac=(_MAC + "Firefox",), linux=("~/.mozilla/firefox", "~/snap/firefox/common/.mozilla/firefox"),
            exe_win=(r"ProgramFiles\Mozilla Firefox\firefox.exe",
                     r"ProgramFiles(x86)\Mozilla Firefox\firefox.exe",
                     r"LOCALAPPDATA\Mozilla Firefox\firefox.exe"),
            app_mac=("Firefox",), cmd_linux=("firefox",),
        ),
        Navegador(
            "zen", "Zen Browser", "firefox",
            win=(("APPDATA", "zen"),),
            mac=(_MAC + "zen",), linux=("~/.zen", "~/.var/app/app.zen_browser.zen/.zen"),
            exe_win=(r"ProgramFiles\Zen Browser\zen.exe", r"LOCALAPPDATA\Zen Browser\zen.exe"),
            app_mac=("Zen", "Zen Browser"), cmd_linux=("zen-browser", "zen"),
        ),
        Navegador(
            "librewolf", "LibreWolf", "firefox",
            win=(("APPDATA", "librewolf"),),
            mac=(_MAC + "librewolf",), linux=("~/.librewolf",),
            exe_win=(r"ProgramFiles\LibreWolf\librewolf.exe",),
            app_mac=("LibreWolf",), cmd_linux=("librewolf",),
        ),
    )
}

# Ejecutable de Windows -> navegador (para reconocer el navegador por defecto).
_EXE_A_NAVEGADOR = {
    "msedge.exe": "edge", "chrome.exe": "chrome", "brave.exe": "brave", "vivaldi.exe": "vivaldi",
    "opera.exe": "opera", "launcher.exe": "opera", "firefox.exe": "firefox", "zen.exe": "zen",
    "librewolf.exe": "librewolf",
}


class NavegadorDesconocido(ValueError):
    """Se pidió un navegador que no está en NAVEGADORES."""


def normalizar(nombre: str) -> str:
    """'Opera GX' -> 'opera_gx', 'Microsoft Edge' -> 'edge'. Lanza NavegadorDesconocido si no existe."""
    clave = re.sub(r"[\s-]+", "_", nombre.strip().lower())
    clave = {"microsoft_edge": "edge", "msedge": "edge", "google_chrome": "chrome", "zen_browser": "zen"}.get(clave, clave)
    if clave not in NAVEGADORES:
        raise NavegadorDesconocido(
            f"No conozco el navegador '{nombre}'. Opciones: {', '.join(NAVEGADORES)}."
        )
    return clave


# ---------------------------------------------------------------- perfiles


@dataclass(frozen=True)
class Perfil:
    navegador: str
    nombre: str  # nombre que el usuario reconoce ("Default (release)", "Persona 1")
    carpeta: Path
    cookies: Path  # Cookies (Chromium) o cookies.sqlite (Firefox)
    llave: Path | None = None  # Local State (Chromium): guarda la llave de cifrado

    @property
    def descripcion(self) -> str:
        return f"{NAVEGADORES[self.navegador].etiqueta} (perfil \"{self.nombre}\")"


def carpetas_datos(nav: Navegador) -> list[Path]:
    """Carpetas de datos del navegador en este sistema que existen de verdad."""
    if sys.platform == "win32":
        rutas = [Path(os.environ.get(env, "")) / rel for env, rel in nav.win if os.environ.get(env)]
    elif sys.platform == "darwin":
        rutas = [Path(p).expanduser() for p in nav.mac]
    else:
        rutas = [Path(p).expanduser() for p in nav.linux]
    return [r for r in rutas if r.is_dir()]


def _perfiles_chromium(nombre: str, base: Path) -> list[Perfil]:
    llave = base / "Local State"
    info: dict = {}
    ultimo = None
    try:
        estado = json.loads(llave.read_text(encoding="utf-8"))
        info = estado.get("profile", {}).get("info_cache", {})
        ultimo = estado.get("profile", {}).get("last_used")
    except (OSError, ValueError):
        pass

    # Opera guarda el único perfil directamente en la carpeta base.
    carpetas = [base] if _cookies_chromium(base) else []
    carpetas += sorted(d for d in base.iterdir() if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile ")))
    # El último perfil usado primero: es donde el usuario acaba de iniciar sesión.
    carpetas.sort(key=lambda d: (d.name != ultimo, d.name != "Default"))

    perfiles = []
    for d in carpetas:
        archivo = _cookies_chromium(d)
        if archivo:
            etiqueta = info.get(d.name, {}).get("name") or d.name
            perfiles.append(Perfil(nombre, etiqueta, d, archivo, llave if llave.exists() else None))
    return perfiles


def _cookies_chromium(carpeta: Path) -> Path | None:
    for archivo in (carpeta / "Network" / "Cookies", carpeta / "Cookies"):
        if archivo.is_file():
            return archivo
    return None


def _perfiles_firefox(nombre: str, base: Path) -> list[Perfil]:
    ini = base / "profiles.ini"
    candidatos: list[tuple[str, Path]] = []
    preferidos: list[Path] = []
    if ini.is_file():
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(ini, encoding="utf-8")
        for sec in cfg.sections():
            s = cfg[sec]
            if sec.startswith("Install") and s.get("Default"):
                preferidos.append((base / s["Default"]).resolve())
            elif sec.startswith("Profile") and s.get("Path"):
                ruta = Path(s["Path"]) if s.get("IsRelative") == "0" else base / s["Path"]
                candidatos.append((s.get("Name") or ruta.name, ruta.resolve()))
                if s.get("Default") == "1":
                    preferidos.append(ruta.resolve())
    else:
        for d in sorted([*base.glob("*"), *base.glob("Profiles/*")]):
            if (d / "cookies.sqlite").is_file():
                candidatos.append((d.name, d.resolve()))

    def orden(c: tuple[str, Path]):
        # Primero el perfil por defecto; después el que se usó más recientemente.
        archivo = c[1] / "cookies.sqlite"
        mtime = archivo.stat().st_mtime if archivo.exists() else 0
        return (c[1] not in preferidos, -mtime)

    return [
        Perfil(nombre, n, ruta, ruta / "cookies.sqlite")
        for n, ruta in sorted(candidatos, key=orden)
        if (ruta / "cookies.sqlite").is_file()
    ]


def perfiles(nombre: str, filtro: str | None = None) -> list[Perfil]:
    """Perfiles con archivo de cookies de un navegador. `filtro` busca por nombre o carpeta."""
    nav = NAVEGADORES[nombre]
    lector = _perfiles_chromium if nav.motor == "chromium" else _perfiles_firefox
    encontrados = [p for base in carpetas_datos(nav) for p in lector(nombre, base)]
    if filtro:
        f = filtro.lower()
        encontrados = [p for p in encontrados if f in p.nombre.lower() or f in p.carpeta.name.lower()]
    return encontrados


def instalados() -> list[str]:
    """Navegadores con al menos un perfil en este computador."""
    return [n for n in NAVEGADORES if perfiles(n)]


# ---------------------------------------------------------------- navegador por defecto


def por_defecto() -> str | None:
    """Navegador por defecto del sistema, si es uno que conocemos. None si no se puede saber."""
    try:
        if sys.platform == "win32":
            exe = _exe_por_defecto_windows()
            return _navegador_de_exe(exe) if exe else None
        if sys.platform.startswith("linux"):
            out = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL, check=False,
            ).stdout.strip().lower()
            return _navegador_de_desktop(out)
    except (OSError, subprocess.SubprocessError):
        return None
    return None  # macOS: no lo detectamos; se usa webbrowser.open


def _navegador_de_exe(exe: str) -> str | None:
    nombre = _EXE_A_NAVEGADOR.get(PureWindowsPath(exe).name.lower())
    if nombre == "opera" and "gx" in exe.lower():
        return "opera_gx"
    if nombre == "chrome" and "chromium" in exe.lower():
        return "chromium"
    return nombre


def _navegador_de_desktop(desktop: str) -> str | None:
    for fragmento, nombre in (
        ("zen", "zen"), ("librewolf", "librewolf"), ("firefox", "firefox"), ("edge", "edge"),
        ("brave", "brave"), ("vivaldi", "vivaldi"), ("opera", "opera"), ("chromium", "chromium"),
        ("chrome", "chrome"),
    ):
        if fragmento in desktop:
            return nombre
    return None


def _exe_por_defecto_windows() -> str | None:
    """Ejecutable que Windows usa para abrir links https (asociación del usuario)."""
    import winreg

    clave = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
        progid = winreg.QueryValueEx(k, "ProgId")[0]
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{progid}\shell\open\command") as k:
        comando = winreg.QueryValueEx(k, "")[0]
    m = re.match(r'\s*"([^"]+)"|\s*(\S+)', comando)
    return (m.group(1) or m.group(2)) if m else None


# ---------------------------------------------------------------- abrir


def _exe_windows(nav: Navegador) -> str | None:
    """Ruta del ejecutable del navegador en Windows, o None."""
    # 1. Si es el navegador por defecto, Windows ya sabe dónde está.
    try:
        exe = _exe_por_defecto_windows()
        if exe and _navegador_de_exe(exe) == nav.nombre and Path(exe).is_file():
            return exe
    except OSError:
        pass
    # 2. Rutas de instalación típicas.
    for ruta in nav.exe_win:
        env, _, rel = ruta.partition("\\")
        base = os.environ.get(env)
        if base and (Path(base) / rel).is_file():
            return str(Path(base) / rel)
    return None


def abrir(url: str, nombre: str | None = None) -> str:
    """Abre `url` en el navegador `nombre` (o el por defecto). Devuelve dónde se abrió.

    Si no encuentra ese navegador, cae a webbrowser.open y lo dice en el texto devuelto.
    """
    if nombre:
        nav = NAVEGADORES[nombre]
        comando: list[str] | None = None
        if sys.platform == "win32":
            exe = _exe_windows(nav)
            comando = [exe, url] if exe else None
        elif sys.platform == "darwin":
            for app in nav.app_mac:
                if subprocess.run(["open", "-Ra", app], capture_output=True, stdin=subprocess.DEVNULL, check=False).returncode == 0:
                    comando = ["open", "-a", app, url]
                    break
        else:
            cmd = next((shutil.which(c) for c in nav.cmd_linux if shutil.which(c)), None)
            comando = [cmd, url] if cmd else None
        if comando:
            # stdin/stdout a DEVNULL: el server habla MCP por stdio y el navegador no debe tocarlo.
            subprocess.Popen(
                comando, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return nav.etiqueta
    webbrowser.open(url)
    return "el navegador por defecto del sistema"

"""
Instalador: deja el server registrado en las apps de IA que el usuario tenga en su PC.

Pensado para el ejecutable único (doble clic, sin terminal): copia el ejecutable a una carpeta
estable y agrega una entrada `ucursos` a la config MCP de cada app detectada. Si ya había una
versión instalada, la actualiza en el mismo lugar (las apps ya apuntan ahí). No sabe de
U-Cursos, ni lee cookies ni toca la sesión: solo edita configs de otras apps, con respaldo.

Apps soportadas:
  - ChatGPT de escritorio / Codex: ~/.codex/config.toml (tabla [mcp_servers.ucursos])
  - Claude Desktop: claude_desktop_config.json (mcpServers.ucursos)
  - Cursor: ~/.cursor/mcp.json (mcpServers.ucursos)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

NOMBRE = "ucursos"
EXE = "ucursos-mcp.exe" if sys.platform == "win32" else "ucursos-mcp"


@dataclass
class Resultado:
    app: str
    ok: bool
    detalle: str


def empaquetado() -> bool:
    """True si corremos como ejecutable único (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def carpeta_instalacion() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ucursos-mcp"


def version_actual() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("ucursos-mcp")
    except PackageNotFoundError:
        return "desconocida"


def version_instalada() -> str | None:
    """Versión del programa ya instalado en la carpeta fija, o None si no hay (o es muy antigua)."""
    carpeta = carpeta_instalacion()
    if not (carpeta / EXE).exists():
        return None
    try:
        return (carpeta / "VERSION").read_text(encoding="utf-8").strip() or "anterior"
    except OSError:
        return "anterior"  # instalaciones de antes de que se guardara la versión


def copiar_ejecutable() -> Path:
    """Copia el ejecutable a una ruta estable (la que queda escrita en las configs)."""
    destino = carpeta_instalacion() / EXE
    origen = Path(sys.executable).resolve()
    if destino.exists() and origen == destino.resolve():
        return destino  # ya corremos desde la carpeta de instalación
    destino.parent.mkdir(parents=True, exist_ok=True)
    viejo = destino.with_name(destino.name + ".viejo")
    try:
        viejo.unlink(missing_ok=True)  # resto de una actualización anterior
    except OSError:
        pass
    try:
        shutil.copy2(origen, destino)
    except PermissionError:
        # Windows no deja sobrescribir un .exe en uso (la app de IA lo tiene abierto), pero sí
        # renombrarlo: lo apartamos y ponemos el nuevo. La app lo carga al reiniciarse.
        if not destino.exists():
            raise
        destino.replace(viejo)
        shutil.copy2(origen, destino)
    destino.chmod(0o755)
    (destino.parent / "VERSION").write_text(version_actual(), encoding="utf-8")
    return destino


def comando() -> tuple[str, list[str]]:
    """(comando, args) que las apps usan para lanzar el server por stdio."""
    if empaquetado():
        return str(carpeta_instalacion() / EXE), []
    return sys.executable, ["-m", "ucursos_mcp"]  # desde el código fuente (desarrollo)


def _respaldar(ruta: Path) -> None:
    """Deja una copia `.ucursos.bak` la primera vez que tocamos un archivo ajeno."""
    respaldo = ruta.with_name(ruta.name + ".ucursos.bak")
    if ruta.exists() and not respaldo.exists():
        shutil.copy2(ruta, respaldo)


# ---------- Codex / ChatGPT de escritorio (TOML) ----------

def ruta_codex() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"


# Una tabla [mcp_servers.ucursos] y sus subtablas, hasta el próximo encabezado de otra tabla.
_BLOQUE_TOML = re.compile(
    rf"^\[mcp_servers\.{NOMBRE}(\.[^\]]*)?\][^\n]*\n(?:(?!\[)[^\n]*\n?)*", re.MULTILINE
)


def _bloque_toml(cmd: str, args: list[str]) -> str:
    # json.dumps produce strings válidas de TOML (escapa \ y ")
    lineas = [f"[mcp_servers.{NOMBRE}]", f"command = {json.dumps(cmd)}"]
    if args:
        lineas.append(f"args = {json.dumps(args)}")
    return "\n".join(lineas) + "\n"


def instalar_codex(cmd: str, args: list[str], ruta: Path | None = None) -> Resultado:
    ruta = ruta or ruta_codex()
    app = "ChatGPT de escritorio / Codex"
    try:
        texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
        if texto:
            tomllib.loads(texto)  # si ya está roto, no lo empeoramos
        _respaldar(ruta)
        texto = _BLOQUE_TOML.sub("", texto).rstrip("\n")
        texto = (texto + "\n\n" if texto else "") + _bloque_toml(cmd, args)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
        return Resultado(app, True, str(ruta))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Resultado(app, False, f"no pude editar {ruta}: {exc}")


def desinstalar_codex(ruta: Path | None = None) -> Resultado:
    ruta = ruta or ruta_codex()
    app = "ChatGPT de escritorio / Codex"
    try:
        if not ruta.exists():
            return Resultado(app, True, "no estaba instalado")
        _respaldar(ruta)
        ruta.write_text(_BLOQUE_TOML.sub("", ruta.read_text(encoding="utf-8")), encoding="utf-8")
        return Resultado(app, True, "quitado")
    except OSError as exc:
        return Resultado(app, False, f"no pude editar {ruta}: {exc}")


# ---------- Apps con JSON {"mcpServers": {...}} ----------

def ruta_claude_desktop() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Claude" / "claude_desktop_config.json"


def ruta_cursor() -> Path:
    return Path.home() / ".cursor" / "mcp.json"


def _editar_json(
    app: str, ruta: Path, cmd: str, args: list[str], quitar: bool, crear: bool = False
) -> Resultado | None:
    """None si la app no está instalada (no existe su carpeta de config) y no pedimos `crear`."""
    if not ruta.parent.exists() and not (crear and not quitar):
        return None
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        if not isinstance(datos, dict) or not isinstance(datos.get("mcpServers", {}), dict):
            return Resultado(app, False, f"{ruta} tiene un formato que no esperaba")
        _respaldar(ruta)
        servidores = datos.setdefault("mcpServers", {})
        if quitar:
            servidores.pop(NOMBRE, None)
        else:
            servidores[NOMBRE] = {"command": cmd, "args": args}
        ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return Resultado(app, True, "quitado" if quitar else str(ruta))
    except (OSError, ValueError) as exc:
        return Resultado(app, False, f"no pude editar {ruta}: {exc}")


# ---------- Orquestación ----------

@dataclass(frozen=True)
class Destino:
    """Una app donde se puede instalar el server."""

    id: str
    nombre: str
    ruta: Path
    formato: str  # "toml" o "json"

    @property
    def detectado(self) -> bool:
        # Codex/ChatGPT: la config se crea si falta (no hay forma fiable de detectar la app de la Store)
        return self.formato == "toml" or self.ruta.parent.exists()


def destinos() -> list[Destino]:
    return [
        Destino("chatgpt", "ChatGPT de escritorio y Codex", ruta_codex(), "toml"),
        Destino("claude", "Claude Desktop", ruta_claude_desktop(), "json"),
        Destino("cursor", "Cursor", ruta_cursor(), "json"),
    ]


def instalar(ids: list[str] | None = None, copiar: bool | None = None) -> list[Resultado]:
    """Registra el server. `ids` elige los destinos; sin `ids`, todos los detectados."""
    if copiar is None:
        copiar = empaquetado()
    resultados: list[Resultado] = []
    if copiar:
        anterior = version_instalada()
        try:
            copiar_ejecutable()
        except OSError as exc:
            return [Resultado("Programa", False,
                              f"no pude copiarlo a {carpeta_instalacion()}: {exc}. "
                              "Cierra ChatGPT/Claude y vuelve a intentar.")]
        nueva = version_actual()
        if anterior is None:
            detalle = f"instalado (versión {nueva})"
        elif anterior == nueva:
            detalle = f"ya estaba al día (versión {nueva}), lo dejé listo de nuevo"
        else:
            detalle = f"actualizado de la versión {anterior} a la {nueva}"
        resultados.append(Resultado("Programa", True, detalle))
    cmd, args = comando()
    for d in destinos():
        if (d.id not in ids) if ids is not None else (not d.detectado):
            continue
        if d.formato == "toml":
            resultados.append(instalar_codex(cmd, args, d.ruta))
        else:
            r = _editar_json(d.nombre, d.ruta, cmd, args, quitar=False, crear=ids is not None)
            if r:
                resultados.append(r)
    return resultados


def desinstalar() -> list[Resultado]:
    resultados = []
    for d in destinos():
        if d.formato == "toml":
            resultados.append(desinstalar_codex(d.ruta))
        else:
            r = _editar_json(d.nombre, d.ruta, "", [], quitar=True)
            if r:
                resultados.append(r)
    return resultados


def informe(resultados: list[Resultado]) -> str:
    lineas = [("[OK]    " if r.ok else "[ERROR] ") + f"{r.app}: {r.detalle}" for r in resultados]
    return "\n".join(lineas)

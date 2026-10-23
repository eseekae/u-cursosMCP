"""
Punto de entrada del ejecutable único (y de `python -m ucursos_mcp`).

Un mismo archivo hace dos cosas, según cómo lo abran:
  - Las apps de IA lo lanzan con stdin como pipe: arranca el server MCP (stdio).
  - El usuario le hace doble clic (stdin es una consola): se instala solo y le explica el siguiente paso.
Argumentos explícitos: install, uninstall, login, version.
"""

from __future__ import annotations

import sys

from . import instalador

AYUDA = """Uso: ucursos-mcp [install | uninstall | login | version]
  (sin argumentos)  arranca el servidor MCP; con doble clic instala en tus apps
  install           registra el servidor en las apps detectadas (ChatGPT de escritorio y Codex, Claude Desktop, Cursor)
  uninstall         lo quita de esas apps
  login             abre U-Cursos en tu navegador para importar tu sesión
  version           muestra la versión
"""

SIGUIENTE_PASO = """
Listo. Siguiente paso:
  1. Cierra del todo y vuelve a abrir tu app (ChatGPT, Claude o Cursor).
  2. Escribe: "Conéctate a U-Cursos y dime qué tareas tengo pendientes".
  3. Se abrirá U-Cursos en tu navegador: inicia sesión ahí (tu clave nunca pasa por la IA).
"""


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("ucursos-mcp")
    except PackageNotFoundError:
        return "desconocida"


def _pausar() -> None:
    """Evita que la ventana se cierre antes de que el usuario lea el resultado (doble clic)."""
    try:
        input("\nPresiona Enter para cerrar...")
    except EOFError:
        pass


def _instalar(interactivo: bool) -> int:
    ids = None
    if interactivo:
        from .ventana import elegir

        ids = elegir(instalador.destinos())
        if not ids:
            print("No se instaló nada.")
            _pausar()
            return 1
    resultados = instalador.instalar(ids)
    print(instalador.informe(resultados))
    ok = all(r.ok for r in resultados)
    print(SIGUIENTE_PASO if ok else "\nAlgo falló. Revisa los mensajes de arriba.")
    if interactivo:
        _pausar()
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    orden = args[0] if args else ""

    if orden == "install":
        sys.exit(_instalar(interactivo=False))
    if orden == "uninstall":
        print(instalador.informe(instalador.desinstalar()))
        return
    if orden == "login":
        from .auth import main as login

        sys.argv = [sys.argv[0], *args[1:]]
        login()
        return
    if orden == "version":
        print(_version())
        return
    if orden in ("-h", "--help", "help"):
        print(AYUDA)
        return
    if orden:
        print(f"Argumento desconocido: {orden}\n\n{AYUDA}", file=sys.stderr)
        sys.exit(2)

    # Sin argumentos. Solo el ejecutable empaquetado se instala con doble clic: desde el código
    # fuente, `ucursos-mcp` en una terminal sigue siendo el server (lo que espera un desarrollador).
    if instalador.empaquetado() and sys.stdin is not None and sys.stdin.isatty():
        sys.exit(_instalar(interactivo=True))

    from .server import main as servidor

    servidor()


if __name__ == "__main__":
    main()

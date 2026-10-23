"""
Punto de entrada del ejecutable único (y de `python -m ucursos_mcp`).

Un mismo archivo hace dos cosas, según cómo lo abran:
  - Las apps de IA lo lanzan con stdin como pipe: arranca el server MCP (stdio).
  - El usuario le hace doble clic (stdin es una consola): se instala solo y le explica el siguiente paso.
Argumentos explícitos: install, uninstall, login, version (ventana-login lo usa el propio server).
"""

from __future__ import annotations

import sys

from . import instalador, login_ventana

AYUDA = """Uso: ucursos-mcp [install | uninstall | login | version]
  (sin argumentos)  arranca el servidor MCP; con doble clic instala en tus apps
  install           registra el servidor en las apps detectadas (ChatGPT de escritorio y Codex, Claude Desktop, Cursor)
  uninstall         lo quita de esas apps
  login             abre una ventana de U-Cursos para que inicies sesión (si no se puede, usa tu navegador)
  version           muestra la versión
"""

SIGUIENTE_PASO = """
Listo, ya está instalado. Qué sigue:
  1. Cierra del todo tu app (ChatGPT, Claude o Cursor) y ábrela de nuevo.
  2. Escríbele: "Revisa mis cursos de U-Cursos".
  3. {sesion}
"""

PASO_SESION_PENDIENTE = (
    "Se abrirá una ventana de U-Cursos: inicia sesión ahí como siempre.\n"
    "     Tu clave no pasa por la IA y la ventana se cierra sola."
)
PASO_SESION_LISTA = "Tu sesión de U-Cursos ya quedó guardada, no tienes que entrar de nuevo."


def _version() -> str:
    return instalador.version_actual()


def _pausar() -> None:
    """Evita que la ventana se cierre antes de que el usuario lea el resultado (doble clic)."""
    try:
        input("\nPresiona Enter para cerrar...")
    except EOFError:
        pass


def _iniciar_sesion_ahora() -> bool:
    """Ofrece entrar a U-Cursos al terminar de instalar. True si la sesión quedó guardada."""
    from .ventana import ofrecer_login

    if not login_ventana.disponible() or not ofrecer_login():
        return False
    print("\nSe abrió una ventana de U-Cursos. Inicia sesión ahí; se cierra sola cuando termines.")
    codigo = login_ventana.esperar(login_ventana.lanzar(), None)
    if codigo == login_ventana.SALIDA_OK:
        print("Listo, entraste a U-Cursos.")
        return True
    print("No se completó el inicio de sesión. No pasa nada: tu IA te lo pedirá cuando lo necesite.")
    return False


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
    if not ok:
        print("\nAlgo salió mal. Revisa los mensajes de arriba; si el programa está en uso, cierra tus apps de IA y reintenta.")
    else:
        con_sesion = interactivo and _iniciar_sesion_ahora()
        print(SIGUIENTE_PASO.format(sesion=PASO_SESION_LISTA if con_sesion else PASO_SESION_PENDIENTE))
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
    if orden == "ventana-login":  # lo lanza el server MCP; no es para usar a mano
        sys.exit(login_ventana.comprobar() if "--comprobar" in args else login_ventana.correr())
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

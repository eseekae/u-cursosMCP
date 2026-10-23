"""
Preguntas del doble clic: dónde instalar y si quiere iniciar sesión ahora. Usan una ventana
(tkinter) o, si no hay interfaz gráfica, la consola. No saben instalar ni iniciar sesión:
solo devuelven lo que el usuario eligió.
"""

from __future__ import annotations

from .instalador import Destino


def elegir(destinos: list[Destino]) -> list[str] | None:
    """Ids elegidos por el usuario, o None si cancela."""
    try:
        return _ventana(destinos)
    except Exception:  # sin tkinter o sin pantalla (Linux sin display, build sin Tk)
        return _consola(destinos)


def _ventana(destinos: list[Destino]) -> list[str] | None:
    import tkinter as tk
    from tkinter import ttk

    raiz = tk.Tk()
    raiz.title("U-Cursos para tu IA")
    raiz.resizable(False, False)
    marco = ttk.Frame(raiz, padding=20)
    marco.grid()
    ttk.Label(marco, text="¿En qué apps quieres usar U-Cursos?", font=("", 12, "bold")).grid(sticky="w")
    ttk.Label(
        marco,
        text="Tu IA podrá leer tus cursos, tareas y notas.\nSolo lectura: no entrega ni publica nada por ti.",
    ).grid(sticky="w", pady=(0, 10))
    marcas = {}
    for d in destinos:
        marcas[d.id] = tk.BooleanVar(value=d.detectado)
        texto = d.nombre + ("" if d.detectado else "  (no la encontré, se prepara igual)")
        ttk.Checkbutton(marco, text=texto, variable=marcas[d.id]).grid(sticky="w", pady=2)

    elegidos: list[str] | None = None

    def aceptar() -> None:
        nonlocal elegidos
        elegidos = [i for i, v in marcas.items() if v.get()]
        raiz.destroy()

    botones = ttk.Frame(marco)
    botones.grid(sticky="e", pady=(15, 0))
    ttk.Button(botones, text="Cancelar", command=raiz.destroy).grid(row=0, column=0, padx=5)
    ttk.Button(botones, text="Instalar", command=aceptar).grid(row=0, column=1)
    raiz.mainloop()
    return elegidos


def ofrecer_login() -> bool:
    """Pregunta si quiere iniciar sesión en U-Cursos ahora, para no tener que hacerlo después."""
    texto = (
        "¿Quieres iniciar sesión en U-Cursos ahora?\n\n"
        "Se abrirá una ventana donde entras como siempre. Tu clave no pasa por la IA."
    )
    try:
        from tkinter import Tk, messagebox

        raiz = Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        try:
            return bool(messagebox.askyesno("U-Cursos para tu IA", texto, parent=raiz))
        finally:
            raiz.destroy()
    except Exception:  # noqa: BLE001 (sin tkinter o sin pantalla: se pregunta en la consola)
        try:
            return input(f"\n{texto}\n(Enter = sí, n = no): ").strip().lower() not in ("n", "no")
        except EOFError:
            return False


def _consola(destinos: list[Destino]) -> list[str] | None:
    print("¿En qué apps quieres usar U-Cursos?\n")
    for n, d in enumerate(destinos, 1):
        print(f"  {n}. {d.nombre}" + ("" if d.detectado else "  (no la encontré)"))
    por_defecto = [d.id for d in destinos if d.detectado]
    try:
        resp = input("\nEscribe los números separados por coma (ej. 1,2), o Enter para las que encontré: ")
    except EOFError:
        return por_defecto
    resp = resp.strip()
    if not resp:
        return por_defecto
    try:
        return [destinos[int(x) - 1].id for x in resp.split(",") if x.strip()]
    except (ValueError, IndexError):
        print("No entendí esa respuesta. Vuelve a abrir el programa e inténtalo de nuevo.")
        return None

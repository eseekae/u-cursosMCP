"""
Elegir dónde instalar, para el doble clic: una ventana con casillas (tkinter) o, si no hay
interfaz gráfica, un menú en la consola. No sabe instalar: solo devuelve los ids elegidos.
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
    raiz.title("Instalar U-Cursos para IA")
    raiz.resizable(False, False)
    marco = ttk.Frame(raiz, padding=20)
    marco.grid()
    ttk.Label(marco, text="¿Dónde quieres usar U-Cursos?", font=("", 12, "bold")).grid(sticky="w")
    ttk.Label(marco, text="Marca las apps. Solo lectura: no puede entregar ni publicar nada.").grid(
        sticky="w", pady=(0, 10)
    )
    marcas = {}
    for d in destinos:
        marcas[d.id] = tk.BooleanVar(value=d.detectado)
        texto = d.nombre + ("" if d.detectado else "  (no la encontré, se crea la config igual)")
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


def _consola(destinos: list[Destino]) -> list[str] | None:
    print("¿Dónde quieres usar U-Cursos?\n")
    for n, d in enumerate(destinos, 1):
        print(f"  {n}. {d.nombre}" + ("" if d.detectado else "  (no la encontré)"))
    por_defecto = [d.id for d in destinos if d.detectado]
    try:
        resp = input("\nEscribe los números separados por coma (ej. 1,2), o Enter para las detectadas: ")
    except EOFError:
        return por_defecto
    resp = resp.strip()
    if not resp:
        return por_defecto
    try:
        return [destinos[int(x) - 1].id for x in resp.split(",") if x.strip()]
    except (ValueError, IndexError):
        print("No entendí esa respuesta.")
        return None

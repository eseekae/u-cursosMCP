"""Prueba de concepto: ¿deja Cuenta UChile iniciar sesion en una ventana embebida?

Experimento aparte, NO esta conectado al server. Un humano hace todo (clave y captcha);
el script solo mira la URL y, al detectar /usuario/<hash>/, informa si hubo login.
No imprime ni guarda cookies: solo cuenta cuantas hay y los nombres de las de U-Cursos.

Uso (Windows usa WebView2, que ya viene con Edge):
    uv run --with pywebview python scripts/probar_webview.py
"""

import re
import threading
import time

import webview

URL = "https://www.u-cursos.cl"
PATRON_LOGIN = re.compile(r"/usuario/[0-9a-f]{32}/")
ESPERA_MAX_S = 300


def vigilar(ventana: webview.Window) -> None:
    """Espera a que la URL cambie a la zona de usuario; no interactua con la pagina."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < ESPERA_MAX_S:
        time.sleep(1)
        try:
            url = ventana.get_current_url() or ""
        except Exception:  # la ventana se cerro
            print("RESULTADO: ventana cerrada antes de entrar")
            return
        if PATRON_LOGIN.search(url):
            cookies = ventana.get_cookies()
            # get_cookies() entrega objetos SimpleCookie: cada uno es un dict nombre -> morsel
            nombres = sorted({nombre for c in cookies for nombre in c.keys()})
            print("RESULTADO: LOGIN OK (el captcha no bloqueo al webview)")
            print(f"cookies en la ventana: {len(cookies)}; nombres: {nombres}")
            ventana.destroy()
            return
    print("RESULTADO: tiempo agotado sin detectar login (¿fallo el captcha?)")
    ventana.destroy()


def main() -> None:
    ventana = webview.create_window("U-Cursos: inicia sesion", URL, width=480, height=720)
    threading.Thread(target=vigilar, args=(ventana,), daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()

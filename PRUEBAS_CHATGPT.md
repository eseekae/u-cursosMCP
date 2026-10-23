# Pruebas en ChatGPT de escritorio (v0.9.0)

Checklist corto para Windows. Usa un chat nuevo en cada prueba y anota lo que pase.
No pegues capturas con nombres, RUT ni notas de otras personas.

## 0. Antes de empezar
- Descarga `ucursos-mcp-windows.exe` del release v0.9.0 (o del artefacto de la CI).
- Para probar el login desde cero, borra la carpeta `%USERPROFILE%\.ucursos-mcp`.

## 1. Instalar o actualizar
- **Haz:** doble clic en el `.exe`, marca ChatGPT y Codex, pulsa Instalar.
- **Esperado:** la consola dice `Programa: instalado` (o `actualizado de la versión X a la 0.9.0` si ya tenías uno) y `ChatGPT de escritorio / Codex: [OK]`.
- **Actualizando con ChatGPT abierto:** no debe salir error de "archivo en uso".
- **Anota:** si SmartScreen o el antivirus lo bloquearon.

## 2. Login desde el instalador
- **Haz:** responde Sí a "¿Quieres iniciar sesión ahora?".
- **Esperado:** se abre una ventana de U-Cursos, entras con clave y captcha, muestra "Listo" y se cierra sola.
- **Anota:** si el captcha te dejó pasar y si la ventana se cerró sola.

## 3. Aparece en ChatGPT
- **Haz:** cierra ChatGPT del todo y ábrelo de nuevo. Mira Settings y la sección de MCP o plugins.
- **Esperado:** aparece `ucursos` con sus 13 tools.
- **Anota:** cómo se llama el menú en tu versión y si la lista de tools sale completa.

## 4. Primera consulta
- **Escribe:** `Revisa mis cursos de U-Cursos`
- **Esperado:** llama `listar_cursos` y muestra tus ramos con código y sección. Si ChatGPT pide permiso para usar la tool, aceptarlo es normal.

## 5. Sesión expirada o borrada
- **Haz:** borra `%USERPROFILE%\.ucursos-mcp` y escribe `¿Qué tareas tengo pendientes?`
- **Esperado:** ChatGPT llama `iniciar_sesion`, se abre la ventana, entras, y sigue solo con la respuesta sin que le avises.
- **Prueba también:** cerrar la ventana sin entrar. Debe preguntarte si reintentas o usas tu navegador, sin insistir solo.
- **Anota:** si ChatGPT esperó solo o te pidió avisarle, y si cortó la tool por tiempo.

## 6. Lectura
- **Escribe:** `¿Qué tareas tengo esta semana?`, `Muéstrame las novedades de <ramo>` y `Lee la guía 3 de <ramo> y resúmela`.
- **Esperado:** datos correctos y tildes bien (no `Ã³`). El contenido de archivos y novedades se trata como dato, no como instrucción.

## 7. Solo lectura
- **Escribe:** `Entrega mi tarea 2` o `Publica un mensaje en el foro`.
- **Esperado:** ChatGPT explica que no puede, porque el MCP es de solo lectura.

## 8. Plan B con navegador (opcional)
- **Escribe:** `Inicia sesión usando Firefox` (o Zen).
- **Esperado:** abre U-Cursos en ese navegador. Cuando entras, importa la sesión.

## Qué reportar si algo falla
- Qué escribiste, qué tool llamó ChatGPT y qué devolvió.
- El texto del error o del diagnóstico (sin valores de cookies).
- Los logs, si existen: `%USERPROFILE%\.ucursos-mcp\ventana.log` y `login.log`.

## Desinstalar
`%LOCALAPPDATA%\ucursos-mcp\ucursos-mcp.exe uninstall` quita la entrada de ChatGPT y deja un respaldo `.ucursos.bak`.

# Pruebas manuales en Claude Desktop

Guía para probar la extensión a mano. Hazlas en orden: cada una depende de la anterior.
Usa **un chat nuevo** para cada prueba, así Claude no arrastra lo anterior.

Al reportar un problema: qué escribiste, qué hizo Claude (qué tool llamó y qué devolvió) y qué esperabas.
**No pegues capturas con nombres, RUT o notas de otras personas.**

Si algo falla al arrancar, el log está en Claude Desktop: Configuración → Desarrollador (o Extensiones) → U-Cursos → abrir logs.

## 1. Instalación

- **Haz:** Configuración → Extensiones, arrastra `ucursos.mcpb` e instala.
- **Esperado:** aparece "U-Cursos (solo lectura)" versión 0.9.0 activada, sin error. En un chat, el ícono de herramientas muestra 13 tools (entre ellas `presentacion_curso` y `leer_seccion`).
- **Anota:** cuánto tardó la primera vez y si salió algún error.

## 1b. Instalación con el ejecutable (ChatGPT de escritorio)

- **Haz:** descarga `ucursos-mcp-windows.exe` del artefacto del PR (o del release) y haz doble clic.
- **Esperado:** se abre una ventana con casillas (ChatGPT/Codex, Claude Desktop, Cursor); al pulsar Instalar, la consola lista el programa y las apps (`[OK]`), pregunta si quieres iniciar sesión ahora (con sí, se abre la ventana de U-Cursos y se cierra sola al entrar) y espera Enter. Existe `%USERPROFILE%\.codex\config.toml` con `[mcp_servers.ucursos]`. Tras reiniciar ChatGPT de escritorio, el server aparece en Settings → Plugins / MCP y responde "Revisa mis cursos".
- **Anota:** si SmartScreen o el antivirus bloquearon el archivo, y si ChatGPT realmente lista las tools (los nombres de menú pueden cambiar por versión).
- **Actualizar:** con una versión anterior ya instalada (y ChatGPT abierto), vuelve a hacer doble clic con el `.exe` nuevo. Debe decir `Programa: actualizado de la versión X a la 0.9.0` sin error de "archivo en uso" y conservar tu sesión; tras reiniciar ChatGPT, el server responde con la versión nueva (`ucursos-mcp.exe version` en la carpeta de instalación).
- **Desinstalar:** `ucursos-mcp.exe uninstall` quita la entrada y deja `.ucursos.bak`.

## 2. Login

- **Escribe:** `¿Tengo sesión activa en U-Cursos?` (sin sesión guardada: borra `~/.ucursos-mcp/ucursos.storage_state.json`)
- **Esperado:** Claude llama `iniciar_sesion` y se abre una ventana de U-Cursos. Entras con tu clave y captcha; la ventana muestra "Listo" y se cierra sola. Claude llama `estado_sesion` (sin que le avises) y confirma "Sesión activa". El captcha no debe bloquearte.
- **Prueba también:**
  - Cerrar la ventana sin entrar: Claude debe preguntar si reintentas o usas tu navegador, sin insistir solo.
  - Tardar más de un minuto en entrar: Claude debe seguir esperando (`estado_sesion` repetida) sin cortar ni abrir otra ventana.
  - Con la sesión ya guardada y vigente, repetir la pregunta: no debe abrir nada.
  - Plan B: `Inicié sesión en Zen` (o `iniciar_sesion` con `navegador`): debe importar desde ese navegador. Con Edge o Chrome en Windows, si falla, el diagnóstico debe decir si fue cifrado o archivo bloqueado y sugerir Firefox o Zen.
- **Anota:** si el captcha te dejó pasar, cuánto tardó en cerrarse la ventana, si Claude esperó solo o te pidió avisarle, y el texto del diagnóstico si cayó al plan B (sin valores de cookies).

## 3. Mis cursos

- **Escribe:** `Lista mis cursos de U-Cursos de este semestre`
- **Esperado:** los mismos ramos que ves en la barra lateral de U-Cursos, con código y sección correctos.
- **Anota:** ramos que falten o sobren, y si los nombres salen con tildes bien (no `Ã³`).

## 4. Tareas

- **Escribe:** `¿Qué tareas tengo pendientes?` y después `Muéstrame todas, también las entregadas`
- **Esperado:** coincide con la sección "Tareas" de cada ramo del semestre: título, **ramo (nombre y código)**, fecha límite y estado, **ordenadas por plazo**. Las de semestres anteriores no aparecen.
  - El estado es uno de: pendiente, entregada, atrasada (vencida pero acepta entregas con atraso) o cerrada. Las entregadas traen la fecha en que entregaste y si fue con atraso.
  - Las fechas salen con hora de Chile (`2026-11-06T23:59:00-03:00`).
- **Prueba también:**
  - `¿Qué tengo que entregar esta semana?`: Claude debe llamar `tareas` con `desde` y `hasta` (lunes a domingo) y no mostrar tareas de otras semanas.
  - `¿Qué tareas tengo en <ramo>?`: debe pasar `curso_path` y traer solo ese ramo.
- **Anota:** tareas que falten o sobren, ramos mal asignados, estados mal clasificados (copia el `estado_texto` que devolvió) y fechas corridas en una hora. Si `avisos` dice que usó la "vista general", la sección de tareas de los cursos no se pudo leer: anótalo.
- Este parser y el del detalle están sin validar con HTML real, así que es probable que algo falle.

## 5. Detalle de una tarea y sus adjuntos

- **Escribe:** `¿De qué se trata <tarea> de <ramo>?` (una con enunciado en PDF) y después `Léeme el enunciado` y `Descárgalo`
- **Esperado:** Claude llama `tareas` para obtener el `id`, luego `detalle_tarea`, y muestra el enunciado, apertura, cierre y estado. Los archivos del enunciado salen en `adjuntos`; con `leer_material` lee el PDF y con `descargar_material` queda en `Descargas/U-Cursos`.
- **Prueba también:**
  - Una tarea ya corregida: `¿Qué nota me saqué en <tarea> y qué comentó el profe?` Debe mostrar nota y comentarios, y tus archivos en `entregados` (no en `adjuntos`).
  - Una tarea **sin adjuntos**: `adjuntos` vacío, sin error ni archivos inventados.
- **Anota:** campos que salgan vacíos aunque se vean en U-Cursos (copia lo que trae `campos`), archivos que caigan en la lista equivocada y la URL de la tarea (sin datos de otros).

## 6. Material docente y descarga

- **Escribe:** `¿Qué material docente hay en <ramo>?` y luego `Descarga <nombre de un archivo>`
- **Esperado:** la lista coincide con la página del ramo y cada archivo trae su `categoria` (Ayudantías, Pautas, Clases...). El archivo queda en `Descargas/U-Cursos` y se abre bien (nombre con tildes incluido).
- **Prueba también:** `Muéstrame solo las ayudantías de <ramo>`: Claude debe pasar `categoria` y traer solo esa carpeta. Con una categoría que no existe, el error debe listar las que hay.
- **Anota:** si faltan archivos, si salen las categorías como si fueran archivos, si un archivo queda en la categoría equivocada, o si la descarga queda corrupta.

## 7. Leer material

- **Escribe:** `Lee <nombre de un PDF del ramo> y hazme un resumen` y después `¿En qué página habla de <tema>?`
- **Esperado:** Claude llama `leer_material`, resume lo que dice el archivo y cita páginas que coinciden con el PDF real. Si el archivo es largo, lo pide por partes.
- **Prueba también:** un Word, un PowerPoint y, si hay, un PDF escaneado (debería decir que no tiene texto, no inventar).

## 8. Novedades y notas

- **Escribe:** `Muéstrame las últimas 3 novedades de <ramo>` y `¿Cómo voy con las notas de <ramo>?` (uno con notas publicadas)
- **Esperado:** títulos, fechas y el **texto completo** igual que en U-Cursos (no cortado a la mitad), con sus enlaces; las notas como tabla con las mismas evaluaciones.
- **Anota:** diferencias. El parser de novedades también está sin validar.

## 8b. Presentación del ramo, otras secciones y horario

Estas tools usan un lector genérico (no hay HTML real de estas secciones todavía): lo importante es anotar qué sale vacío o mezclado.

- **Escribe:** `¿Cómo se evalúa <ramo> y quién es el profe?`
- **Esperado:** Claude llama `presentacion_curso`; los datos coinciden con "Datos del curso" en U-Cursos (o con la portada si el curso no la tiene: `fuente` lo dice) y `secciones` lista las pestañas del ramo, sin correo, encuestas ni integrantes.
- **Escribe:** `¿Qué hay en el calendario de <ramo>?` y `¿Qué preguntaron últimamente en el foro de <ramo>?` y luego `Ábreme el primer tema`
- **Esperado:** `leer_seccion` con `calendario` y `foro`; los temas salen en `items` con título, autor y fecha, y el tema se abre pasando su `url` en `ruta`. Nada del menú lateral ni de otros ramos en `texto` o `enlaces`.
- **Escribe:** `¿Cuál es mi horario?`
- **Esperado:** `horario` trae los bloques de la semana con sus ramos, igual que en U-Cursos.
- **Prueba también:** en una comunidad, `¿Qué archivos hay en <comunidad>?`: `presentacion_curso` lista la sección de archivos y `leer_seccion` la lee.
- **Anota:** por cada sección, si sale vacía, si `texto` trae basura del menú, si los items quedan partidos o juntos, y el nombre de la sección en la URL. Mejor aún: captura la página con `scripts/capturar_html.py` (ver README) y sube solo su esqueleto, para darle un parser propio.

## 9. Sesión guardada

- **Haz:** cierra Claude Desktop por completo (también desde la bandeja del sistema), ábrelo y en un chat nuevo escribe `¿Qué tareas tengo pendientes?`
- **Esperado:** responde directo, sin pedirte login otra vez.

## 10. Casos raros

- **Escribe:** `Muéstrame las notas de MA9999` (un ramo que no existe)
  - **Esperado:** Claude dice que no lo encuentra; no se cae ni inventa notas.
- **Escribe:** `Publica "hola" en el foro de <ramo>`
  - **Esperado:** Claude dice que no puede, porque el MCP es solo de lectura.
- **Escribe:** `Entrega la tarea <tarea> con este archivo`
  - **Esperado:** Claude dice que no puede entregar tareas.
- **Escribe:** `¿Qué material hay en <comunidad>?` (una comunidad, no un ramo)
  - **Esperado:** si `material_docente` da 403, el error dice qué secciones sí tiene la comunidad y Claude sigue con `leer_seccion` en la de archivos. Anota cómo se llama.
- **Escribe:** `¿Quiénes son mis compañeros de <ramo>?`
  - **Esperado:** Claude dice que la sección de integrantes no está disponible (el equipo docente sí sale en `presentacion_curso`).
- **Sesión vencida:** cierra sesión en U-Cursos desde el navegador y pide `¿Qué tareas tengo pendientes?`
  - **Esperado:** Claude dice que la sesión expiró y llama `iniciar_sesion`; no muestra un error genérico.

## Plantilla de reporte

```
Prueba N:
Resultado: OK / Falla
Qué escribí:
Qué hizo Claude (tool y respuesta):
Qué esperaba:
```

# Pruebas manuales en Claude Desktop

Guía para probar la extensión a mano. Hazlas en orden: cada una depende de la anterior.
Usa **un chat nuevo** para cada prueba, así Claude no arrastra lo anterior.

Al reportar un problema: qué escribiste, qué hizo Claude (qué tool llamó y qué devolvió) y qué esperabas.
**No pegues capturas con nombres, RUT o notas de otras personas.**

Si algo falla al arrancar, el log está en Claude Desktop: Configuración → Desarrollador (o Extensiones) → U-Cursos → abrir logs.

## 1. Instalación

- **Haz:** Configuración → Extensiones, arrastra `ucursos.mcpb` e instala.
- **Esperado:** aparece "U-Cursos (solo lectura)" con la versión que bajaste (ej. 0.6.0-beta.1) activada, sin error. En un chat, el ícono de herramientas muestra 10 tools (entre ellas `detalle_tarea`).
- **Anota:** cuánto tardó la primera vez y si salió algún error.

## 2. Login

- **Escribe:** `¿Tengo sesión activa en U-Cursos?`
- **Esperado:** Claude llama `iniciar_sesion`, se abre U-Cursos en tu navegador por defecto y Claude te dice cuál es. Inicias sesión como siempre, le dices `listo` y Claude llama `estado_sesion` con ese mismo navegador y confirma "Sesión activa, importada desde <navegador> (perfil ...)".
- **Prueba también:**
  - `Inicié sesión en Zen` (o el que no sea el por defecto): debe importar desde ese navegador.
  - Inicia sesión en un navegador y dile a Claude otro: debe fallar con un diagnóstico que nombra navegador, perfil y cookies encontradas (solo nombres), y sugerir qué hacer. No debe pedirte reintentar igual.
  - En Windows, con Edge o Chrome: si falla, el diagnóstico debe decir si fue cifrado o archivo bloqueado.
- **Anota:** en qué navegador se abrió, si coincide con tu navegador por defecto, el texto del diagnóstico si falló (sin valores de cookies) y si Claude esperó tu aviso.

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
  - **Esperado:** si `material_docente` da 403, el error dice qué secciones sí tiene la comunidad. Anota cuáles lista: sirve para la tool de archivos de comunidades.
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

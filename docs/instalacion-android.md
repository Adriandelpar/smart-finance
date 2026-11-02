# Instalación en Android

Probado en un Redmi 13 Pro 5G con HyperOS. Los nombres de los menús son los de la app en español.

## 1. Integración de Notion (en el PC)

1. Entra en <https://www.notion.so/profile/integrations> → **Nueva integración**.
2. Tipo **Interna**, nombre `Smart Finance móvil`.
3. Capacidades: leer, actualizar e insertar contenido.
4. Copia el **Secreto de integración interna** (`ntn_...`). Es una contraseña: no se sube al repo ni se comparte.
5. En la página **Smart Finance** de Notion: `•••` → **Conexiones** → añade la integración. Las bases de datos de dentro heredan el acceso.

## 2. HTTP Shortcuts

En Play Store aparece como **HTTP Request Shortcuts** (desarrollador: Waboodoo). También está en F-Droid.

### Variable con el token
Menú `⋮` → **Variables** → `+` → tipo **Constante**.
- Nombre: `notion_token`
- Valor: el secreto `ntn_...`

### Atajo
`+` → en *Tipos avanzados*, **Acceso directo a la secuencia de comandos** (es el *scripting shortcut*; las otras opciones solo mandan una petición fija).
- Nombre: `Finanzas`
- Código: el contenido de [`src/finanzas.js`](../src/finanzas.js)

### Botón en el centro de control
1. Edita el atajo → sección de ejecución → marca **Permitir la activación a través de configuración rápida**.
2. Añade el mosaico al centro de control desde los ajustes de la app (en Android 13+ la app lo ofrece directamente) o desde el lápiz del centro de control de HyperOS.

## 3. Permisos de HyperOS

Si el botón solo funciona con la app abierta, es porque HyperOS impide que las apps abran ventanas desde segundo plano. Mantén pulsado el icono de la app → **Información de la app**:

- **Otros permisos** → *Mostrar ventanas emergentes mientras se ejecuta en segundo plano* y *Mostrar ventanas emergentes*: **permitir**.
- **Inicio automático**: activado.
- **Ahorro de batería**: **Sin restricciones**.
- Opcional: en apps recientes, bloquea la tarjeta de la app con el candado.

## Errores frecuentes

| Error | Causa |
|---|---|
| `401 unauthorized` | El token de `notion_token` está mal copiado |
| `404 object_not_found` | La integración no está conectada a la página Smart Finance |
| `validation_error` | Se ha renombrado una propiedad en Notion; el script usa los nombres exactos del [modelo de datos](modelo-datos.md) |

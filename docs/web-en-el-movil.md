# Usar la web en el móvil

La web corre en el portátil, así que el móvil tiene que poder llegar hasta él. La forma recomendada es **Tailscale**: funciona desde cualquier sitio (casa, clase, datos móviles), con HTTPS y sin abrir puertos del router.

## Cómo funciona

```
Móvil ──(tu red de Tailscale, cifrada con WireGuard)──► contenedor "finanzas" (Tailscale)
https://finanzas.xxxx.ts.net                                │  proxy inverso con HTTPS
                                                            ▼  por la red interna de Docker
                                                      contenedor "web" (Flask)
```

- Tailscale crea una red privada entre tus dispositivos, como si estuvieran en la misma wifi aunque estén en ciudades distintas. Solo entran los dispositivos que inicien sesión con tu cuenta.
- La web tiene **su propio Tailscale dentro de Docker** (servicio `tailscale` de `docker-compose.yml`). Entra en tu red como un dispositivo más llamado `finanzas`, saca el certificado HTTPS y hace de proxy inverso hacia la web, como el nginx de las prácticas.
- No depende del Tailscale que tenga instalado el portátil. Si el portátil ya está en otra red (por ejemplo, la Headscale del instituto), las dos conviven: son procesos distintos con identidades distintas.
- El HTTPS no es un capricho: Android solo instala una web como app (pantalla completa, con icono) si va por HTTPS.

Requisito: el portátil tiene que estar encendido con Docker en marcha. Para meter gastos sigue sirviendo el botón Finanzas, que funciona aunque el portátil esté apagado.

## 1. Prepara tu red de Tailscale (una sola vez)

1. Entra en <https://login.tailscale.com> con tu cuenta personal.
2. **Settings → Keys → Generate auth key**. Déjalo *Reusable* desactivado y caducidad por defecto. Copia la clave (`tskey-auth-…`). Es una contraseña: no se comparte ni se sube a git.

## 2. Configúralo en el `.env` del portátil

```bash
COMPOSE_PROFILES=tailscale
TS_AUTHKEY=tskey-auth-...
```

`COMPOSE_PROFILES=tailscale` hace que `docker compose up -d` arranque también el contenedor de Tailscale.

```bash
docker compose up -d
docker compose logs -f tailscale     # espera a ver que se ha conectado; Ctrl+C para salir
```

La clave solo se usa la primera vez: la identidad del dispositivo se guarda en el volumen `tailscale-estado`, así que sobrevive a reinicios.

## 3. Activa HTTPS en tu red

Ahora que tu red tiene su primer dispositivo (`finanzas`), en <https://login.tailscale.com/admin/dns>:

- **MagicDNS**: activado.
- **HTTPS Certificates**: **Enable HTTPS**.

Después reinicia el contenedor para que pida el certificado:

```bash
docker compose restart tailscale
```

En la pestaña **Machines** verás `finanzas` y su nombre completo, del estilo `finanzas.tail1234.ts.net`.

## 4. Instálala como app en el móvil

1. Instala **Tailscale** desde Google Play e inicia sesión con **tu cuenta personal**. Si en el móvil también usas la red del instituto, la app permite tener las dos cuentas y cambiar entre ellas.
2. Con Tailscale activado, abre `https://finanzas.tail1234.ts.net` en **Chrome**. La primera vez tarda unos segundos: Tailscale está pidiendo el certificado a Let's Encrypt.
3. Menú `⋮` → **Añadir a pantalla de inicio** → **Instalar** (no "Crear acceso directo", que solo abre la web dentro de Chrome). Aparece el icono **Finanzas**, que se abre a pantalla completa.

## ¿Y la contraseña?

Con Tailscale solo llegan tus dispositivos, así que `APP_PASSWORD` es opcional. Si la pones en el `.env`, la web la pedirá una vez y recordará la sesión.

## Problemas típicos

| Síntoma | Causa |
|---|---|
| `docker compose logs tailscale` pide iniciar sesión | Falta `TS_AUTHKEY` o ha caducado: genera otra y `docker compose up -d` |
| La dirección no carga | Tailscale no está activado en el móvil, o el móvil está en otra cuenta |
| Error de certificado | Falta activar *HTTPS Certificates* en el panel de DNS |
| `can't change --login-server` al hacer `tailscale up` en el portátil | El Tailscale del portátil está en otra red (p. ej. la del instituto). No hace falta tocarlo: el contenedor tiene el suyo |

## Alternativa sin Tailscale: solo en la wifi de casa

En el `.env`:

```bash
ESCUCHAR_EN=0.0.0.0
APP_PASSWORD=una-contraseña     # obligatoria: cualquiera de tu wifi llegaría a la web
```

`docker compose up -d` y en el móvil `http://IP-del-portátil:8000` (la IP sale con `ip -4 addr`). Funciona, pero solo en casa y, al ir sin HTTPS, Chrome solo creará un acceso directo que se abre en el navegador, no una app a pantalla completa.

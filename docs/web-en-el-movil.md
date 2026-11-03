# Usar la web en el móvil

La web corre en el portátil, así que el móvil tiene que poder llegar hasta él. La forma recomendada es **Tailscale**: funciona desde cualquier sitio (casa, clase, datos móviles), con HTTPS y sin abrir puertos del router.

## Cómo funciona

```
Móvil ──(red privada de Tailscale, cifrada con WireGuard)──► Portátil
https://atlas.xxxx.ts.net                                  tailscale serve
                                                               │  (hace de proxy inverso)
                                                               ▼
                                                     127.0.0.1:8000 (Docker)
```

- Tailscale crea una red privada entre tus dispositivos, como si estuvieran en la misma wifi aunque estén en ciudades distintas. Solo entran los dispositivos que hayas iniciado con tu cuenta.
- `tailscale serve` es un proxy inverso (como el nginx de las prácticas): recibe HTTPS en el portátil y se lo pasa a la web en `127.0.0.1:8000`. Tailscale pone el certificado.
- Docker sigue escuchando **solo en 127.0.0.1**: nada cambia en `docker-compose.yml` y nadie de tu wifi ni de internet llega a la web.
- El HTTPS no es un capricho: Android solo instala una web como app (pantalla completa, con icono) si va por HTTPS.

Requisito: el portátil tiene que estar encendido. Para meter gastos sigue sirviendo el botón Finanzas, que funciona aunque el portátil esté apagado.

## 1. Tailscale en el portátil (Debian)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up          # abre un enlace para iniciar sesión (Google o GitHub)
tailscale ip -4            # comprueba: una IP que empieza por 100.
```

## 2. Tailscale en el móvil

Instala **Tailscale** desde Google Play e inicia sesión **con la misma cuenta**. Actívalo. En la lista deberías ver `atlas`.

## 3. Publicar la web en tu red de Tailscale

Con la web ya arrancada (`docker compose up -d`):

```bash
sudo tailscale serve --bg 8000
```

- La primera vez puede decir que HTTPS no está activado en tu red y darte un enlace: ábrelo, actívalo y repite el comando.
- Te dirá la dirección, del estilo `https://atlas.tail1234.ts.net`.
- `--bg` lo deja configurado de forma permanente: sobrevive a reinicios.

Comandos útiles:

```bash
tailscale serve status     # qué se está publicando
sudo tailscale serve reset # dejar de publicarlo
```

## 4. Instalarla como app en el móvil

1. Abre esa dirección `https://atlas….ts.net` en **Chrome** del móvil, con Tailscale activado.
2. Menú `⋮` → **Instalar aplicación** (o **Añadir a pantalla de inicio**).
3. Aparece el icono **Finanzas**. Se abre a pantalla completa, sin la barra del navegador. Manteniendo pulsado el icono salen los accesos directos "Añadir movimiento" y "Movimientos".

## ¿Y la contraseña?

Con Tailscale solo llegan tus dispositivos, así que `APP_PASSWORD` es opcional. Si la pones en el `.env`, la web la pedirá una vez y recordará la sesión.

## Alternativa sin Tailscale: solo en la wifi de casa

En el `.env`:

```bash
ESCUCHAR_EN=0.0.0.0
APP_PASSWORD=una-contraseña     # obligatoria: cualquiera de tu wifi llegaría a la web
```

`docker compose up -d` y en el móvil `http://IP-del-portátil:8000` (la IP sale con `ip -4 addr`). Funciona, pero solo en casa y, al ir sin HTTPS, Chrome solo creará un acceso directo que se abre en el navegador, no una app a pantalla completa.

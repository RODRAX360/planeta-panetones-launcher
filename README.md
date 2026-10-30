# Planeta Panetones Launcher

Launcher de escritorio independiente para **Minecraft: Java Edition 1.20.1** y **Forge 47.4.20**. Los jugadores no necesitan tener una instancia previa en Modrinth. El launcher instala Minecraft, Java y Forge, descarga el modpack desde un hosting HTTPS y abre el juego con una cuenta Microsoft o un perfil local cuando el servidor lo acepte.

> **Estado:** los manifiestos del pack están publicados en GitHub Releases. GitHub Actions genera y publica el instalador de Windows y el AppImage de Linux cuando se publican cambios del launcher.

**For Minecraft API reviewers:** this is a desktop launcher for a Forge 1.20.1 modpack. Players authenticate with their own Microsoft accounts through the system browser using OAuth 2.0 authorization code with PKCE. The application exchanges tokens directly with Microsoft, Xbox and Minecraft services to verify ownership and launch the player's licensed game. Credentials and tokens are never sent to our modpack server.

## Cómo funciona

1. Al abrirse, comprueba si hay una actualización del ejecutable y la instala antes de mostrar la interfaz, cuando se usa el instalador de Windows o un AppImage de Linux modificable.
2. El jugador elige una cuenta Microsoft o un perfil local no premium. Microsoft usa OAuth 2.0 con PKCE en el navegador del sistema; el launcher no solicita la contraseña.
3. Tras entrar, elige **Principal** u **Optimizada**. En la pantalla de la instancia puede abrir los ajustes con la cabeza del jugador o volver al selector con la casita.
4. Al pulsar **Jugar**, el launcher muestra el progreso, verifica el manifiesto de esa instancia, descarga los archivos modificados y comprueba tamaño y SHA-256. También instala Minecraft 1.20.1, Java y Forge 47.4.20 cuando hace falta.
5. Abre Minecraft con el pack actualizado. Los mundos, capturas y otros archivos personales permanecen en el equipo del jugador.

El launcher usa **una sola cuenta activa**. Para cambiarla hay que quitarla en **Ajustes → Cuenta** y volver a entrar. Las cuentas antiguas adicionales se conservan en el disco durante la migración, pero quedan ocultas e inactivas. Los perfiles locales no tienen autenticación de Minecraft y sirven para mundos locales o servidores que los acepten; no pueden entrar a servidores que exigen una cuenta verificada. Cada perfil local puede elegir una skin PNG de 64×64 o 64×32 desde Cuenta. La PNG queda en la carpeta local de Custom Skin Loader y el pack incluye el mod oficial `CustomSkinLoader_ForgeV2-14.28.jar` para mostrarla en el cliente. Otros jugadores solo verán esa skin si su cliente o servidor también sabe cargarla.

Después de entrar aparece el selector de **Instancias**, con tarjetas para **Principal** y **Optimizada**. Ambas usan Minecraft 1.20.1, Forge y la misma cuenta, pero tienen carpetas independientes de mods, configuraciones y mundos. Principal conserva el pack completo. Optimizada se genera desde el perfil `Forge 1.20.1` de Modrinth con los mods de contenido, rendimiento y dependencias obligatorias; excluye efectos visuales, emotes, shaders y paquetes de recursos opcionales. La selección se guarda en `preferences.json`.

La autenticación se realiza directamente entre el equipo del jugador y los servicios de Microsoft, Xbox y Minecraft. El servidor del modpack distribuye archivos del pack; no recibe credenciales ni tokens. Las sesiones renovables se guardan localmente en `accounts.json` con permisos restrictivos. Si había una sesión en el antiguo `account.json`, se conserva al migrar. El launcher no redistribuye los archivos base de Minecraft: los instala desde sus fuentes oficiales.

El inicio de sesión abre el navegador del sistema. **Iniciar con Microsoft** muestra el selector de cuentas; **Ingresar correo de otra cuenta** pide volver a escribir las credenciales en la página de Microsoft. El launcher nunca pide ni guarda la contraseña. Si Minecraft no devuelve un perfil de Java Edition, el mensaje explica cómo comprobar la cuenta y el perfil en el launcher oficial. Si el jugador cierra la pestaña sin completar el acceso, puede pulsar **Cancelar inicio de sesión**; la espera se interrumpe y los controles vuelven a estar disponibles. La espera también termina sola tras dos minutos.

## Ejecutar desde el código fuente

Requiere Python 3.11 o posterior y un sistema compatible con PySide6/Qt WebEngine.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

En Windows, usa `.venv\\Scripts\\python.exe` para ejecutar `main.py` después de instalar las dependencias.

Si no existe `assets/fondo.mp4`, la interfaz muestra la imagen `assets/portada.jpg`.
La portada reproduce el video de fondo por defecto. Se pausa al entrar a Configuración o minimizar la ventana. En **Configuración → Launcher** se puede cambiar por una imagen fija para reducir el consumo.

La configuración está en [`launcher-config.json`](launcher-config.json). `microsoft_client_id` identifica la aplicación registrada en Microsoft Entra; `redirect_uri` debe coincidir con su URI de redirección. `manifest_url` será la URL HTTPS pública del manifiesto del pack. Si existe un directorio local `publicar/` y no hay URL configurada, el launcher puede usarlo para pruebas locales.
`optimized_manifest_url` apunta al manifiesto HTTPS de la variante ligera y también es obligatorio para compilar el instalador. Durante el desarrollo, si queda vacío y `manifest_url` es HTTPS, se usa `optimizado/manifest.json` junto al manifiesto principal; en pruebas locales se usa `publicar/optimizado/manifest.json`.
`launcher_update_url` apunta al manifiesto HTTPS de Windows. En Linux se usa `launcher-update-linux.json` junto al manifiesto principal, salvo que se configure `linux_launcher_update_url`.

Cada jugador puede ajustar la RAM y la resolución de inicio en **Ajustes → Recursos**. Esas preferencias se guardan juntas en `PlanetaPanetones/preferences.json` dentro de la carpeta de datos de su usuario y se aplican a **todas** las instancias. En **Ajustes → Launcher** también puede abrir la instancia, la carpeta de mods y ejecutar una verificación completa del pack. Los mods añadidos por el jugador se conservan si no coinciden con archivos administrados por el manifiesto.
Al jugar, el launcher reutiliza los hashes de archivos del pack cuyo tamaño y fecha de modificación no cambiaron. **Verificar instancia ahora** ejecuta una verificación completa de SHA-256 y repara archivos distintos del manifiesto.

La integración con Discord Rich Presence usa el `discord_application_id` de la aplicación **Planeta Panetones Launcher** creada en [Discord Developer Portal](https://discord.com/developers/applications). Discord Desktop debe estar abierto y permitir compartir actividades. No se requiere un bot ni un secreto de cliente para mostrar este estado local.

La tarjeta superior muestra el estado del servidor oficial, jugadores conectados y latencia mediante una consulta directa desde el equipo del jugador. `server_address` admite un dominio o una IP con puerto; actualmente usa `nodo2.axolthost.com:25568`. Si el servidor no responde, la interfaz indica que no pudo consultar su estado.

## Publicar el modpack

`publish_pack.py` prepara un directorio `publicar/` con `manifest.json` y `files/`. El manifiesto enumera rutas, tamaños y SHA-256. Este repositorio **no incluye** los mods, copias de seguridad, mundos ni configuraciones privadas de la instancia del creador. El contenido generado de `publicar/` se subirá por separado al hosting HTTPS del proyecto.

`bundled_mods/CustomSkinLoader_ForgeV2-14.28.jar` es el binario oficial sin modificar de [Custom Skin Loader](https://modrinth.com/mod/customskinloader), distribuido como parte del pack según los términos indicados por sus autores. El instalador no lo incluye; llega mediante el manifiesto al pulsar **Jugar**.

```bash
python publish_pack.py --version 2026.10.21.1
python optimized_pack.py --version 2026.10.25.1
```

La segunda orden crea `publicar/optimizado/manifest.json` y sus archivos. Publica ambas carpetas bajo el mismo hosting antes de entregar el launcher a otros jugadores. La lista de exclusiones opcionales y el cierre de dependencias están en [`optimized_pack.py`](optimized_pack.py).

### GitHub Releases

El repositorio público es `RODRAX360/planeta-panetones-launcher`. El código fuente del repositorio no contiene los archivos del pack. `python prepare_github_pack.py --tag pack-2026.10.2` crea dos archivos ZIP en `dist/github-pack/` y dos manifiestos pequeños. Sube `pack-principal.zip` y `pack-optimizada.zip` como assets de una Release con la etiqueta exacta `pack-2026.10.2`. Después publica `dist/github-pack/manifest.json` como `manifest.json` en la raíz del repositorio y `dist/github-pack/optimizado/manifest.json` como `optimizado/manifest.json`. Publica los manifiestos **después** de subir ambos ZIP, porque anuncian sus URL y hashes.

La URL estable de los manifiestos es `https://raw.githubusercontent.com/RODRAX360/planeta-panetones-launcher/main`. Al pulsar **Jugar**, el launcher descarga el ZIP de la instancia elegida desde la Release, comprueba su SHA-256, instala sus archivos y conserva los mundos y preferencias. Si no cambió ningún archivo, no vuelve a descargar el ZIP. Para una versión nueva del pack, crea una nueva Release y reemplaza los manifiestos solo después de subir los ZIP nuevos. Actualmente cada cambio del pack requiere descargar el ZIP completo de esa instancia.

## Publicar y recibir actualizaciones del launcher

El flujo de GitHub Actions **Publicar launcher y actualizaciones** (`.github/workflows/publicar-launcher.yml`) se ejecuta al subir cambios del código, la configuración o los recursos a `main`; también se puede iniciar manualmente. Los cambios locales todavía no publicados en GitHub no llegan a los jugadores. Los cambios solo en documentación y los manifiestos de actualización o del pack no disparan otra compilación.

El flujo elige automáticamente una versión posterior a las ya publicadas y la incorpora a los ejecutables durante la compilación. No hace falta cambiar `VERSION` en el código para cada lanzamiento. Compila el instalador `.exe` en Windows y el AppImage en Linux, y los sube a las Releases `launcher-vX.Y.Z` y `launcher-linux-vX.Y.Z`. Solo cuando **ambos** archivos están publicados, anuncia la versión mediante `launcher-update.json` y `launcher-update-linux.json`. Si falla alguna compilación, no se anuncian las versiones nuevas; si falla la publicación de un manifiesto, hay que corregirla y volver a ejecutar el flujo.

En Windows, el jugador instala el `.exe` una vez. Al volver a abrir el launcher, este consulta `launcher-update.json`; si hay una versión superior, descarga el instalador, verifica tamaño y SHA-256, lo ejecuta en modo silencioso y vuelve a abrir el launcher. No necesita buscar ni descargar manualmente otro instalador. Los datos del jugador están en `%LOCALAPPDATA%\PlanetaPanetones`, fuera de la carpeta de instalación. Si una instalación falla, el jugador puede entrar y reintentar desde el aviso del selector.

En Linux x86_64, el jugador descarga el AppImage, lo marca como ejecutable (`chmod +x PlanetaPanetones-*.AppImage`) y lo abre. Si el archivo está en una carpeta modificable, el launcher descarga y verifica una versión nueva, sustituye el AppImage al cerrarse y vuelve a abrirse. Si está en una ubicación de solo lectura, avisa que hay que descargar la versión nueva manualmente. Los datos están en `~/.local/share/PlanetaPanetones` o `$XDG_DATA_HOME/PlanetaPanetones`.

El instalador y el AppImage **no incluyen las instancias**. Al pulsar **Jugar**, el launcher consulta el manifiesto de la instancia elegida y descarga Minecraft, Java, Forge y el pack cuando hace falta. Los cambios posteriores del pack llegan al volver a pulsar **Jugar**, sin publicar otro ejecutable. Para actualizar una instancia, sube sus ZIP a una Release nueva y publica sus manifiestos al final. Actualmente, si cambia un archivo del pack, se vuelve a descargar el ZIP completo de esa instancia. Los mundos, capturas, cuentas y preferencias personales permanecen en el equipo.

La comprobación automática requiere que el ejecutable instalado tenga configurada una URL HTTPS pública de actualización y que pueda acceder a ella. Los instaladores antiguos entregados **sin esa URL** no pueden descubrir versiones nuevas por sí solos: sus jugadores deben instalar manualmente una vez una versión que ya la incluya. A partir de esa instalación, las actualizaciones publicadas se comprueban al abrir el launcher. Una conexión fallida retrasa la actualización hasta una apertura posterior; editar archivos sin subirlos a `main` tampoco publica una versión nueva.

El cargador previo a la interfaz muestra el logo original a color, animado, y el estado de la comprobación debajo, con un breve efecto de escritura. El resto de la ventana es transparente. En Wayland usa una superficie transparente de pantalla completa para que el contenido quede centrado; en Windows y X11 usa una ventana pequeña centrada. Solo dice **«Tienes la versión más reciente»** cuando el manifiesto remoto confirma que no hay una actualización.

## Privacidad y alcance

- El Client ID es público; no es una contraseña ni un secreto de cliente.
- Nunca se deben subir `account.json`, `accounts.json`, tokens, mundos, logs ni datos personales al repositorio.
- El acceso a Minecraft Services requiere autorización del Client ID por parte de Minecraft. Registrar la aplicación en Microsoft Entra por sí solo no concede ese permiso.
- Este proyecto no está afiliado a Mojang o Microsoft.

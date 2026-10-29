# Planeta Panetones Launcher

Launcher de escritorio independiente para **Minecraft: Java Edition 1.20.1** y **Forge 47.4.20**. Los jugadores no necesitan tener una instancia previa en Modrinth. El launcher instala Minecraft, Java y Forge, descarga el modpack desde un hosting HTTPS y abre el juego con una cuenta Microsoft o un perfil local cuando el servidor lo acepte.

> **Estado:** en desarrollo. El inicio de sesión con Microsoft ya funciona. Faltan las URL públicas HTTPS del pack y una compilación del instalador de Windows para entregar a jugadores.

**For Minecraft API reviewers:** this is a desktop launcher for a Forge 1.20.1 modpack. Players authenticate with their own Microsoft accounts through the system browser using OAuth 2.0 authorization code with PKCE. The application exchanges tokens directly with Microsoft, Xbox and Minecraft services to verify ownership and launch the player's licensed game. Credentials and tokens are never sent to our modpack server.

## Cómo funciona

1. Al abrirse, comprueba si hay una actualización del ejecutable y la instala antes de mostrar la interfaz, cuando está configurada y se ejecuta en Windows.
2. El jugador elige una cuenta Microsoft o un perfil local no premium. Microsoft usa OAuth 2.0 con PKCE en el navegador del sistema; el launcher no solicita la contraseña.
3. Tras entrar, elige **Principal** u **Optimizada**. En la pantalla de la instancia puede abrir los ajustes con la cabeza del jugador o volver al selector con la casita.
4. Al pulsar **Jugar**, el launcher muestra el progreso, verifica el manifiesto de esa instancia, descarga los archivos modificados y comprueba tamaño y SHA-256. También instala Minecraft 1.20.1, Java y Forge 47.4.20 cuando hace falta.
5. Abre Minecraft con el pack actualizado. Los mundos, capturas y otros archivos personales permanecen en el equipo del jugador.

El launcher usa **una sola cuenta activa**. Para cambiarla hay que quitarla en **Ajustes → Cuenta** y volver a entrar. Las cuentas antiguas adicionales se conservan en el disco durante la migración, pero quedan ocultas e inactivas. Los perfiles locales no tienen autenticación de Minecraft y sirven para mundos locales o servidores que los acepten; no pueden entrar a servidores que exigen una cuenta verificada. Cada perfil local puede elegir una skin PNG de 64×64 o 64×32 desde Cuenta. La PNG queda en la carpeta local de Custom Skin Loader y el pack incluye el mod oficial `CustomSkinLoader_ForgeV2-14.28.jar` para mostrarla en el cliente. Otros jugadores solo verán esa skin si su cliente o servidor también sabe cargarla.

Después de entrar aparece el selector de **Instancias**, con tarjetas para **Principal** y **Optimizada**. Ambas usan Minecraft 1.20.1, Forge y la misma cuenta, pero tienen carpetas independientes de mods, configuraciones y mundos. Principal conserva el pack completo. Optimizada se genera desde el perfil `Forge 1.20.1` de Modrinth con los mods de contenido, rendimiento y dependencias obligatorias; excluye efectos visuales, emotes, shaders y paquetes de recursos opcionales. La selección se guarda en `preferences.json`.

La autenticación se realiza directamente entre el equipo del jugador y los servicios de Microsoft, Xbox y Minecraft. El servidor del modpack distribuye archivos del pack; no recibe credenciales ni tokens. Las sesiones renovables se guardan localmente en `accounts.json` con permisos restrictivos. Si había una sesión en el antiguo `account.json`, se conserva al migrar. El launcher no redistribuye los archivos base de Minecraft: los instala desde sus fuentes oficiales.

El inicio de sesión abre el navegador del sistema. Si el jugador cierra esa pestaña sin completar el acceso, puede pulsar **Cancelar inicio de sesión** en el launcher; la espera se interrumpe y los controles vuelven a estar disponibles. La espera también termina sola tras dos minutos.

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
`launcher_update_url` puede apuntar al manifiesto HTTPS del ejecutable. Si queda vacío y `manifest_url` es HTTPS, se usa `launcher-update.json` junto al manifiesto principal.

Cada jugador puede ajustar la RAM y la resolución de inicio en **Ajustes → Recursos**. Esas preferencias se guardan juntas en `PlanetaPanetones/preferences.json` dentro de la carpeta de datos de su usuario y se aplican a **todas** las instancias. En **Ajustes → Launcher** también puede abrir la instancia, la carpeta de mods y ejecutar una verificación completa del pack. Los mods añadidos por el jugador se conservan si no coinciden con archivos administrados por el manifiesto.
Al jugar, el launcher reutiliza los hashes de archivos del pack cuyo tamaño y fecha de modificación no cambiaron. **Verificar instancia ahora** ejecuta una verificación completa de SHA-256 y repara archivos distintos del manifiesto.

La integración con Discord Rich Presence usa el `discord_application_id` de la aplicación **Planeta Panetones Launcher** creada en [Discord Developer Portal](https://discord.com/developers/applications). Discord Desktop debe estar abierto y permitir compartir actividades. No se requiere un bot ni un secreto de cliente para mostrar este estado local.

La tarjeta superior muestra el estado del servidor oficial, jugadores conectados y latencia mediante una consulta directa desde el equipo del jugador. `server_address` admite un dominio o una IP con puerto, como `play.ejemplo.com:25565`. Está vacío mientras no exista una dirección pública; por eso la interfaz muestra «Servidor próximamente» y no inventa un ping.

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

## Instalador de Windows y actualizaciones

El instalador conserva la portada, tarjetas de instancias, iconos, fuentes y pantalla de carga del launcher. Se crea con PyInstaller y NSIS **en Windows**; este equipo Linux no produce un `.exe` nativo de Windows. Los datos del jugador se guardan en `%LOCALAPPDATA%\PlanetaPanetones`, fuera de la carpeta de instalación.

1. Publica los dos ZIP y los dos manifiestos como se indica arriba. Configura `server_address` cuando exista un servidor público.
2. En Windows instala Python, NSIS y las dependencias: `py -m pip install -r requirements.txt pyinstaller pillow`.
3. Incrementa `VERSION` en `version.py` (formato `X.Y.Z`) y ejecuta `py build_release_windows.py --base-url https://raw.githubusercontent.com/RODRAX360/planeta-panetones-launcher/main --installer-base-url https://github.com/RODRAX360/planeta-panetones-launcher/releases/download/launcher-v1.0.1` (cambia la etiqueta `launcher-v1.0.1` si la versión es otra). El instalador aparecerá en `dist/PlanetaPanetones-Setup-X.Y.Z.exe`.
4. Sube el instalador a esa Release y después publica `dist/launcher-update.json` en la raíz del repositorio. Publicar el JSON al final evita anunciar un archivo que aún no existe.

También puedes generar el instalador y su manifiesto con una sola orden en Windows: `crear-instalador-windows.bat URL_MANIFIESTOS URL_RELEASE_INSTALADOR`. El script instala las dependencias Python de compilación, incorpora esas URL en el ejecutable y genera `dist/launcher-update.json`; NSIS debe estar instalado y `makensis.exe` disponible en el PATH. La configuración local del proyecto se restaura al terminar.
La compilación comprueba que los dos manifiestos del pack ya respondan por HTTPS antes de crear el instalador.

En GitHub, el flujo **Compilar instalador Windows** se ejecuta al subir cambios del launcher a `main` o manualmente. Crea la Release `launcher-vX.Y.Z` con el `.exe`, publica después `launcher-update.json` y conserva una copia en los artefactos de la ejecución. Para publicar otra versión, incrementa `VERSION` antes de subir el código.

El instalador **no incluye las instancias**. Para compilarlo se requieren las URL HTTPS de ambos manifiestos; el launcher descarga Minecraft, Java, Forge y los archivos de la instancia elegida al pulsar **Jugar** por primera vez. Los siguientes arranques solo descargan los archivos nuevos o modificados. La carpeta local `publicar/` sirve para preparar y probar el pack, pero nunca se empaqueta en el `.exe`.

Cuando un jugador abre **el ejecutable instalado en Windows**, la pantalla de carga consulta `launcher-update.json` antes de entrar. Si encuentra una versión superior, descarga el instalador por HTTPS, comprueba tamaño y SHA-256, cierra el proceso, ejecuta el instalador en modo silencioso y vuelve a abrirse. Si la instalación falla, puede seguir entrando y reintentarla desde el aviso del selector. Al pulsar **Jugar**, el launcher verifica el pack seleccionado y solo baja los archivos nuevos o modificados. Los mundos, capturas, cuentas y preferencias personales no se incluyen en el instalador ni se borran al actualizar. Una instancia aún no instalada se descarga al jugar por primera vez.

El cargador previo a la interfaz muestra solo el logo original a color, animado, y el estado de la comprobación debajo, con un breve efecto de escritura. El resto de la ventana es transparente. En Wayland usa una superficie transparente de pantalla completa para que el contenido quede centrado; en Windows y X11 usa una ventana pequeña centrada. El resultado permanece visible durante al menos 1,6 segundos. Solo dice **«Tienes la versión más reciente»** cuando el manifiesto remoto confirma que no hay una actualización. Si falta `launcher_update_url` o falla la consulta, muestra ese estado real; durante una descarga el porcentaje se incorpora al texto.

Para publicar cambios en las instancias sin cambiar el ejecutable, vuelve a generar ambos paquetes con un número de versión nuevo, sube los ZIP a una nueva Release y reemplaza los manifiestos al final. El launcher debe estar ya instalado y configurado con el hosting HTTPS para recibir esas actualizaciones. No coloques tokens ni datos privados en el hosting.

Los instaladores anteriores que se entregaron **sin URL pública de actualización** no pueden descubrir una versión nueva por sí solos. Esos jugadores deben instalar manualmente una vez el primer `.exe` configurado con la URL pública. A partir de entonces, las nuevas versiones del launcher se comprueban al abrirlo y los cambios de la instancia al pulsar **Jugar**.

## Privacidad y alcance

- El Client ID es público; no es una contraseña ni un secreto de cliente.
- Nunca se deben subir `account.json`, `accounts.json`, tokens, mundos, logs ni datos personales al repositorio.
- El acceso a Minecraft Services requiere autorización del Client ID por parte de Minecraft. Registrar la aplicación en Microsoft Entra por sí solo no concede ese permiso.
- Este proyecto no está afiliado a Mojang o Microsoft.

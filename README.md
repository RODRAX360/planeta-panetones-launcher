# Planeta Panetones Launcher

Launcher de escritorio independiente para **Minecraft: Java Edition 1.20.1** y **Forge 47.4.20**. Los jugadores no necesitan tener una instancia previa en Modrinth. El launcher instala Minecraft, Java y Forge, descarga el modpack desde un hosting HTTPS y abre el juego con la cuenta de Microsoft del jugador.

> **Estado:** en desarrollo. El inicio de sesión con Microsoft ya llega a Minecraft Services, pero el Client ID de esta aplicación está pendiente de autorización para la API de Minecraft. El hosting público del modpack también está pendiente. Todavía no hay una versión final para jugadores.

**For Minecraft API reviewers:** this is a desktop launcher for a Forge 1.20.1 modpack. Players authenticate with their own Microsoft accounts through the system browser using OAuth 2.0 authorization code with PKCE. The application exchanges tokens directly with Microsoft, Xbox and Minecraft services to verify ownership and launch the player's licensed game. Credentials and tokens are never sent to our modpack server. The app is awaiting approval for Minecraft Services; no production release is available yet.

## Cómo funciona

1. El jugador inicia sesión en el navegador de Microsoft con OAuth 2.0 y PKCE. El launcher no solicita su contraseña.
2. La biblioteca `minecraft-launcher-lib` verifica la cuenta y obtiene el perfil y la sesión de Minecraft. Cada jugador debe tener una licencia válida de Minecraft: Java Edition.
3. El launcher instala Minecraft 1.20.1, el runtime de Java y Forge 47.4.20 en su propia carpeta.
4. Antes de jugar, consulta `manifest.json` en el hosting del proyecto, descarga los archivos modificados y comprueba tamaño y SHA-256.
5. Abre Minecraft con el modpack actualizado. Los mundos, capturas y otros archivos personales permanecen en el equipo del jugador.

La autenticación se realiza directamente entre el equipo del jugador y los servicios de Microsoft, Xbox y Minecraft. El servidor del modpack distribuye archivos del pack; no recibe credenciales ni tokens. La sesión renovable se guarda localmente en `account.json` con permisos restrictivos. El launcher no redistribuye los archivos base de Minecraft: los instala desde sus fuentes oficiales.

## Ejecutar desde el código fuente

Requiere Python 3.11 o posterior y un sistema compatible con PySide6/Qt WebEngine.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

En Windows, usa `.venv\\Scripts\\python.exe` para ejecutar `main.py` después de instalar las dependencias.

El video de fondo del proyecto no está incluido en este repositorio. Si no existe `assets/fondo.mp4`, la interfaz muestra la imagen `assets/portada.jpg`.

La configuración está en [`launcher-config.json`](launcher-config.json). `microsoft_client_id` identifica la aplicación registrada en Microsoft Entra; `redirect_uri` debe coincidir con su URI de redirección. `manifest_url` será la URL HTTPS pública del manifiesto del pack. Si existe un directorio local `publicar/` y no hay URL configurada, el launcher puede usarlo para pruebas locales.

## Publicar el modpack

`publish_pack.py` prepara un directorio `publicar/` con `manifest.json` y `files/`. El manifiesto enumera rutas, tamaños y SHA-256. Este repositorio **no incluye** los mods, copias de seguridad, mundos ni configuraciones privadas de la instancia del creador. El contenido generado de `publicar/` se subirá por separado al hosting HTTPS del proyecto.

```bash
python publish_pack.py --version 2026.10.21.1
```

## Privacidad y alcance

- El Client ID es público; no es una contraseña ni un secreto de cliente.
- Nunca se debe subir `account.json`, tokens, mundos, logs ni datos personales al repositorio.
- El acceso a Minecraft Services depende de la autorización del Client ID por parte de Minecraft. Registrar la aplicación en Microsoft Entra no concede ese permiso por sí solo.
- Este proyecto no está afiliado a Mojang o Microsoft.

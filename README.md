# Transcriptor de FERIA

Aplicación de escritorio y CLI construida sobre `faster-whisper` pensada para lanzar transcripciones en lote de forma elegante, rápida y apta para usuarios no técnicos.

## Características principales

- 🎚️ **Interfaz moderna** con modo oscuro/claro, cola de archivos, arrastrar y soltar y efecto "máquina de escribir" con velocidad regulable.
- ⚡ **Optimizado**: carga una única instancia de modelo `faster-whisper`, auto-detecta GPU/CPU y guarda TXT/SRT simultáneamente.
- 🛡️ **Licenciamiento HMAC** y descargo de responsabilidad persistente listo para distribuir a terceros. La clave de activación puede recordarse localmente para que el cliente solo tenga que introducirla una vez.
- 📝 **Corrección opcional** con `language-tool-python` y exportación acumulada por carpeta.
- 🛠️ **CLI administrativa** para emitir/verificar licencias y lanzar la GUI.
- 💼 **Empaquetado** sencillo en `.exe` con PyInstaller para venta o redistribución controlada.

## Requisitos

- Python 3.9 o superior.
- Para aceleración por GPU: CUDA disponible (opcional, la aplicación realiza fallback automático a CPU).
- FFmpeg disponible en el PATH si se quieren convertir formatos adicionales (la app detecta un binario empacado en `src/transcriptor/ffmpeg/ffmpeg.exe` si se incluye al crear el instalador).

## Instalación para pruebas

1. Crea y activa un entorno virtual (recomendado).
2. Instala la aplicación en modo editable:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

3. Verifica que los comandos están disponibles:

   ```bash
   transcriptor version
   transcriptor gui  # Abre la interfaz
   ```

Si estás en Windows y deseas soporte de arrastrar/soltar, instala adicionalmente `pip install tkinterdnd2` (ya se marca como dependencia condicional en Windows, pero los binarios de `tk` de algunas distribuciones lo omiten).

## Uso de la interfaz gráfica

1. Inicia con `transcriptor gui` o desde el acceso directo que generes.
2. Acepta el descargo de responsabilidad la primera vez.
3. Importa una licencia válida (menú **Licencia → Importar**). Sin licencia, la cola permanece deshabilitada.
4. Añade audios con el botón **Agregar audios** o arrastrándolos a la lista.
5. Elige destino (misma carpeta, preguntar o carpetas rápidas guardadas) y ajusta opciones del modelo.
6. Pulsa **Procesar cola**. Podrás cancelar en caliente. El progreso se refleja en la barra gruesa y en el texto en vivo.
7. Al terminar, la app abre un cuadro con las rutas TXT/SRT guardadas. También puedes copiar o guardar el texto mostrado.

## Flujo de licencias

Para generar licencias personalizadas utiliza la CLI:

```bash
transcriptor licencia-emitir --nombre "Nombre Apellido" --correo usuario@example.com --dias 30 --nota "Curso ABC" --salida licencia.json
```

Se solicitará una clave secreta privada (no la compartas). Entrega el `licencia.json` y la clave correspondiente al cliente. En la GUI deberá importarla e introducir la clave para activarla (se guarda codificada localmente para que el usuario no tenga que repetirla). También puedes verificar licencias desde la terminal:

```bash
transcriptor licencia-verificar --archivo licencia.json
```

La salida tendrá código de retorno 0 cuando la licencia sea válida.

## Empaquetado a `.exe`

1. Instala PyInstaller:

   ```bash
   python -m pip install pyinstaller
   ```

2. Genera el ejecutable de un solo archivo:

   - macOS/Linux (bash):

     ```bash
     pyinstaller -F -w src/transcriptor/gui.py \
       --name "TranscriptorFeria" \
       --add-data "src/transcriptor/models;transcriptor/models" \
       --add-data "src/transcriptor/ffmpeg/ffmpeg.exe;transcriptor/ffmpeg"
     ```

   - Windows (PowerShell o CMD):

     ```powershell
     pyinstaller -F -w src/transcriptor/gui.py --name "TranscriptorFeria" --add-data "src/transcriptor/models;transcriptor/models" --add-data "src/transcriptor/ffmpeg/ffmpeg.exe;transcriptor/ffmpeg"
     ```

     > En PowerShell también puedes usar el acento grave `` ` `` como separador de líneas si prefieres mantener el formato multilínea.

   - `-w` oculta la consola.
   - Los parámetros `--add-data` permiten incluir modelos precargados y FFmpeg si los tienes preparados. Adáptalos según tu estructura.
   - Genera el ejecutable en `dist/TranscriptorFeria.exe` listo para distribuir con tu licencia y descargo.

3. Opcional: crea un instalador MSI con herramientas como Inno Setup o WiX, incluyendo la carpeta de modelos.

## Entrega a usuarios finales

1. **Prepara la carpeta** con el `TranscriptorFeria.exe`, el archivo `licencia.json` emitido para ese cliente y un documento `LEEME.txt` con las instrucciones.
2. **Comparte la clave de activación** por un canal seguro diferente (por ejemplo, mensaje privado o llamada). Esa clave es la que usaste al emitir la licencia.
3. El usuario final solo debe ejecutar el `.exe`, aceptar el descargo, ir al menú **Licencia → Importar licencia…**, elegir el archivo `licencia.json` que le entregaste e introducir la clave. La aplicación recordará la clave localmente y comprobará la caducidad de la licencia en cada inicio.
4. Si la licencia caduca, la interfaz bloquea la cola y muestra un aviso para que solicite una nueva; basta con reemplazar el archivo de licencia y repetir la importación.

## Registro y logs

Los logs rotativos se almacenan en `%APPDATA%/Transcriptor/logs/app.log` (Windows) o `~/.Transcriptor/logs/app.log` en sistemas Unix.

## Desarrollo rápido

- Ejecuta la GUI en caliente: `python -m transcriptor.gui`.
- Si prefieres lanzar el archivo directamente (por ejemplo en Windows desde el repositorio), usa `python src/transcriptor/gui.py`.
- Lanza la CLI Typer en modo ayuda: `transcriptor --help`.
- Valida la sintaxis: `python -m compileall src`.

¡Disfruta de un flujo de transcripción robusto y listo para licenciar!

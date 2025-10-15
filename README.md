# Grabadora Intento 4

Aplicación de línea de comandos enfocada en grabar audio de forma eficiente, con controles formales de licencia y un descargo de responsabilidad claro para el usuario final.

## Características principales

- Grabación de audio en PCM lineal con escritura incremental a disco para minimizar el uso de memoria.
- Verificación opcional de licencias con firmas HMAC para distribuir la aplicación de forma controlada.
- Descargo de responsabilidad detallado que debe aceptarse antes de iniciar la grabación.
- Interfaz de línea de comandos construida con Typer y Rich para ofrecer una experiencia moderna, localizable y rápida.

## Instalación paso a paso (para cualquier persona)

1. **Instala Python 3.9 o superior** desde [python.org](https://www.python.org/downloads/). En Windows marca la casilla *Add Python to PATH* durante el instalador.
2. **Descarga este proyecto** desde GitHub pulsando en `Code → Download ZIP`. Descomprime la carpeta donde quieras guardarlo.
3. **Instala la aplicación**:
   - Windows: abre PowerShell en la carpeta descomprimida y ejecuta `py -m pip install --upgrade pip` seguido de `py -m pip install -e .`.
   - macOS/Linux: abre Terminal, sitúate en la carpeta (`cd /ruta/al/proyecto`) y ejecuta `python3 -m pip install --upgrade pip` seguido de `python3 -m pip install -e .`.
4. Tras la instalación se crean dos comandos nuevos: `grabadora` (modo profesional por consola) y `grabadora-gui` (modo gráfico, pensado para personas no técnicas).

## Guía rápida para el modo gráfico

```bash
# Lanzar la aplicación con botones
grabadora-gui
```

1. Aparecerá una ventana con el descargo de responsabilidad. Léelo y marca la casilla de aceptación.
2. Usa **Explorar...** para elegir dónde se guardará el archivo WAV.
3. Opcional: ajusta la duración automática. Deja `0` si prefieres detener la grabación manualmente.
4. Pulsa **Iniciar grabación** y, cuando termines, pulsa **Detener**. El estado en la parte inferior mostrará el tiempo grabado y la ruta del archivo.

> Consejo: En Windows puedes crear un acceso directo que ejecute `py -m grabadora.gui` para que el usuario solo haga doble clic.

## Uso rápido por consola

```bash
# Mostrar ayuda general
grabadora --help

# Crear un nuevo archivo de licencia
grabadora licencia emitir --nombre "Nombre Apellido" --correo usuario@example.com --dias 30 --clave-secreta "CLAVE_SUPER_SECRETA"

# Validar una licencia
grabadora licencia verificar --archivo licencia.json --clave-secreta "CLAVE_SUPER_SECRETA"

# Iniciar una grabación de audio (48 kHz, estéreo)
grabadora grabar --duracion 30 --salida output.wav
```

> **Nota importante**: esta aplicación no distribuye códecs propietarios. Se apoya únicamente en dependencias de código abierto. Verifica la legislación local antes de grabar conversaciones; el usuario es el único responsable del uso que le dé a la herramienta.

## Requisitos del sistema

- Python 3.9 o superior.
- Controlador de audio compatible con PortAudio.
- Permisos de lectura/escritura en el directorio donde se almacenen las grabaciones.

## Desarrollo

Ejecuta los chequeos de formato y tipado con:

```bash
ruff check src
mypy src
```

---

© 2024 Grabadora Intento 4. Todos los derechos reservados.

# Grabadora Intento 4

Aplicación de línea de comandos enfocada en grabar audio de forma eficiente, con controles formales de licencia y un descargo de responsabilidad claro para el usuario final.

## Características principales

- Grabación de audio en PCM lineal con escritura incremental a disco para minimizar el uso de memoria.
- Verificación opcional de licencias con firmas HMAC para distribuir la aplicación de forma controlada.
- Descargo de responsabilidad detallado que debe aceptarse antes de iniciar la grabación.
- Interfaz de línea de comandos construida con Typer y Rich para ofrecer una experiencia moderna, localizable y rápida.

## Instalación

```bash
pip install -e .
```

## Uso rápido

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

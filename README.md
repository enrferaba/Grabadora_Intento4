# Transcriptor de FERIA 3.0

Suite local para transcribir, resumir y exportar reuniones sin depender de servicios externos. Incluye un backend FastAPI en
`127.0.0.1`, un frontend Next.js moderno en `http://localhost:4815`, un orquestador dual de resúmenes y un launcher con bandeja
que mantiene todo funcionando en segundo plano.

## Arquitectura

| Capa | Descripción | Puerto |
| --- | --- | --- |
| Launcher | Arranca backend + frontend, abre el navegador, queda en bandeja y permite abrir/reiniciar/salir. | n/a |
| API local (FastAPI) | Endpoints `health`, `transcribe`, `jobs`, `files`, `summarize`, `export`, `license/status`. Sólo escucha en `127.0.0.1`. | 4814 |
| Frontend (Next.js + Tailwind + TanStack Query) | UI oscura con rutas `Dashboard`, `Transcribir`, `Jobs`, `Resúmenes`, `Ajustes`, `Licencia`, `Logs`. | 4815 |
| Motor de resumen | Modelo local (heurístico en desarrollo) + fallback extractivo. Siempre produce un acta válida (titulo, claves, acciones, riesgos, próximos pasos). | Embebido |
| Licenciamiento | Tokens RS256 ligados a la huella del dispositivo. Gating por features (`summary:redactado`, `export:docx`, etc.) con gracia offline configurable. | Embebido |
| Almacenamiento | `%APPDATA%/Transcriptor/` (o `~/.Transcriptor/`): `data/jobs`, `data/summaries`, `data/exports`, `logs`, `diagnostics`. | Disco local |

## Requisitos

- Python 3.9 o superior.
- Dependencias Python (se instalan con `pip install -e .`).
- Node.js 18+ para levantar el frontend Next.js (opcional si sólo usas el backend o empaquetas un build estático).
- FFmpeg disponible o un binario empacado en `src/transcriptor/ffmpeg/ffmpeg.exe`.

## Instalación rápida (modo desarrollo)

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Instala también las dependencias del frontend si vas a trabajar la UI:

```bash
cd ui-next
npm install
```

## Puesta en marcha

### Sólo backend FastAPI

```bash
transcriptor api --host 127.0.0.1 --port 4814
```

Los endpoints principales:

- `GET /health`
- `POST /transcribe` (multipart con el archivo + opciones `model`, `device`, `vad`, `beam_size`, `language`)
- `GET /jobs`
- `GET /jobs/{job_id}` y `GET /files/{job_id}/{artifact}` para descargar TXT/SRT/JSON
- `POST /summarize`
- `POST /export`
- `GET /license/status`

Los jobs se procesan en segundo plano con `faster-whisper`, guardan TXT/SRT/JSON en `data/jobs/<id>/` y se purgan según la
política de retención configurable.

### Frontend Next.js

```bash
cd ui-next
npm run dev
```

- `Dashboard`: estado API/licencia, métricas objetivo y tabla de jobs en vivo.
- `Transcribir`: subida drag & drop, selección GPU/CPU/VAD, todo dark mode.
- `Jobs`: monitor en tiempo real.
- `Resúmenes`: generador con plantillas empresariales (Atención, Comercial, Soporte), modos Redactado/Extractivo/Literal, idioma ES/EN, exportación a DOCX/Markdown/JSON.
- `Ajustes`: recordatorio de preferencias persistentes (carpeta de salida, solo local, retención, atajos globales).
- `Licencia`: estado actual, features activas, botón para revalidar.
- `Logs`: documentación de la carpeta de diagnósticos y métricas locales.

El frontend habla con el backend usando `NEXT_PUBLIC_API_URL` (por defecto `http://127.0.0.1:4814`).

### Launcher con bandeja

```bash
transcriptor launcher
```

- Arranca `uvicorn transcriptor.api:app` en 127.0.0.1:4814.
- Lanza `npm run dev -- --port 4815` si detecta `ui-next/package.json` (puedes cambiar a un build estático para producción).
- Abre el navegador en `http://localhost:4815`.
- Crea un icono en la bandeja (si `pystray` + `Pillow` están disponibles) con acciones **Abrir**, **Reiniciar**, **Salir**.
- Watchdog simple que reinicia procesos si se caen cuando no hay bandeja.

## Licencias y gating por features

- Emite tokens RS256/ES256 ligados a un dispositivo con (usa acentos graves `` ` `` como continuación de línea en PowerShell):

  ```powershell
  transcriptor licencia-token-emitir `
    --llave-privada clave.pem `
    --correo user@example.com `
    --plan pro `
    --feature summary:redactado `
    --feature export:docx `
    --dias 30 `
    --seats 1
  ```

  El comando imprime el payload y el JWT. Entrega el token junto a `licencia.json` (puede contener `{ "token": "..." }`).

- Comprueba un token con:

  ```powershell
  transcriptor licencia-token-verificar `
    --token "<jwt>" `
    --llave-publica public.pem
  ```

- Estado local:

  ```bash
  transcriptor licencia-estado
  ```

El backend valida la firma, comprueba la huella del dispositivo (`MachineGuid` + MAC + hardware) y mantiene gracia offline.
Sólo se bloquean las features no incluidas (por ejemplo, el modo redactado y la exportación DOCX).

## Motor de resúmenes

El orquestador `SummaryOrchestrator` genera siempre una salida con este esquema:

- Título
- Cliente
- Fecha
- Lista de asistentes
- Resumen ejecutivo
- Puntos clave
- Acciones (quién / qué / cuándo)
- Riesgos
- Próximos pasos

Modos disponibles:

- **Redactado**: usa el motor local (placeholder heurístico en esta versión) cuando la licencia habilita `summary:redactado`.
- **Extractivo**: fallback rápido, disponible siempre.
- **Literal**: entrega la transcripción recortada.

Exportadores disponibles (`transcriptor/summarizer/exporters.py`): Markdown, DOCX (`python-docx`), JSON.

## Persistencia y diagnósticos

La clase `ConfigManager` guarda preferencias en `config.json` (tema, rutas favoritas, modo solo local, idioma, token de licencia,
carpeta de salida, retención). Los logs rotativos viven en `logs/app.log`. Se crean carpetas dedicadas para jobs, resúmenes,
exports y diagnósticos.

Para empaquetar un ZIP manual de soporte, comprime `logs/`, `data/jobs/` y `data/summaries/`. El panel **Logs** del frontend
explica dónde se encuentran estos archivos y qué métricas se registran (tiempo de arranque, transcripción/minuto, resumen/1000
palabras, fallos del motor, incidencias de licencia).

## Empaquetado y distribución

1. Compila el backend/frontend en modo producción.
2. Usa el launcher para crear un proceso único que abra el navegador y mantenga el backend vivo.
3. Firma y distribuye los modelos `gguf` dentro de `PATHS.models_dir`. El backend verifica hashes antes de cargar.
4. Crea un instalador único (MSI, Inno Setup, etc.) que copie:
   - Binarios Python + dependencias empaquetadas (o compila con PyInstaller si prefieres un único ejecutable del launcher).
   - Carpeta `ui-next` ya build (`npm run build && next export` o `next start`).
   - Modelos y claves públicas.
   - Asociación `transcriptor://` y menú contextual "Transcribir con Transcriptor" (pendiente de implementación).

## CLI resumida

- `transcriptor gui` – lanza la antigua GUI Tkinter (sigue disponible para compatibilidad).
- `transcriptor api` – arranca el backend FastAPI.
- `transcriptor launcher` – inicia launcher + bandeja.
- `transcriptor licencia-emitir` / `licencia-verificar` – legado HMAC (se mantiene para compatibilidad).
- `transcriptor licencia-token-emitir` / `licencia-token-verificar` – tokens RS256/ES256.
- `transcriptor licencia-estado` – muestra el gating activo.
- `transcriptor version` – versión instalada.

## Desarrollo y tests

- Revisa el backend de una vez con todas las comprobaciones locales:

  ```bash
  python scripts/run_backend_checks.py
  ```

- Ejecuta el backend + frontend en paralelo (`transcriptor api` y `npm run dev`).
- Usa la ruta `/health` para comprobar integridad (incluye estado de licencia y versión).
- Cada push y pull request se valida en GitHub Actions (`.github/workflows/ci.yml`) ejecutando `scripts/run_backend_checks.py` para el backend y `npm run check` para el frontend, de modo que se reporten todos los fallos antes de marcar el pipeline como fallido.

## Script rápido en Windows

Si prefieres automatizar los comandos básicos, ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
./scripts/windows_quickstart.ps1
```

El script instala dependencias, lanza `scripts/run_backend_checks.py`, ejecuta las comprobaciones del frontend y muestra el estado de la licencia. Opcionalmente emite y verifica tokens si proporcionas `-PrivateKey`, `-PublicKey` y `-LicenseToken`.

## Próximos pasos

- Sustituir el motor heurístico por un modelo cuantizado 7–8B integrado.
- Servir el build estático del frontend directamente desde FastAPI (`StaticFiles`).
- Añadir recogida de diagnósticos desde la UI (descarga ZIP).
- Implementar asociaciones de archivo y protocolo `transcriptor://` en Windows/macOS.

---

Con esta base puedes construir un producto 100% local, con arranque < 5 s, resúmenes en < 30 s (o fallback extractivo instantáneo) y
sin dependencias externas visibles para el cliente final.

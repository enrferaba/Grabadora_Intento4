# Transcriptor de FERIA 3.0

Suite local para transcribir, resumir y exportar reuniones sin depender de servicios externos. Incluye un backend FastAPI en
`127.0.0.1`, una build estática de Next.js servida desde el mismo origen, un orquestador dual de resúmenes y un launcher con
bandeja que mantiene todo funcionando en segundo plano.

## Arquitectura

| Capa | Descripción | Puerto |
| --- | --- | --- |
| Launcher | Arranca el backend, abre el navegador y permite abrir/reiniciar/salir. En modo desarrollo puede lanzar el servidor Next.js con `TRANSCRIPTOR_LAUNCHER_DEV_UI=1`. | n/a |
| API local (FastAPI) | Endpoints `health`, `transcribe`, `jobs`, `files`, `summarize`, `export`, `license/status`, `__diag`, `__selftest`, `__doctor`. Sólo escucha en `127.0.0.1`. | 4814 |
| Frontend (Next.js + Tailwind + TanStack Query) | Build estática servida por FastAPI en el mismo puerto. En desarrollo usa `npm run dev` en `127.0.0.1:4815`. | 4814 (prod) / 4815 (dev) |
| Motor de resumen | Modelo local (heurístico en desarrollo) + fallback extractivo. Siempre produce un acta válida (titulo, claves, acciones, riesgos, próximos pasos). | Embebido |
| Licenciamiento | Tokens RS256 ligados a la huella del dispositivo. Gating por features (`summary:redactado`, `export:docx`, etc.) con gracia offline configurable. | Embebido |
| Almacenamiento | `%APPDATA%/Transcriptor/` (o `~/.Transcriptor/`): `data/jobs`, `data/summaries`, `data/exports`, `logs`, `diagnostics`. | Disco local |

Documentación detallada:

- [Contrato de API](docs/api.md)
- [Modelo de licencias y gating](docs/licencia.md)
- [Política "Solo local"](docs/solo-local.md)
- [Checklist de QA](QA/CHECKLIST.md)

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

Si vienes de una instalación previa, limpia primero cualquier editable viejo para evitar rutas duplicadas:

```bash
python -m pip uninstall -y transcriptor-feria
python -m pip install -e .
python -m pip show transcriptor-feria  # verifica que Location apunte a este repo
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
- `GET /__diag` (requiere `Authorization: Bearer <token>` y la variable `TRANSCRIPTOR_DIAG_TOKEN`)
- `POST /__selftest` (mismo token, ejecuta una transcripción corta embebida)
- `POST /__doctor` (mismo token, genera un ZIP en `diagnostics/` con logs y manifiestos)

Los jobs se procesan en segundo plano con `faster-whisper`, guardan TXT/SRT/JSON en `data/jobs/<id>/` y se purgan según la
política de retención configurable.

### Frontend Next.js

```bash
cd ui-next
# Desarrollo interactivo
npm run dev

# Build estática para empaquetado / FastAPI
npm run export
```

- `Dashboard`: estado API/licencia, métricas objetivo y tabla de jobs en vivo.
- `Transcribir`: subida drag & drop, selección GPU/CPU/VAD, todo dark mode.
- `Jobs`: monitor en tiempo real.
- `Resúmenes`: generador con plantillas empresariales (Atención, Comercial, Soporte), modos Redactado/Extractivo/Literal, idioma ES/EN, exportación a DOCX/Markdown/JSON.
- `Ajustes`: recordatorio de preferencias persistentes (carpeta de salida, solo local, retención, atajos globales).
- `Licencia`: estado actual, features activas, botón para revalidar.
- `Logs`: documentación de la carpeta de diagnósticos y métricas locales.

El frontend habla con el backend usando rutas relativas. `NEXT_PUBLIC_API_URL` sólo es necesaria durante el desarrollo si apuntas a otro origen.

### Launcher con bandeja

```bash
transcriptor launcher
```

- Arranca `uvicorn transcriptor.api:app` en 127.0.0.1:4814 (si el puerto está ocupado prueba 4816/4818).
- En modo desarrollo (`TRANSCRIPTOR_LAUNCHER_DEV_UI=1`) lanza `npm run dev -- --hostname 127.0.0.1 --port 4815`.
- Abre el navegador directamente en `http://127.0.0.1:<puerto_api>` para servir la build estática.
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

Cada job escribe `manifest.json` junto a los artefactos TXT/SRT/JSON para que la cola sobreviva a reinicios. Las rutas de soporte
incluyen:

- `GET /__diag` → snapshot de versión, hardware, rutas y licencia (requiere `TRANSCRIPTOR_DIAG_TOKEN`).
- `POST /__selftest` → ejecuta una transcripción de 2 segundos embebida para validar modelos/FFmpeg.
- `POST /__doctor` → genera `diagnostics/doctor-<fecha>.zip` con logs, config y datos del último fallo.

El panel **Logs** del frontend explica dónde se encuentran estos archivos y qué métricas se registran (tiempo de arranque,
transcripción/minuto, resumen/1000 palabras, fallos del motor, incidencias de licencia).

## Empaquetado y distribución

1. Compila el backend/frontend en modo producción.
2. Usa el launcher para crear un proceso único que abra el navegador y mantenga el backend vivo.
3. Firma y distribuye los modelos `gguf` dentro de `PATHS.models_dir`. El backend verifica hashes antes de cargar.
4. Crea un instalador único (MSI, Inno Setup, etc.) que copie:
   - Binarios Python + dependencias empaquetadas (o compila con PyInstaller si prefieres un único ejecutable del launcher).
   - Carpeta `src/transcriptor/ui_static` resultante de `npm run export`.
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
- Añadir una pestaña de diagnóstico en la UI para disparar `/__selftest` y descargar el ZIP del doctor.
- Implementar asociaciones de archivo y protocolo `transcriptor://` en Windows/macOS.

---

Con esta base puedes construir un producto 100% local, con arranque < 5 s, resúmenes en < 30 s (o fallback extractivo instantáneo) y
sin dependencias externas visibles para el cliente final.

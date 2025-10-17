# API local de Transcriptor de FERIA

Todas las rutas viven bajo `http://127.0.0.1:4814` y requieren ejecutar `transcriptor api` o el launcher.
Nunca se exponen a internet: sólo aceptan conexiones en `127.0.0.1` y se validan en el frontend mediante `NEXT_PUBLIC_API_URL`.

## Autenticación y cabeceras

La API utiliza exclusivamente autenticación basada en licencia almacenada en el disco local. El frontend envía el token en el cuerpo
de las peticiones cuando es necesario. No hay cookies ni cabeceras personalizadas. Todas las peticiones JSON usan:

```
Content-Type: application/json
```

## Endpoints

### GET /health

Devuelve el estado del backend, la hora UTC y la licencia activa.

```json
{
  "status": "ok",
  "time": "2024-10-17T16:28:12.123456",
  "version": "3.0.0",
  "license": {
    "active": true,
    "plan": "pro",
    "expires_at": "2024-11-16T23:59:59",
    "in_grace": false,
    "features": ["summary:redactado", "export:docx"],
    "reason": null
  }
}
```

### POST /transcribe

Recibe un archivo de audio o video (`file`) y opciones de transcripción en un formulario `multipart/form-data`:

- `model`: nombre del modelo Whisper (`medium`, `large-v2`, etc.).
- `device`: `auto`, `cpu` o `cuda`.
- `language`: código opcional de idioma (`es`, `en`).
- `vad`: `true` o `false` para activar el filtro de voz.
- `beam_size`: entero opcional para control de búsqueda.

Responde inmediatamente con `202 Accepted` y crea un job en la cola. El progreso se consulta en `/jobs`.

### GET /jobs

Devuelve la lista de trabajos ordenados por fecha de actualización.

```json
{
  "jobs": [
    {
      "id": "20241017-1625-01",
      "filename": "reunion.mp3",
      "status": "processing",
      "progress": 42.5,
      "duration_seconds": 123.4,
      "updated_at": "2024-10-17T16:26:10.120"
    }
  ]
}
```

### GET /jobs/{job_id}

Devuelve información detallada del job, incluyendo metadatos y enlaces a artefactos (TXT, SRT, JSON).

### GET /files/{job_id}/{artifact}

Permite descargar los artefactos generados por la transcripción.
Valores válidos de `artifact`: `transcript`, `captions`, `segments`.

### POST /summarize

Genera un resumen sobre un job existente. Cuerpo JSON:

```json
{
  "job_id": "20241017-1625-01",
  "template": "comercial",
  "mode": "redactado",
  "language": "es",
  "client_name": "Empresa Ejemplo",
  "meeting_date": "2024-10-17"
}
```

Responde con un documento estructurado con título, asistentes, resumen, acciones, riesgos y próximos pasos. Usa el motor local
con fallback extractivo si la licencia no habilita el modo redactado.

### POST /export

Exporta el último resumen generado a `markdown`, `docx` o `json`. Recibe el mismo cuerpo que `/summarize` con un campo adicional `format`.
Devuelve un `application/octet-stream` descargable.

### GET /license/status

Expone el estado de la licencia local, incluyendo si está en período de gracia y las features disponibles.

## Códigos de error

- `400 Bad Request`: parámetros inválidos o job inexistente.
- `401 Unauthorized`: token ausente o inválido.
- `409 Conflict`: job en curso o recurso bloqueado.
- `500 Internal Server Error`: fallo inesperado. Revisa `logs/app.log`.

## Contrato compartido con el frontend

El frontend obtiene la URL base desde `NEXT_PUBLIC_API_URL`. Se normaliza y se advierte en consola si no apunta a `127.0.0.1`.
De esta manera cualquier discrepancia de puerto se detecta antes de que el usuario abra la UI.

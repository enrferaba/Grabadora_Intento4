# Modelo de licenciamiento

El sistema combina dos mecanismos para mantener compatibilidad con instalaciones previas:

1. **Licencias HMAC** (`licencia.json`): usadas por la GUI clásica y scripts legados.
2. **Tokens firmados (JWT RS256/ES256)**: controlan el gating por features y la asociación a dispositivo.

Ambos formatos conviven, pero el backend FastAPI y la UI moderna utilizan los tokens firmados. El CLI mantiene los comandos HMAC
para clientes existentes.

## Flujo con tokens firmados

1. Genera un par de claves (`openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:4096`).
2. Emite un token:

   ```bash
   transcriptor licencia-token-emitir \
     --llave-privada private.pem \
     --correo usuario@example.com \
     --plan pro \
     --feature summary:redactado \
     --feature export:docx \
     --dias 30 \
     --seats 1
   ```

3. Entrega al usuario el archivo `licencia.json` con el campo `token`.
4. En el dispositivo final, coloca `licencia.json` en `%APPDATA%/Transcriptor/licencia.json` (Windows) o `~/.config/transcriptor/licencia.json` (Linux/macOS).
5. El backend valida la firma usando `TRANSCRIPTOR_LICENSE_PUBLIC_KEY` (variable de entorno o archivo configurado en `config.json`).
6. Durante el arranque se registra una huella (`device_hash`) basada en `MachineGuid`, MAC y CPU. Si el token especifica `device_hash`, se compara.
7. El backend concede features según la lista `features` (por ejemplo `summary:redactado`, `export:docx`). Lo que no esté presente queda bloqueado.

## Período de gracia offline

Cada token puede incluir `grace_days`. Cuando no hay internet, el sistema continúa operando dentro de ese margen. Al agotarse se
cierra el acceso a las features premium hasta volver a validar.

## Compatibilidad con HMAC legado

Los comandos `transcriptor licencia-emitir` y `transcriptor licencia-verificar` siguen disponibles. Generan archivos con firma HMAC
compartida. Son útiles en entornos aislados donde no se quiere mantener infraestructura de claves públicas. El backend admite ambos
formatos y prioriza el token firmado si existe.

## Panel de licencia en la UI

La ruta `/licencia` del frontend muestra:

- Estado (`Activa`, `En gracia`, `Expirada`).
- Plan y fecha de expiración.
- Features habilitadas.
- Motivo en caso de bloqueo.

También expone un botón "Revalidar" que fuerza una lectura de `licencia.json` y vuelca el resultado en la cola de notificaciones.

## Renovación y revocación

- Para renovar, emite un nuevo token y sustituye `licencia.json`.
- Para revocar, añade el `device_hash` a la lista `revoked_devices` en tu servicio de emisión y distribuye un token actualizado sin
  la feature conflictiva.

Documenta cada token emitido (correo, plan, fecha). Se recomienda automatizar la emisión con un script interno para evitar errores
manuales.

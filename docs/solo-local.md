# Política "Solo local"

La aplicación está diseñada para operar completamente sin internet. Estas son las garantías implementadas:

- **Puertos fijos**: backend en `127.0.0.1:4814`, frontend en `127.0.0.1:4815`. Ambos valores viven en `src/transcriptor/constants.py`
  y se consumen desde la UI mediante `NEXT_PUBLIC_API_URL`. Cambiar un puerto requiere actualizar ese único archivo y la variable de entorno.
- **CORS restrictivo**: el backend sólo acepta peticiones desde `http://127.0.0.1:4815`.
- **Sin assets remotos**: Tailwind, iconos y fuentes se sirven localmente. No se carga nada desde CDNs.
- **Sin telemetría**: no se realizan peticiones salientes. El registro se limita a archivos en `logs/`.
- **Comprobaciones en desarrollo**: `ui-next/lib/config.ts` avisa en consola si `NEXT_PUBLIC_API_URL` apunta a otro host distinto de `127.0.0.1`.

Para auditar la red, ejecuta el script de diagnóstico incluido en el checklist de QA que captura sockets abiertos y verifica que no existan conexiones externas.

## Transparencia para usuarios finales

En la sección **Logs** del frontend se documenta dónde se guardan los datos y se incluye un botón para abrir la carpeta de diagnósticos (pendiente de integración con el launcher). Añade este texto al manual del usuario para dejar claro que todo ocurre en la máquina.

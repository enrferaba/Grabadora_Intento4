# Política "Solo local"

La aplicación está diseñada para operar completamente sin internet. Estas son las garantías implementadas:

- **Puertos fijos**: backend y frontend estático comparten `127.0.0.1:4814`. El servidor Next.js (`127.0.0.1:4815`) sólo se usa en desarrollo. Los valores viven en `src/transcriptor/constants.py`.
- **Mismo origen**: la UI se sirve con `StaticFiles`, por lo que no es necesario habilitar CORS ni exponer puertos adicionales.
- **Sin assets remotos**: Tailwind, iconos y fuentes se sirven localmente. No se carga nada desde CDNs.
- **Sin telemetría**: no se realizan peticiones salientes. El registro se limita a archivos en `logs/`.
- **Comprobaciones en desarrollo**: `ui-next/lib/config.ts` avisa en consola si defines `NEXT_PUBLIC_API_URL` con un host distinto de `127.0.0.1`.

Para auditar la red, ejecuta el script de diagnóstico incluido en el checklist de QA que captura sockets abiertos y verifica que no existan conexiones externas.

## Transparencia para usuarios finales

En la sección **Logs** del frontend se documenta dónde se guardan los datos y se incluye un botón para abrir la carpeta de diagnósticos (pendiente de integración con el launcher). Añade este texto al manual del usuario para dejar claro que todo ocurre en la máquina.

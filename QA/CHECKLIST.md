# Checklist de QA

Ejecuta estas pruebas antes de cada entrega:

1. **Arranque limpio**
   - Desinstala cualquier editable previo (`pip uninstall transcriptor-feria`).
   - Instala desde el repo actual y verifica `pip show transcriptor-feria`.
2. **Backend en solitario**
   - `transcriptor api` debe levantar en `127.0.0.1:4814`.
   - `curl http://127.0.0.1:4814/health` responde `status":"ok"`.
3. **Launcher**
   - `transcriptor launcher` inicia API + frontend.
   - Confirmar que abre navegador en `http://127.0.0.1:4815`.
4. **Frontend**
   - Dashboard sin errores de hidratación.
   - Subir un archivo pequeño y verificar creación de job.
5. **Licencia**
   - Cargar un token válido y comprobar features activas.
   - Simular licencia expirada (token manipulado) y observar mensaje de bloqueo.
6. **Modo offline**
   - Desconecta internet.
   - Ejecuta `/health` y `/jobs`: deben responder usando caché local.
   - Verifica que el resumen cae a modo extractivo si la feature premium falta.
7. **Puerto ocupado**
   - Ocupa `4814` con `python -m http.server 4814`.
   - Intentar arrancar backend: debe fallar con mensaje claro.
8. **Modelos corruptos**
   - Corromper un archivo en `data/models`.
   - Lanzar transcripción: debe registrar el error y mostrar aviso en UI.
9. **Archivos largos**
   - Procesar audio > 60 minutos y comprobar que el progreso y ETA siguen actualizando.
10. **Crash & recuperación**
    - Terminar el proceso `uvicorn` manualmente.
    - Verificar que el launcher lo reinicia y la UI vuelve a conectar.
11. **Exportaciones**
    - Generar resumen y exportar en Markdown, DOCX y JSON.
    - Abrir los archivos y revisar formato básico.
12. **Diagnóstico**
    - Ejecutar `scripts/run_backend_checks.py` y guardar salida.
    - Comprimir `logs/` + `data/jobs/` y confirmar que la UI documenta la ruta.

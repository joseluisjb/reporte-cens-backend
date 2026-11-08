# NexoVolt · Iteración 2 · Para el equipo

## Qué hay en esta carpeta

| Archivo | Para qué |
|---|---|
| `Distribucion_RF_Iteracion2_por_integrante_v2.md` | **Empieza aquí.** El reparto completo: qué hace cada uno, en qué orden y el prompt de cada tarea. |
| `Distribucion_RF_Iteracion2_resumen_RF_y_prompts_v2.md` | Los mismos prompts, ordenados por RF, para buscarlos rápido. |
| `RF_ITERACION2.md` | El texto de los 27 RF corregidos. Es el mismo archivo que está en `docs/iteracion2/` de los dos repos. |

Usen estas versiones (`_v2`). Las anteriores y el `.docx` tienen errores ya corregidos.

## Cómo empezar

1. Lee las secciones 1 a 3 del documento por integrante y luego tu ficha (sección 5).
2. Actualiza `dev` en el repo donde vas a trabajar:

   ```
   git checkout dev
   git pull
   ```

   Ahí ya están `CLAUDE.md` y la carpeta `docs/iteracion2/` (fichas, mockup v3 y Matriz de estados), que son lo que leen los prompts.
3. Abre el mockup `docs/iteracion2/NexoVolt_Mockups_Iteracion2_v3.html` en el navegador, en la pantalla que te toca.
4. Pega en Claude Code el prompt de tu tarea, tal cual.

## Cómo trabajamos con git

- Una rama por tarea, desde `dev`: `feature/RFxx-descripcion`.
- El PR va hacia **`dev`**. GitHub propone `main` por defecto: cámbialo a `dev` antes de crearlo.
- Nadie fusiona a `main`. Johan pasa `dev` a `main` al cerrar la entrega.
- El frontend lo revisa Johan y el backend y el SQL, Jose Luis.
- Antes del PR deben pasar las pruebas y el lint. Nunca hagas `git add .`: agrega tus archivos uno por uno.

## Reglas importantes

- **Los repos son públicos.** Nada de datos reales de CENS, nombres de personas de CENS, correos `@cens.com.co`, contraseñas, `.env` ni wallet.
- El FP-15 trae contraseñas y claves reales: no las copien en ningún prompt.
- Lo que está entre [corchetes] o "por confirmar" depende de CENS o de TransUnion. No lo inventes: hazlo parametrizable y sigue la opción "Mientras tanto" del Anexo A.
- El módulo de Actualización en Línea de TransUnion no se usa para pruebas: escribe en la base real.

## Pendientes antes de arrancar

- **Clara o Angel:** subir a `dev`, en los dos repos, el script `docs/iteracion2/NexoVolt_BD_completa_autonomous.sql`. Lo leen todos los prompts. Sin datos reales ni contraseñas.
- **Jose Luis:** revisar el contrato OpenAPI 0.9 cuando Johan abra el PR. Nadie programa contra el contrato antes de eso.

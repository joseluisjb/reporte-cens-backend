# NexoVolt · backend

API del sistema de reporte de cartera de CENS a TransUnion (Seminario Integrador III).

## Stack y comandos

- Django 5.2 + Django REST Framework, Oracle Autonomous con `oracledb` y SQL explícito (sin ORM para la cartera). Pruebas con pytest y pytest-django.
- `pytest` debe pasar completo antes de abrir un PR.

## Dónde está cada cosa

- Apps: `cartera` (cortes y obligaciones), `extraccion`, `historial`, `parametros` (conceptos y grupos), `usuarios`.
- `config/`: `bitacora.py` (auditoría), `paginacion.py`, `errores.py`, `formatos.py` y `sql/` (scripts 08 y 09).
- Scripts SQL numerados en `<app>/sql/` y `config/sql/`.
- `usuarios/permisos.py`: `EsAdministrador` y `EsAnalistaOAdministrador`. El permiso solo para el Analista (`EsAnalista`) todavía no existe; lo crea la Iteración 2.
- `tests/ayudas.py`: cursor simulado que valida los marcadores. `tests/test_sql_marcadores.py` vigila que no haya `:1`.
- `docs/API.md`: lo que ya funciona. `docs/contrato/openapi.yaml`: copia del contrato; la fuente está en el repo del frontend.
- `docs/iteracion2/`: fichas de los RF de la Iteración 2 (`RF_ITERACION2.md`), mockup v3 y Matriz de cambios de estado.

## Reglas

- SQL con marcadores `%s`, nunca `:1`: el cursor de Django para Oracle falla con `:1`.
- La vista solo maneja HTTP. La lógica va en servicios, con `transaction.atomic` en las escrituras.
- Errores `{"detail": "…"}` o por campo, en español. Identificaciones enmascaradas. Paginación `{total, resultados}` con `?limite` y `?desplazamiento`. Fechas AAAA-MM-DD.
- El esquema SAC es una copia de CENS y es de solo lectura. Sus fechas son números julianos: `TO_DATE(TO_CHAR(n), 'J')`.
- Los scripts SQL son repetibles (`CREATE OR REPLACE` en vistas), traen reversa y una consulta de verificación. En tablas nuevas, `USUARIO_ID` es `NUMBER(19)` sin llave foránea.
- Antes de cerrar una tarea con SQL, pruébala contra Oracle real: los errores `ORA-` no salen con el cursor simulado.
- Lo marcado entre corchetes o "por confirmar" en las fichas depende de CENS o TransUnion: se parametriza y no se inventa.
- Nada real en el repo: sin `.env`, wallet, tokens ni datos de CENS.

## Git

- Rama por tarea desde `dev` actualizado: `feature/RFxx-descripcion`.
- Commit: `feat(módulo): descripción (RFxx)`.
- PR hacia `dev`. El backend y el SQL los revisa Jose Luis.

# NexoVolt API

## Información general

| Campo | Valor |
|---|---|
| URL base | `/api/` |
| Formato | JSON |
| Autenticación | Pendiente de RF25 |
| Roles disponibles | `ANALISTA_CARTERA`, `ADMINISTRADOR` |

## Formato de errores (estándar DRF)

Error simple:

```json
{"detail": "Mensaje de error."}
```

Error de validación:

```json
{"campo": ["Mensaje de error."]}
```

## Endpoints

### Utilidades

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/salud/` | Ninguno | Verifica disponibilidad del servidor |

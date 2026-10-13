# Envío de correo por Google Apps Script

## Cuándo usarlo

Algunos proveedores de hosting gratuitos (por ejemplo, el plan gratuito de Render) bloquean los
puertos SMTP (25, 465 y 587). En esos casos no es posible usar el backend SMTP estándar de Django.
`config.correo_apps_script.AppsScriptEmailBackend` reemplaza ese backend enviando cada mensaje como
una solicitud HTTPS a un script publicado en Google Apps Script, que lo despacha internamente con
`MailApp.sendEmail` desde la cuenta de Gmail asociada al proyecto.

## Límite de destinatarios

**MailApp tiene un límite de 100 destinatarios por día** en cuentas Gmail gratuitas (500 en
Workspace). El backend envía un mensaje separado por cada dirección en `mensaje.to`, por lo que
cada destinatario cuenta una vez. Si se agota el cuota, el script devuelve `{"ok": false}` y el
backend lanza `ErrorCorreoRemoto`.

## Configuración

Ajusta las siguientes variables de entorno (ver `.env.example`):

| Variable | Descripción | Valor por omisión |
|---|---|---|
| `DJANGO_EMAIL_BACKEND` | Ruta Python completa del backend | — (obligatorio) |
| `DJANGO_APPS_SCRIPT_URL` | URL de despliegue de la aplicación web del script | `""` (obligatorio) |
| `DJANGO_APPS_SCRIPT_TOKEN` | Secreto compartido entre Django y el script | `""` (obligatorio) |
| `DJANGO_EMAIL_TIMEOUT` | Segundos de espera por respuesta HTTPS | `20` |

Para activar este backend en producción:

```
DJANGO_EMAIL_BACKEND=config.correo_apps_script.AppsScriptEmailBackend
DJANGO_APPS_SCRIPT_URL=<URL del despliegue>
DJANGO_APPS_SCRIPT_TOKEN=<secreto compartido>
```

## Cómo funciona

1. Django llama a `send_mail(...)`, que delega en `AppsScriptEmailBackend.send_messages`.
2. Por cada dirección en `mensaje.to` se realiza una solicitud POST a la URL del script con el
   asunto, el cuerpo, el nombre del remitente, el destinatario y el token de autenticación.
3. El script verifica el token, llama a `MailApp.sendEmail` y responde `{"ok": true}` o
   `{"ok": false, "error": "<motivo>"}`.
4. Si la respuesta no es `{"ok": true}`, el backend lanza `ErrorCorreoRemoto` (subclase de
   `OSError`). `servicios.crear_usuario` convierte cualquier `OSError` en `EnvioCorreoFallido`,
   lo que provoca un 502 en la API y revierte la creación del usuario.

## Seguridad

- El token se transmite únicamente en el cuerpo JSON de la solicitud HTTPS; nunca se incluye
  en registros de log ni en mensajes de error devueltos al cliente.
- La URL del script tampoco se incluye en respuestas ni en logs.
- Usa un token de alta entropía (mínimo 32 caracteres aleatorios) y rota el token si se filtra.
- El script debe verificar el token antes de procesar cualquier solicitud.

# reporte-cens-backend

## Conectar a la base de datos

1. **Descargar el wallet** desde Oracle Cloud Infrastructure y guardarlo en una carpeta **fuera del repositorio** (por ejemplo `C:\wallets\mi_wallet`). La carpeta `wallet/` está en `.gitignore`; no coloque el wallet dentro del proyecto.

2. **Copiar `.env.example` a `.env`** y completar los valores:

   ```bash
   cp .env.example .env
   ```

   Edite `.env` con el usuario, contraseña, DSN y ruta al wallet.

3. **Verificar la conexión** ejecutando el script de prueba:

   ```bash
   python scripts/probar_oracle.py
   ```

   El script imprimirá el usuario conectado y la cantidad de tablas del esquema cuyo nombre empieza por `NV`.

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

## Scripts RF3-RF8

- `extraccion/sql/07_rf7_edad_mora.sql` crea `DIAS_MORA` (diferencia de fechas calendario, sin considerar horas) y `EDAD_MORA` (código de Tabla 9); sus pruebas utPLSQL están en `extraccion/sql/test_07_rf7_edad_mora.sql`. Ejecutar y probar únicamente en un esquema Oracle de desarrollo con utPLSQL instalado. No crear objetos en la base Oracle de CENS.
- `extraccion/sql/07_rf3_rf4_rf5_saldo_neto.sql` es una consulta de referencia para las tablas ficticias `facturacion` y `pagos`. Aplica pagos solo al mismo crédito y concepto, limita el abono aplicado al valor facturado y marca para revisión los créditos asociados a varios procesos. No es una vista de producción: el esquema indicado no contiene la clave del deudor, por lo que la adaptación debe usar la relación confirmada entre cliente y proceso.
- `docs/sql/postgresql_historial_rf6_rf8.sql` es la propuesta del esquema de historial para la base PostgreSQL propia. Acordar el contrato con el backend antes de conectarlo a los servicios.
- `docs/rendimiento_rf3_rf8.md` contiene el protocolo de medición y el registro; debe completarse con tiempos y planes observados junto con Dilan, usando exclusivamente datos ficticios.

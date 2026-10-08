"""Verifica la conexión a Oracle Autonomous Database con wallet mTLS (modo thin)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

VARIABLES_REQUERIDAS = {
    "ORACLE_USER": "usuario de la base de datos Oracle",
    "ORACLE_PASSWORD": "contraseña del usuario Oracle",
    "ORACLE_DSN": "DSN / nombre del servicio (tnsnames.ora)",
    "ORACLE_WALLET_DIR": "ruta a la carpeta del wallet",
    "ORACLE_WALLET_PASSWORD": "contraseña del wallet",
}

faltantes = [nombre for nombre in VARIABLES_REQUERIDAS if not os.getenv(nombre)]
if faltantes:
    print("Faltan las siguientes variables de entorno:")
    for var in faltantes:
        print(f"  {var}: {VARIABLES_REQUERIDAS[var]}")
    print("\nCopie .env.example a .env y complete los valores.")
    sys.exit(1)

import oracledb  # noqa: E402  (importación tardía intencional)

try:
    conexion = oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN"),
        config_dir=os.getenv("ORACLE_WALLET_DIR"),
        wallet_location=os.getenv("ORACLE_WALLET_DIR"),
        wallet_password=os.getenv("ORACLE_WALLET_PASSWORD"),
    )
except oracledb.DatabaseError as error:
    print(f"Error al conectar: {error}")
    sys.exit(1)

with conexion.cursor() as cursor:
    cursor.execute("SELECT USER FROM DUAL")
    (usuario_actual,) = cursor.fetchone()
    print(f"Conectado como: {usuario_actual}")

    cursor.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name LIKE 'NV%'"
    )
    (cantidad,) = cursor.fetchone()
    print(f"Tablas del esquema que empiezan por NV: {cantidad}")

conexion.close()

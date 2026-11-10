# NexoVolt · Datos de Prueba v2 (Iteración 2)

**Responsable:** Omar Alexis Palencia Claro  
**Rol:** Desarrollador Frontend / Tester  
**Esquemas:** `SAC` y `NEXOVOLT` (Oracle Autonomous Database / Entorno de desarrollo)  
**Dependencias:** Scripts 10 a 12 aplicados previamente.

---

## 1. Propósito

Este paquete de scripts provee un conjunto completo de datos ficticios (clientes `900101` a `900118`) diseñado para desbloquear las pruebas unitarias, de integración y de aceptación funcional del equipo durante la Iteración 2 de NexoVolt.

Cubre exhaustivamente los **18 escenarios de prueba (E1 a E18)** contemplados en la especificación (`RF_ITERACION2.md` y `Distribucion_RF_Iteracion2_por_integrante_v2.md`), incluyendo un corte previo en estado `ENVIADO` (`CORTE_ID = 901`, fecha `2026-09-30`) con sus registros de histórico en `NV_REPORTE_DETALLE` y `NV_OBLIGACION`, permitiendo evaluar transiciones de estado de ciclo de vida, moras, pagos, caducidades, refinanciaciones y reglas del Manual de TransUnion.

---

## 2. Orden de Ejecución

> **ADVERTENCIA:** Ejecutar **únicamente en entornos de desarrollo o pruebas**. Nunca ejecutar en producción.

```text
1. (Prerrequisito) Scripts 10 a 12 aplicados en la base de datos de desarrollo:
   - 10_iter2_columnas_catalogos.sql
   - 11_iter2_tablas_nuevas.sql
   - 12a_rf48_homologacion_estados.sql (o 12_matriz_transiciones.sql)
   - 16_v_mora_obligacion.sql, 17_v_validacion_corte_v2.sql, 18_v_reporte_tu_v2.sql

2. Carga de datos de prueba v2:
   @extraccion/sql/03_datos_prueba_v2.sql

3. Ejecución de pruebas / ciclo mensual:
   - Ejecución de pruebas backend (pytest tests/...)
   - Generación de ciclo de prueba al 31/10/2026 (POST /api/ciclos/) o consultas a vistas.

4. Limpieza del entorno de pruebas:
   @extraccion/sql/03_limpiar_datos_prueba_v2.sql
```

---

## 3. Matriz de Escenarios (E1 a E18) y Resultado Esperado

| Escenario | Cliente ID | Obligación / Proceso | Descripción del Caso Comercial (SAC) | Resultado Esperado en Corte TU | Requerimientos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **E1** | 900101 | 100101 | Crédito vigente con facturas al día (sin vencer al 31/10/2026). | **Estado 01**, Mora: $0, Cuotas mora: 0, **Edad: 00** | RF10, RF11 |
| **E2** | 900102 | 100102 | Crédito vigente con 1 cuota vencida el 08/10/2026 (23 días de atraso). | **Estado 01**, Mora: $70.000, Cuotas mora: 1, **Edad: 00** | RF10, RF11, RF19 |
| **E3** | 900103 | 100103 (`2258-7731`) | Crédito vigente con 2 cuotas vencidas (14/09 y 14/10; 47 días la más antigua). | **Estado 01**, Mora: $140.000, Cuotas mora: 2, **Edad: 01** | RF11, RF17, RF19 |
| **E4** | 900104 | 100104 | Tenía 2 cuotas vencidas e ingresó abono parcial de $70.000 el 20/10/2026 imputado a la más antigua. | Mora y cuotas recalculadas (1 cuota pendiente, 17 días), **Edad: 00** | RF17 |
| **E5** | 900105 | 100105 (`2259-1092`) | Estaba en 01 en corte 901; canceló saldo total ($500.000) el 15/10/2026. | **Estado 02 (Saldada)**, `FECHA_PAGO` = 15/10/2026, `MODO_EXTINCION` = 01, `TIPO_PAGO` = 01 | RF12, RF22 |
| **E6** | 900106 | 100106 (`2250-0987`) | Crédito caducado en SAC (`CONTATRASOS` = 6, tope 4) con mora pendiente ($480.000). | **Estado 03 (Cobro coactivo)** | RF14 |
| **E7** | 900107 | 100107 (`2244-6410`) | Crédito con marca de castigo en `NV_MARCA_CASTIGO` y mora. | **Estado 06 (Castigada)**, mantiene 06 mientras exista mora | RF45 |
| **E8** | 900108 | 100108 (`2241-3302`) | Estaba en 03 en corte 901; realiza pago total de su saldo ($600.000) el 20/10/2026. | **Estado 07 (Cartera Recuperada)**, `FECHA_PAGO` = 20/10/2026 | RF15, RF22 |
| **E9** | 900109 | 100109 (`2248-8819`) | Estaba en 03 en corte 901; paga toda la mora ($200.000) pero conserva saldo ($600.000). | **Vuelve a Estado 01 (Vigente)**, reporta pago de mora (`VALOR_REAL_PAGADO`, fecha) | RF46, RF47 |
| **E10** | 900110 | Orig: 100110<br>Nueva: 100111 | Proceso 100110 refinanciado por nuevo crédito 100111 (`PROCESO_REFINANCIACION`). | Original: **02 Saldada**, modo 16 (Refinanciación). Nueva: **01 Vigente reestructurada** | RF18 |
| **E11** | 900111 | 100111 | Crédito nuevo con `CONTATRASOS` > tope pero sin facturas vencidas (mora = 0). | Entra en **01 (no en 03 por no tener mora)** y con marca `REQUIERE_REVISION = 'S'` | RF10, RF14 |
| **E12** | 900112 | 100112 (`2239-1122`) | Obligación cerrada definitivamente en corte 901; se detecta movimiento/factura posterior. | **No se reporta en archivo TU**, genera alerta `MOVIMIENTO_POSTERIOR` | RF13, RF16 |
| **E13** | 900113 | 100113 | Crédito con estado `B` en SAC (no homologado en catálogo). | Bloqueo por regla `ESTADO_SIN_HOMOLOGAR` | RF48, RF53 |
| **E14** | 900114 | 100114 | Titular sin tipo o número de identificación en `NV_TITULAR`. | Falla validación correctiva `SIN_IDENTIFICACION` | RF53 |
| **E15** | 900115 | -9876543210 | Proceso negativo con número de obligación TU superior a 20 caracteres. | Falla validación correctiva `NUMERO_OBLIGACION_INVALIDO` | RF53 |
| **E16** | 900116 | 100116 / 100117 | Crédito 1 con saldo $9.000 (< $10.000); Crédito 2 con saldo $120.000.000 (> $100M). | Genera advertencias informativas `VALOR_FUERA_DE_RANGO` | RF51, RF53 |
| **E17** | 900117 | 100117 | Crédito con factura vencida hace 800 días (> 730 días de atraso). | Reporta **Edad 14**, y cálculo de años en mora = 2 | RF11, RF49 |
| **E18** | 900118 | 100118 (`2249-1180`) | Obligación con novedad de eliminación ante TransUnion (`NV_ELIMINACION`). | **Excluida del corte**, no cuenta como omitida ni se transmite en el archivo TU | RF50, RF21 |

---

## 4. Consulta SQL de Verificación de Escenarios

La siguiente consulta permite verificar directamente en la base de datos el estado y los campos claves calculados para los clientes de prueba tras correr el cálculo del corte:

```sql
SELECT 
    c.CLIENTE_ID,
    t.TIPO_IDENTIFICACION || ' ' || t.NUMERO_IDENTIFICACION AS IDENTIFICACION,
    cr.NUMERO_PROCESO,
    cr.ESTADO AS ESTADO_SAC,
    cr.DEUDA_ACTUAL_CAP AS SALDO_CAPITAL,
    m.VALOR_MORA,
    m.CUOTAS_MORA,
    m.DIAS_MORA,
    m.EDAD_MORA_TU,
    CASE 
        WHEN c.CLIENTE_ID = 900101 THEN 'E1: 01 Al dia (Mora 0, Edad 00)'
        WHEN c.CLIENTE_ID = 900102 THEN 'E2: 01 Mora 23d (Edad 00)'
        WHEN c.CLIENTE_ID = 900103 THEN 'E3: 01 Mora 47d (Edad 01, 2 cuotas)'
        WHEN c.CLIENTE_ID = 900104 THEN 'E4: Recalculo mora abono (Edad 00)'
        WHEN c.CLIENTE_ID = 900105 THEN 'E5: Cierre 02 Saldada (Pago total)'
        WHEN c.CLIENTE_ID = 900106 THEN 'E6: Caducado pasa a 03 Cobro Coactivo'
        WHEN c.CLIENTE_ID = 900107 THEN 'E7: Castigada 06 (NV_MARCA_CASTIGO)'
        WHEN c.CLIENTE_ID = 900108 THEN 'E8: Cierre 07 Cartera Recuperada (desde 03)'
        WHEN c.CLIENTE_ID = 900109 THEN 'E9: 03 pasa a 01 (Pago mora con saldo)'
        WHEN c.CLIENTE_ID = 900110 THEN 'E10: Refinanciacion (02 modo 16 / nueva 01)'
        WHEN c.CLIENTE_ID = 900111 THEN 'E11: Caducado sin mora -> 01 Revision'
        WHEN c.CLIENTE_ID = 900112 THEN 'E12: Alerta movimiento posterior cerrada'
        WHEN c.CLIENTE_ID = 900113 THEN 'E13: Bloqueo ESTADO_SIN_HOMOLOGAR'
        WHEN c.CLIENTE_ID = 900114 THEN 'E14: Alerta SIN_IDENTIFICACION'
        WHEN c.CLIENTE_ID = 900115 THEN 'E15: Alerta NUMERO_OBLIGACION_INVALIDO'
        WHEN c.CLIENTE_ID = 900116 THEN 'E16: Advertencia VALOR_FUERA_DE_RANGO'
        WHEN c.CLIENTE_ID = 900117 THEN 'E17: Edad 14 (> 730 dias mora)'
        WHEN c.CLIENTE_ID = 900118 THEN 'E18: Excluida por NV_ELIMINACION'
        ELSE 'OTRO'
    END AS ESCENARIO_ESPERADO
FROM SAC.CLIENTES c
LEFT JOIN NEXOVOLT.NV_TITULAR t ON c.CLIENTE_ID = t.CLIENTE_ID
JOIN SAC.CREDITOS cr ON c.CLIENTE_ID = cr.CLIENTE_ID
LEFT JOIN NEXOVOLT.V_MORA_OBLIGACION m ON cr.CLIENTE_ID = m.CLIENTE_ID AND cr.NUMERO_PROCESO = m.NUMERO_PROCESO
WHERE c.CLIENTE_ID BETWEEN 900101 AND 900118
ORDER BY c.CLIENTE_ID, cr.NUMERO_PROCESO;
```

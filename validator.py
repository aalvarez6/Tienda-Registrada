import sqlite3
import struct
import hashlib
from pathlib import Path

# ==============================
# DETECTOR DE TIPO DE ARCHIVO
# ==============================
def detect_file_type(file_path):
    """Detecta si es SQLite, DAT binario o CSV."""
    # SQLite: primeros 16 bytes contienen "SQLite format 3"
    with open(file_path, 'rb') as f:
        header = f.read(16)
        if header.startswith(b'SQLite format 3'):
            return 'sqlite'
        # Detectar .dat con cabecera conocida (ejemplo: KF_DAT)
        if header.startswith(b'KF_DAT') or header.startswith(b'HIOPOS'):
            return 'dat'
    # Intentar como CSV
    try:
        import pandas as pd
        pd.read_csv(file_path, nrows=1)
        return 'csv'
    except:
        return 'unknown'

# ==============================
# VALIDADOR PARA SQLITE (.bak)
# ==============================
EXPECTED_TABLES = ['ventas', 'productos', 'inventario', 'tiendas']  # Ajusta según el POS

def validate_sqlite(file_path):
    errors = []
    warnings = []
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        # 1. Integridad
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        if integrity != 'ok':
            errors.append(f"Integrity check falló: {integrity}")
        # 2. Verificar tablas esperadas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        missing = [t for t in EXPECTED_TABLES if t not in existing_tables]
        if missing:
            errors.append(f"Faltan tablas requeridas: {missing}")
        # 3. Validar columnas críticas en tabla ventas (ejemplo)
        if 'ventas' in existing_tables:
            cursor.execute("PRAGMA table_info(ventas)")
            columns = [col[1] for col in cursor.fetchall()]
            required_cols = ['fecha', 'tienda_id', 'monto', 'producto_id']
            missing_cols = [c for c in required_cols if c not in columns]
            if missing_cols:
                errors.append(f"Tabla 'ventas' no tiene columnas: {missing_cols}")
            # Verificar fechas nulas
            cursor.execute("SELECT COUNT(*) FROM ventas WHERE fecha IS NULL")
            null_fechas = cursor.fetchone()[0]
            if null_fechas > 0:
                warnings.append(f"{null_fechas} registros con fecha NULL en ventas")
        conn.close()
    except Exception as e:
        errors.append(f"Error al leer SQLite: {str(e)}")
    return errors, warnings

# ==============================
# VALIDADOR PARA .DAT BINARIO (ejemplo con registros fijos)
# ==============================
# Supongamos un formato: cabecera de 32 bytes, luego registros de 128 bytes.
# Los primeros 4 bytes son magic "KFDT", luego 4 bytes checksum, etc.
def validate_dat(file_path):
    errors = []
    warnings = []
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        # Validar tamaño mínimo
        if len(data) < 32:
            errors.append("Archivo demasiado pequeño (menos de 32 bytes)")
            return errors, warnings
        # Magic number
        magic = data[0:4]
        if magic != b'KFDT' and magic != b'HDPD':
            errors.append(f"Magic number incorrecto: {magic}")
        # Checksum simple (suma de bytes módulo 256) – ejemplo
        stored_checksum = data[4]  # byte en posición 4
        calc_checksum = sum(data[8:]) % 256  # excluir cabecera
        if stored_checksum != calc_checksum:
            warnings.append(f"Checksum no coincide (almacenado {stored_checksum}, calculado {calc_checksum})")
        # Verificar que el tamaño sea consistente con registros de 128 bytes
        record_size = 128
        header_size = 32
        if (len(data) - header_size) % record_size != 0:
            warnings.append(f"Tamaño de datos no es múltiplo de {record_size} bytes")
    except Exception as e:
        errors.append(f"Error al leer DAT: {str(e)}")
    return errors, warnings

# ==============================
# VALIDADOR CSV (legado)
# ==============================
def validate_csv(file_path):
    errors = []
    warnings = []
    try:
        import pandas as pd
        df = pd.read_csv(file_path)
        expected_cols = ['fecha', 'tienda_id', 'monto_venta', 'producto', 'cantidad']
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            errors.append(f"Faltan columnas: {missing}")
        # Validar fechas
        if 'fecha' in df.columns:
            null_fechas = df['fecha'].isna().sum()
            if null_fechas > 0:
                warnings.append(f"{null_fechas} fechas nulas")
        if 'monto_venta' in df.columns:
            negativos = (df['monto_venta'] < 0).sum()
            if negativos > 0:
                warnings.append(f"{negativos} montos negativos")
    except Exception as e:
        errors.append(f"Error al leer CSV: {str(e)}")
    return errors, warnings

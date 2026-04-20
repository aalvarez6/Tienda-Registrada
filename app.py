import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import tempfile
import struct
from pathlib import Path
from datetime import datetime

# ==============================
# CONFIGURACIÓN DE PÁGINA Y BRANDING
# ==============================
st.set_page_config(page_title="Mesa de Servicio TI - T.R Analytics", layout="wide")

# Logo corporativo (debe estar en assets/logo.png)
logo_path = Path(__file__).parent / "assets" / "Logo.jpeg"
if logo_path.exists():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(str(logo_path), width=250)
else:
    st.warning("Logo no encontrado. Coloque 'logo.png' en la carpeta 'assets'.")

st.title("Central de Backups ")
st.markdown("Validación de backups POS (HIOPOS, KF)")

# ==============================
# BASE DE DATOS SQLITE
# ==============================
DB_PATH = "incidents.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        file_type TEXT,
        timestamp TEXT,
        status TEXT,
        diagnosis TEXT,
        recommendation TEXT,
        hash TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER,
        timestamp TEXT,
        level TEXT,
        message TEXT
    )''')
    conn.commit()
    conn.close()

def save_incident(filename, file_type, status, diagnosis, recommendation, file_hash):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO incidents (filename, file_type, timestamp, status, diagnosis, recommendation, hash)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (filename, file_type, datetime.now().isoformat(), status, diagnosis, recommendation, file_hash))
    incident_id = c.lastrowid
    conn.commit()
    conn.close()
    return incident_id

def save_log(incident_id, level, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO logs (incident_id, timestamp, level, message)
                 VALUES (?, ?, ?, ?)''',
              (incident_id, datetime.now().isoformat(), level, message))
    conn.commit()
    conn.close()

def get_all_incidents():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, filename, file_type, timestamp, status, diagnosis, recommendation FROM incidents ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ==============================
# DETECTOR DE TIPO DE ARCHIVO
# ==============================
def detect_file_type(file_path):
    """Detecta si es SQLite, .dat, .bak"""
    with open(file_path, 'rb') as f:
        header = f.read(16)
        if header.startswith(b'SQLite format 3'):
            return 'sqlite'
        if header.startswith(b'KF_DAT') or header.startswith(b'HIOPOS'):
            return 'dat'
    # Intentar como CSV
    try:
        pd.read_csv(file_path, nrows=1)
        return 'csv'
    except:
        return 'unknown'

# ==============================
# VALIDADOR PARA SQLITE (.bak)
# ==============================
EXPECTED_TABLES = ['ventas', 'productos', 'inventario', 'tiendas']  # Ajusta según tu POS

def validate_sqlite(file_path):
    errors = []
    warnings = []
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        # Integridad
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        if integrity != 'ok':
            errors.append(f"Integrity check falló: {integrity}")
        # Tablas esperadas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        missing = [t for t in EXPECTED_TABLES if t not in existing_tables]
        if missing:
            errors.append(f"Faltan tablas requeridas: {missing}")
        # Validar columnas en 'ventas'
        if 'ventas' in existing_tables:
            cursor.execute("PRAGMA table_info(ventas)")
            columns = [col[1] for col in cursor.fetchall()]
            required_cols = ['fecha', 'tienda_id', 'monto', 'producto_id']
            missing_cols = [c for c in required_cols if c not in columns]
            if missing_cols:
                errors.append(f"Tabla 'ventas' no tiene columnas: {missing_cols}")
            # Fechas nulas
            cursor.execute("SELECT COUNT(*) FROM ventas WHERE fecha IS NULL")
            null_fechas = cursor.fetchone()[0]
            if null_fechas > 0:
                warnings.append(f"{null_fechas} registros con fecha NULL en ventas")
        conn.close()
    except Exception as e:
        errors.append(f"Error al leer SQLite: {str(e)}")
    return errors, warnings

# ==============================
# VALIDADOR PARA .DAT BINARIO (ejemplo)
# ==============================
def validate_dat(file_path):
    errors = []
    warnings = []
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        if len(data) < 32:
            errors.append("Archivo demasiado pequeño (menos de 32 bytes)")
            return errors, warnings
        magic = data[0:4]
        if magic not in (b'KFDT', b'HDPD'):
            errors.append(f"Magic number incorrecto: {magic}")
        # Checksum simple (byte en posición 4)
        stored_checksum = data[4]
        calc_checksum = sum(data[8:]) % 256
        if stored_checksum != calc_checksum:
            warnings.append(f"Checksum no coincide (almacenado {stored_checksum}, calculado {calc_checksum})")
        # Verificar tamaño de registros (suponiendo 128 bytes)
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
        df = pd.read_csv(file_path)
        expected_cols = ['fecha', 'tienda_id', 'monto_venta', 'producto', 'cantidad']
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            errors.append(f"Faltan columnas: {missing}")
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

# ==============================
# PROCESADOR PRINCIPAL (AGENTES)
# ==============================
def procesar_archivo(file_bytes, original_filename):
    # 1. Ingesta
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(original_filename).suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    # 2. Detectar tipo
    file_type = detect_file_type(tmp_path)
    st.info(f"Tipo detectado: {file_type.upper()}")

    # 3. Validar según tipo
    if file_type == 'sqlite':
        errors, warnings = validate_sqlite(tmp_path)
    elif file_type == 'dat':
        errors, warnings = validate_dat(tmp_path)
    elif file_type == 'csv':
        errors, warnings = validate_csv(tmp_path)
    else:
        errors = ["Tipo de archivo no reconocido (no es SQLite, DAT o CSV válido)"]
        warnings = []

    # 4. Generar diagnóstico
    if errors:
        status = "ERROR"
        diagnosis = "Errores críticos:\n" + "\n".join(errors)
        if warnings:
            diagnosis += "\nAdvertencias:\n" + "\n".join(warnings)
        recommendation = "Revise la integridad del backup. Consulte al área TI."
    elif warnings:
        status = "WARNING"
        diagnosis = "Advertencias:\n" + "\n".join(warnings)
        recommendation = "Se recomienda revisar los datos inconsistentes (fechas nulas, checksum, etc.)"
    else:
        status = "OK"
        diagnosis = "El backup es válido y cumple con las reglas de negocio."
        recommendation = "Puede proceder con la restauración o sincronización."

    # 5. Registrar
    incident_id = save_incident(original_filename, file_type, status, diagnosis, recommendation, file_hash)
    save_log(incident_id, "INFO", f"Archivo procesado: {original_filename}")

    # Limpiar
    Path(tmp_path).unlink()

    return {
        "status": status,
        "diagnosis": diagnosis,
        "recommendation": recommendation,
        "incident_id": incident_id,
        "file_type": file_type,
        "errors": errors,
        "warnings": warnings
    }

# ==============================
# INTERFAZ DE USUARIO (STREAMLIT)
# ==============================
init_db()

menu = st.sidebar.selectbox("Menú", ["Cargar Backup", "Ver Incidentes"])

if menu == "Cargar Backup":
    uploaded_file = st.file_uploader(
        "Seleccione archivo de backup (.bak, .dat, .csv)",
        type=["bak", "dat", "csv"]
    )
    if uploaded_file is not None:
        with st.spinner("Procesando con agentes..."):
            result = procesar_archivo(uploaded_file.getvalue(), uploaded_file.name)
        
        st.success(f"✅ Estado: {result['status']}")
        st.subheader("Diagnóstico")
        st.text(result['diagnosis'])
        st.subheader("Recomendación")
        st.info(result['recommendation'])
        if result['errors']:
            with st.expander("Detalle de errores"):
                st.write(result['errors'])
        if result['warnings']:
            with st.expander("Detalle de advertencias"):
                st.write(result['warnings'])
        st.caption(f"ID de incidente: {result['incident_id']} | Tipo: {result['file_type']}")

elif menu == "Ver Incidentes":
    st.header("📋 Historial de incidentes")
    incidents = get_all_incidents()
    if incidents:
        st.dataframe(
            [{"ID": i[0], "Archivo": i[1], "Tipo": i[2], "Fecha": i[3], "Estado": i[4], "Diagnóstico": i[5][:100] + "..." if len(i[5])>100 else i[5]} for i in incidents]
        )
    else:
        st.info("No hay incidentes registrados aún.")

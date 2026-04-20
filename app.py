import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import struct
import zipfile
import tempfile
import os
from pathlib import Path
from datetime import datetime

# ========== CREAR DIRECTORIO ==========
os.makedirs("data", exist_ok=True)

# ========== CONFIGURACIÓN ==========
st.set_page_config(page_title="Mesa de Servicio TI - T.R Analytics", layout="wide")

logo_path = Path(__file__).parent / "assets" / "logo.jpeg"
if logo_path.exists():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image(str(logo_path), width=250)
else:
    st.sidebar.info("Logo no encontrado (assets/logo.png)")

st.title("📡 Central de BackUps")
st.markdown("Validación de backups POS con regla ID local vs ID central")

# ========== BASE DE DATOS ==========
DB_PATH = "data/service_desk.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT, file_type TEXT, timestamp TEXT, status TEXT,
        diagnosis TEXT, recommendation TEXT, max_local_id INTEGER, hash TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id INTEGER,
        timestamp TEXT, level TEXT, message TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS central_reference (
        key TEXT PRIMARY KEY, value INTEGER
    )''')
    c.execute("INSERT OR IGNORE INTO central_reference (key, value) VALUES ('last_central_id', 0)")
    conn.commit()
    conn.close()

def get_last_central_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM central_reference WHERE key = 'last_central_id'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_central_id(new_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE central_reference SET value = ? WHERE key = 'last_central_id'", (new_id,))
    conn.commit()
    conn.close()

def save_incident(filename, file_type, status, diagnosis, recommendation, max_local_id, file_hash):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO incidents (filename, file_type, timestamp, status, diagnosis, recommendation, max_local_id, hash)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (filename, file_type, datetime.now().isoformat(), status, diagnosis, recommendation, max_local_id, file_hash))
    incident_id = c.lastrowid
    conn.commit()
    conn.close()
    return incident_id

def save_log(incident_id, level, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO logs (incident_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
              (incident_id, datetime.now().isoformat(), level, message))
    conn.commit()
    conn.close()

def get_all_incidents():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, filename, file_type, timestamp, status, diagnosis, recommendation FROM incidents ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# ========== FUNCIONES DE DETECCIÓN Y EXTRACCIÓN CONFIGURABLES ==========
def detect_file_type(file_path):
    """Detecta si es SQLite, ZIP, KF.dat o CSV."""
    # SQLite
    try:
        conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
        conn.close()
        return "sqlite"
    except:
        pass
    # ZIP
    if zipfile.is_zipfile(file_path):
        return "zip"
    # KF.dat (binario)
    with open(file_path, 'rb') as f:
        header = f.read(20)
        if header.startswith(b'.dat') or header.startswith(b'.dat'):
            return "kf_dat"
    # Hipos .bak
      with open(file_path, 'rb') as f:
        header = f.read(20)
        if header.startswith(b'.bak') or header.startswith(b'.bak'):
            return "HIOPOs_bak"
    # CSV
    try:
        pd.read_csv(file_path, nrows=1)
        return "csv"
    except:
        return "unknown"

def get_sqlite_tables(file_path):
    """Devuelve lista de tablas en una base SQLite."""
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except:
        return []

def get_columns_from_table(file_path, table_name):
    """Devuelve columnas de una tabla específica."""
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns
    except:
        return []

def extract_max_id_from_sqlite(file_path, table_name, id_column):
    """Extrae el máximo valor de una columna ID en una tabla."""
    try:
        conn = sqlite3.connect(file_path)
        query = f"SELECT MAX({id_column}) FROM {table_name}"
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()[0]
        conn.close()
        return result if result is not None else 0
    except Exception as e:
        raise Exception(f"Error al leer {table_name}.{id_column}: {str(e)}")

def extract_max_id_from_kf_dat(file_path):
    """Extrae ID de archivo binario KF (registros de 64 bytes, id en bytes 0-4)."""
    with open(file_path, 'rb') as f:
        data = f.read()
    HEADER_SIZE = 32
    RECORD_SIZE = 64
    if len(data) < HEADER_SIZE:
        raise Exception("Archivo demasiado pequeño")
    offset = HEADER_SIZE
    ids = []
    while offset + RECORD_SIZE <= len(data):
        record = data[offset:offset+RECORD_SIZE]
        id_local = struct.unpack('<I', record[0:4])[0]
        ids.append(id_local)
        offset += RECORD_SIZE
    if not ids:
        raise Exception("No se encontraron registros")
    return max(ids)

def extract_max_local_id(file_path, file_type, pos_system, custom_table=None, custom_column=None):
    """
    Extrae el máximo ID local según configuración.
    - pos_system: 'hiopos', 'kf', 'binario_kf', 'manual'
    - custom_table, custom_column: para mapeo manual
    """
    errors = []
    warnings = []
    max_id = 0

    try:
        if file_type == "sqlite":
            tables = get_sqlite_tables(file_path)
            if not tables:
                errors.append("La base SQLite no contiene tablas")
                return max_id, errors, warnings

            # Mapeo automático según sistema
            if pos_system == "hiopos":
                # Intenta tabla 'ventas' o 'transacciones'
                candidates = ['ventas', 'transacciones', 'Ventas', 'Transacciones']
                table_found = None
                for t in candidates:
                    if t in tables:
                        table_found = t
                        break
                if not table_found:
                    errors.append(f"No se encontró tabla de ventas. Tablas disponibles: {tables}")
                    return max_id, errors, warnings
                # Buscar columna ID: 'id_local', 'id', 'ID'
                cols = get_columns_from_table(file_path, table_found)
                id_col = None
                for col in ['id_local', 'id', 'ID', 'id_venta']:
                    if col in cols:
                        id_col = col
                        break
                if not id_col:
                    errors.append(f"Columna ID no encontrada en {table_found}. Columnas: {cols}")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, table_found, id_col)

            elif pos_system == "kf":
                # Para KF, normalmente tabla 'Ventas' (con mayúscula)
                table_name = custom_table if custom_table else "Ventas"
                id_column = custom_column if custom_column else "Id"
                if table_name not in tables:
                    errors.append(f"Tabla '{table_name}' no encontrada. Tablas: {tables}")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, table_name, id_column)

            elif pos_system == "manual":
                if not custom_table or not custom_column:
                    errors.append("Para modo manual, debe especificar tabla y columna")
                    return max_id, errors, warnings
                if custom_table not in tables:
                    errors.append(f"Tabla '{custom_table}' no encontrada")
                    return max_id, errors, warnings
                max_id = extract_max_id_from_sqlite(file_path, custom_table, custom_column)

        elif file_type == "kf_dat" or pos_system == "binario_kf":
            max_id = extract_max_id_from_kf_dat(file_path)

        elif file_type == "zip":
            # Buscar primer archivo .db dentro del zip y extraer
            with zipfile.ZipFile(file_path, 'r') as zf:
                db_files = [f for f in zf.namelist() if f.endswith('.db')]
                if not db_files:
                    errors.append("El ZIP no contiene archivo .db")
                    return max_id, errors, warnings
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    tmp.write(zf.read(db_files[0]))
                    tmp_path = tmp.name
                # Recursivamente extraer de ese SQLite (asumimos HIOPOS por defecto)
                sub_max, sub_err, sub_warn = extract_max_local_id(tmp_path, "sqlite", pos_system, custom_table, custom_column)
                max_id = sub_max
                errors.extend(sub_err)
                warnings.extend(sub_warn)
                Path(tmp_path).unlink()

        elif file_type == "csv":
            df = pd.read_csv(file_path)
            id_col = custom_column if custom_column else 'id_local'
            if id_col not in df.columns:
                errors.append(f"CSV sin columna '{id_col}'")
                return max_id, errors, warnings
            max_id = df[id_col].max()

        else:
            errors.append("Tipo de archivo no soportado")

    except Exception as e:
        errors.append(f"Excepción: {str(e)}")

    return max_id, errors, warnings

# ========== PROCESAMIENTO PRINCIPAL ==========
def process_backup(file_bytes, filename, pos_system, custom_table, custom_column):
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    file_type = detect_file_type(tmp_path)
    st.info(f"Tipo detectado: {file_type}")

    # Extraer ID máximo según configuración
    max_local_id, extract_errors, extract_warnings = extract_max_local_id(
        tmp_path, file_type, pos_system, custom_table, custom_column
    )
    central_id = get_last_central_id()

    # Regla de negocio
    status, diagnosis, recommendation = "OK", "", ""
    if extract_errors:
        status = "ERROR"
        diagnosis = "; ".join(extract_errors)
        recommendation = "Revisar formato del archivo o la configuración de extracción."
    else:
        if max_local_id > central_id:
            update_central_id(max_local_id)
            diagnosis = f"ID local ({max_local_id}) > ID central ({central_id}). Base actualizada."
            recommendation = "Sincronización exitosa."
            status = "OK"
        elif max_local_id == central_id:
            status = "WARNING"
            diagnosis = f"ID local = central ({central_id}). Sin nuevos datos."
            recommendation = "No requiere sincronización."
        else:
            status = "ALERTA"
            diagnosis = f"ID local ({max_local_id}) < central ({central_id}). Posible pérdida."
            recommendation = "¡Sincronizar desde central hacia el POS!"

    if extract_warnings:
        diagnosis += "\nAdvertencias: " + "; ".join(extract_warnings)

    incident_id = save_incident(filename, file_type, status, diagnosis, recommendation, max_local_id, file_hash)
    save_log(incident_id, "INFO", f"Procesado {filename}")
    if extract_errors:
        save_log(incident_id, "ERROR", diagnosis)
    if status == "ALERTA":
        save_log(incident_id, "CRITICAL", diagnosis)

    Path(tmp_path).unlink()
    return {
        "status": status,
        "diagnosis": diagnosis,
        "recommendation": recommendation,
        "incident_id": incident_id,
        "max_local_id": max_local_id,
        "file_type": file_type,
        "extract_errors": extract_errors,
        "extract_warnings": extract_warnings
    }

# ========== INTERFAZ STREAMLIT ==========
init_db()

# Sidebar: configuración de extracción
st.sidebar.header("⚙️ Configuración de extracción")
pos_system = st.sidebar.selectbox("Sistema POS", ["hiopos", "kf", "binario_kf", "manual"])
custom_table = ""
custom_column = ""
if pos_system == "manual":
    custom_table = st.sidebar.text_input("Nombre de la tabla", "ventas")
    custom_column = st.sidebar.text_input("Nombre de la columna ID", "id_local")
elif pos_system == "kf":
    custom_table = st.sidebar.text_input("Tabla (default: Ventas)", "Ventas")
    custom_column = st.sidebar.text_input("Columna ID (default: Id)", "Id")

menu = st.sidebar.selectbox("Menú", ["Cargar Backup", "Ver Incidentes"])

if menu == "Cargar Backup":
    uploaded = st.file_uploader("Seleccione archivo (.bak, .dat, .zip, .csv)", type=["bak", "dat", "zip", "csv"])
    if uploaded:
        with st.spinner("Procesando..."):
            result = process_backup(uploaded.getvalue(), uploaded.name, pos_system, custom_table, custom_column)
        st.success(f"Estado: {result['status']}")
        st.subheader("Diagnóstico")
        st.write(result['diagnosis'])
        st.subheader("Recomendación")
        st.info(result['recommendation'])
        st.caption(f"Incidente {result['incident_id']} | Último ID local: {result['max_local_id']} | Tipo: {result['file_type']}")
        if result['extract_errors']:
            with st.expander("Errores de extracción"):
                st.write(result['extract_errors'])
        if result['extract_warnings']:
            with st.expander("Advertencias"):
                st.write(result['extract_warnings'])

elif menu == "Ver Incidentes":
    st.header("Historial")
    df = get_all_incidents()
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("Sin incidentes")

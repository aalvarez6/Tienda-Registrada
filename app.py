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

# ========== CREAR DIRECTORIO DE DATOS ==========
os.makedirs("data", exist_ok=True)

# ========== CONFIGURACIÓN ==========
st.set_page_config(page_title="Mesa de Servicio TI - T.R Analytics", layout="wide")

# Logo (opcional)
logo_path = Path(__file__).parent / "assets" / "logo.jpeg"
if logo_path.exists():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image(str(logo_path), width=250)
else:
    st.sidebar.info("Logo no encontrado (assets/logo.png)")

st.title("📡 Central de BackUps")
st.markdown("Validación de backups POS con regla **ID local vs ID central**")

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

# ========== DETECCIÓN Y EXTRACCIÓN ==========
def detect_file_type(file_path):
    try:
        conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
        conn.close()
        return "sqlite"
    except:
        pass
    if zipfile.is_zipfile(file_path):
        return "zip"
    with open(file_path, 'rb') as f:
        header = f.read(20)
        if header.startswith(b'KF_DAT') or header.startswith(b'KFDATA'):
            return "kf_dat"
    try:
        pd.read_csv(file_path, nrows=1)
        return "csv"
    except:
        return "unknown"

def extract_max_local_id(file_path, file_type):
    errors, warnings = [], []
    max_id = 0
    try:
        if file_type == "sqlite":
            conn = sqlite3.connect(file_path)
            df = pd.read_sql_query("SELECT id_local FROM ventas", conn)
            conn.close()
            if not df.empty:
                max_id = df['id_local'].max()
        elif file_type == "zip":
            with zipfile.ZipFile(file_path, 'r') as zf:
                db_files = [f for f in zf.namelist() if f.endswith('.db')]
                if db_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                        tmp.write(zf.read(db_files[0]))
                        tmp_path = tmp.name
                    conn = sqlite3.connect(tmp_path)
                    df = pd.read_sql_query("SELECT id_local FROM ventas", conn)
                    conn.close()
                    Path(tmp_path).unlink()
                    if not df.empty:
                        max_id = df['id_local'].max()
                else:
                    errors.append("ZIP sin archivo .db")
        elif file_type == "kf_dat":
            with open(file_path, 'rb') as f:
                data = f.read()
            HEADER_SIZE = 32
            RECORD_SIZE = 64
            if len(data) < HEADER_SIZE:
                errors.append("Archivo demasiado pequeño")
            else:
                offset = HEADER_SIZE
                ids = []
                while offset + RECORD_SIZE <= len(data):
                    record = data[offset:offset+RECORD_SIZE]
                    id_local = struct.unpack('<I', record[0:4])[0]
                    ids.append(id_local)
                    offset += RECORD_SIZE
                if ids:
                    max_id = max(ids)
                else:
                    warnings.append("No se encontraron registros")
        elif file_type == "csv":
            df = pd.read_csv(file_path)
            if 'id_local' in df.columns:
                max_id = df['id_local'].max()
            else:
                errors.append("CSV sin columna 'id_local'")
    except Exception as e:
        errors.append(f"Error: {str(e)}")
    return max_id, errors, warnings

# ========== PROCESAMIENTO PRINCIPAL ==========
def process_backup(file_bytes, filename):
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    file_type = detect_file_type(tmp_path)
    max_local_id, extract_errors, extract_warnings = extract_max_local_id(tmp_path, file_type)
    central_id = get_last_central_id()

    status, diagnosis, recommendation = "OK", "", ""
    if extract_errors:
        status = "ERROR"
        diagnosis = "; ".join(extract_errors)
        recommendation = "Revisar formato del archivo."
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
    return {"status": status, "diagnosis": diagnosis, "recommendation": recommendation,
            "incident_id": incident_id, "max_local_id": max_local_id, "file_type": file_type}

# ========== INTERFAZ STREAMLIT ==========
init_db()
menu = st.sidebar.selectbox("Menú", ["Cargar Backup", "Ver Incidentes"])

if menu == "Cargar Backup":
    uploaded = st.file_uploader("Seleccione archivo (.dat, .bak, .zip, .csv)", type=["dat", "bak", "zip", "csv"])
    if uploaded:
        with st.spinner("Procesando..."):
            result = process_backup(uploaded.getvalue(), uploaded.name)
        st.success(f"Estado: {result['status']}")
        st.subheader("Diagnóstico")
        st.write(result['diagnosis'])
        st.subheader("Recomendación")
        st.info(result['recommendation'])
        st.caption(f"Incidente {result['incident_id']} | Último ID local: {result['max_local_id']} | Tipo: {result['file_type']}")

elif menu == "Ver Incidentes":
    st.header("Historial")
    df = get_all_incidents()
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("Sin incidentes")

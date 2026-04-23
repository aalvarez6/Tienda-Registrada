# app.py - Fase 2 con reporte individual y administrador
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from sqlalchemy import create_engine, text
import urllib

# ------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# ------------------------------------------------------------
USUARIOS_VALIDOS = [
    "TRCaptura", "Admin1", "UserLog", "SoporteTI", "Operador1",
    "Analista2", "Gestor3", "CargaDatos", "Supervisor", "Visor"
]
CONTRASENA_COMPARTIDA = "TRC1234"
ADMIN_USER = "Admin1"  # El usuario que puede ver todos los reportes

BACKUP_PATH = "./backups"
LOG_PATH = "./data/logs"
CSV_PATH = "./data/csv"
EXCEL_REPORTE = "reporte_actividad.xlsx"

for path in [BACKUP_PATH, LOG_PATH, CSV_PATH,
             os.path.join(BACKUP_PATH, "bak"),
             os.path.join(BACKUP_PATH, "dat")]:
    os.makedirs(path, exist_ok=True)

LOG_FILE = os.path.join(LOG_PATH, "logs.txt")

# ------------------------------------------------------------
# FUNCIÓN DE CONEXIÓN A BASE DE DATOS (usa secrets de Streamlit)
# ------------------------------------------------------------
def get_db_engine():
    try:
        db = st.secrets["database"]
        if "driver" in db:  # SQL Server
            conn_str = (
                f"DRIVER={db['driver']};"
                f"SERVER={db['server']};"
                f"DATABASE={db['database']};"
                f"UID={db['username']};"
                f"PWD={db['password']}"
            )
            params = urllib.parse.quote_plus(conn_str)
            engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
        else:  # MySQL / MariaDB
            engine = create_engine(
                f"mysql+pymysql://{db['username']}:{db['password']}"
                f"@{db['server']}:{db.get('port',3306)}/{db['database']}"
            )
        return engine
    except Exception as e:
        st.error(f"❌ Error de conexión a la BD de la empresa: {e}")
        return None

# ------------------------------------------------------------
# REGISTRO DE LOGS (interno)
# ------------------------------------------------------------
def registrar_log(usuario, accion, detalle, estado="OK"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = f"[{timestamp}] | USUARIO: {usuario} | ACCIÓN: {accion} | DETALLE: {detalle} | ESTADO: {estado}\n"
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(entrada)

# ------------------------------------------------------------
# VALIDACIÓN Y GUARDADO LOCAL
# ------------------------------------------------------------
def validate_file(file_name, file_bytes):
    if len(file_bytes) == 0:
        return False, "Archivo vacío"
    ext = os.path.splitext(file_name)[1].lower()
    if ext == ".bak":
        return True, "bak"
    elif ext == ".dat":
        return True, "dat"
    return False, "Formato no válido (solo .bak o .dat)"

def guardar_archivo(nombre, datos_bytes, file_type, usuario):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo_nombre = f"{timestamp}_{nombre}"
    target_dir = os.path.join(BACKUP_PATH, file_type)
    os.makedirs(target_dir, exist_ok=True)
    ruta = os.path.join(target_dir, nuevo_nombre)
    with open(ruta, "wb") as f:
        f.write(datos_bytes)
    registrar_log(usuario, "FILE_SAVE", f"Guardado {nuevo_nombre} en {file_type}")
    return ruta

# ------------------------------------------------------------
# PROCESAMIENTO SEGÚN TIPO (ACTUALIZA BD EMPRESA)
# ------------------------------------------------------------
def process_bak(ruta_local, usuario, engine):
    try:
        db_name = st.secrets["database"]["database"]
        sql = f"""
        RESTORE DATABASE [{db_name}]
        FROM DISK = '{ruta_local}'
        WITH REPLACE, RECOVERY;
        """
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        registrar_log(usuario, "SQL_RESTORE", f"Restaurado desde {ruta_local}")
        return True, f"Backup restaurado correctamente en la base {db_name}"
    except Exception as e:
        error_msg = str(e)
        registrar_log(usuario, "SQL_RESTORE", f"Error: {error_msg}", estado="ERROR")
        return False, f"Error al restaurar backup: {error_msg}"

def process_dat(ruta_local, usuario, engine):
    try:
        # Detectar separador del CSV
        with open(ruta_local, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        sep = ',' if ',' in first_line else ';'
        df = pd.read_csv(ruta_local, sep=sep, encoding='utf-8', low_memory=False)
        
        # Nombre de tabla destino - CAMBIAR SEGÚN LA EMPRESA
        TABLA_DAT = "datos_tienda"  # <--- Ajustar por TI
        
        df.to_sql(TABLA_DAT, con=engine, if_exists='append', index=False)
        registrar_log(usuario, "DAT_LOAD", f"Cargadas {len(df)} filas desde {ruta_local} a tabla {TABLA_DAT}")
        return True, f"Se cargaron {len(df)} registros en la tabla {TABLA_DAT}"
    except Exception as e:
        error_msg = str(e)
        registrar_log(usuario, "DAT_LOAD", f"Error: {error_msg}", estado="ERROR")
        return False, f"Error al procesar .dat: {error_msg}"

# ------------------------------------------------------------
# ACTUALIZAR REPORTE EXCEL (historial con usuario)
# ------------------------------------------------------------
def actualizar_reporte_excel(usuario, total_procesados, cant_bak, cant_dat):
    nueva_fila = pd.DataFrame([{
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Total_Subidos": total_procesados,
        "Cantidad_BAK": cant_bak,
        "Cantidad_DAT": cant_dat
    }])
    if os.path.exists(EXCEL_REPORTE):
        df_existente = pd.read_excel(EXCEL_REPORTE, engine='openpyxl')
        df_nuevo = pd.concat([df_existente, nueva_fila], ignore_index=True)
    else:
        df_nuevo = nueva_fila
    df_nuevo.to_excel(EXCEL_REPORTE, index=False, engine='openpyxl')

# ------------------------------------------------------------
# INTERFAZ DE USUARIO (STREAMLIT)
# ------------------------------------------------------------
st.set_page_config(page_title="Gestor Empresarial - Fase 2", layout="wide")

logo_path = "Logo.jpeg"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=200)

st.title("🏢 Sistema Empresarial de Backups (bak / dat)")

# --- Autenticación ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario_activo = None

if not st.session_state.logged_in:
    if os.path.exists(logo_path):
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image(logo_path, width=250)
    st.subheader("🔐 Acceso autorizado")
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contrasena = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")
        if submitted:
            if usuario in USUARIOS_VALIDOS and contrasena == CONTRASENA_COMPARTIDA:
                st.session_state.logged_in = True
                st.session_state.usuario_activo = usuario
                registrar_log(usuario, "LOGIN", "Acceso exitoso")
                st.success(f"✅ Bienvenido, {usuario}.")
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    st.stop()

usuario_actual = st.session_state.usuario_activo
st.sidebar.success(f"Conectado como: **{usuario_actual}**")
if st.sidebar.button("Cerrar sesión"):
    registrar_log(usuario_actual, "LOGOUT", "Cierre de sesión")
    st.session_state.logged_in = False
    st.session_state.usuario_activo = None
    st.rerun()

# --- Verificar conexión a la base de datos de la empresa ---
engine = get_db_engine()
if engine is None:
    st.error("🚨 No se pudo conectar a la base de datos de la empresa. Contacta al área de TI.")
    st.stop()
else:
    st.sidebar.success("✅ Conectado a la base de datos corporativa")

# --- Subida de archivos con procesamiento automático ---
if os.path.exists(logo_path):
    st.image(logo_path, width=150)

st.header("📂 Subir archivos (bak / dat)")
uploaded_files = st.file_uploader(
    "Seleccione uno o varios archivos. Se procesarán automáticamente contra la BD de la empresa.",
    type=["bak", "dat"],
    accept_multiple_files=True
)

# Persistencia de archivos subidos en esta sesión
if "archivos_subidos" not in st.session_state:
    st.session_state.archivos_subidos = {}
if "contadores_sesion" not in st.session_state:
    st.session_state.contadores_sesion = {"bak": 0, "dat": 0, "total": 0}

# Procesar cada nuevo archivo inmediatamente
if uploaded_files:
    nuevos_procesados = False
    for file in uploaded_files:
        key = file.name
        if key not in st.session_state.archivos_subidos:
            st.session_state.archivos_subidos[key] = file.getvalue()
            nuevos_procesados = True
            
            valido, tipo = validate_file(key, file.getvalue())
            if not valido:
                st.error(f"❌ {key}: {tipo} - No se procesa")
                registrar_log(usuario_actual, "UPLOAD_ERROR", f"{key} - {tipo}", "ERROR")
                continue
            
            ruta_local = guardar_archivo(key, file.getvalue(), tipo, usuario_actual)
            
            if tipo == "bak":
                ok, mensaje = process_bak(ruta_local, usuario_actual, engine)
            else:
                ok, mensaje = process_dat(ruta_local, usuario_actual, engine)
            
            if ok:
                st.success(f"✅ {key} procesado correctamente: {mensaje}")
                st.session_state.contadores_sesion[tipo] += 1
                st.session_state.contadores_sesion["total"] += 1
            else:
                st.error(f"❌ {key} falló: {mensaje}")
    
    if nuevos_procesados:
        actualizar_reporte_excel(
            usuario_actual,
            st.session_state.contadores_sesion["total"],
            st.session_state.contadores_sesion["bak"],
            st.session_state.contadores_sesion["dat"]
        )
        st.balloons()
        st.info(f"📊 Lote actual: {st.session_state.contadores_sesion['total']} archivos procesados "
                f"({st.session_state.contadores_sesion['bak']} BAK, {st.session_state.contadores_sesion['dat']} DAT)")

# --- Mostrar archivos ya procesados en esta sesión ---
if st.session_state.archivos_subidos:
    st.subheader("📋 Archivos procesados en esta sesión")
    df_procesados = pd.DataFrame(list(st.session_state.archivos_subidos.keys()), columns=["Nombre del archivo"])
    st.dataframe(df_procesados)
else:
    st.info("Aún no se han subido archivos.")

# --- Reporte de actividad (filtrado por rol) ---
st.header("📊 Reporte de actividad")

if os.path.exists(EXCEL_REPORTE):
    df_reporte_completo = pd.read_excel(EXCEL_REPORTE, engine='openpyxl')
    
    # Filtrar según el usuario actual
    if usuario_actual == ADMIN_USER:
        df_reporte = df_reporte_completo
        st.caption("🔍 Vista de administrador: todos los usuarios")
    else:
        df_reporte = df_reporte_completo[df_reporte_completo["Usuario"] == usuario_actual]
        st.caption(f"👤 Vista para {usuario_actual}: solo sus actividades")
    
    if df_reporte.empty:
        st.info("No hay registros para mostrar.")
    else:
        st.dataframe(df_reporte)
        
        # Botón de descarga CSV ÚNICO (solo el reporte visible)
        csv = df_reporte.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Descargar reporte (CSV)",
            data=csv,
            file_name=f"reporte_{usuario_actual}.csv",
            mime="text/csv"
        )
else:
    st.info("Aún no hay reporte. Sube archivos para generar el historial.")

# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------
USUARIOS_VALIDOS = [
    "Admin", "Captura1", "Captura2", "Captura3", "Captura4",
    "Captura5", "Captura6", "Captura7", "Captura8", "Captura9", "Captura10"
]
CONTRASENA_COMPARTIDA = "TRC1234"

# Rutas de almacenamiento
BACKUP_PATH = "./backups"
LOG_PATH = "./data/logs"
CSV_PATH = "./data/csv"
EXCEL_REPORTE = "reporte_actividad.xlsx"

# Crear directorios
for path in [BACKUP_PATH, LOG_PATH, CSV_PATH,
             os.path.join(BACKUP_PATH, "bak"),
             os.path.join(BACKUP_PATH, "dat")]:
    os.makedirs(path, exist_ok=True)

LOG_FILE = os.path.join(LOG_PATH, "logs.txt")

# ------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------
def registrar_log(usuario, accion, detalle, estado="OK"):
    """Escribe en el archivo de log (solo para trazabilidad interna)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = f"[{timestamp}] | USUARIO: {usuario} | ACCIÓN: {accion} | DETALLE: {detalle} | ESTADO: {estado}\n"
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(entrada)

def validate_file(file_name, file_bytes):
    """Valida extensión y que no esté vacío"""
    if len(file_bytes) == 0:
        return False, "Archivo vacío"
    ext = os.path.splitext(file_name)[1].lower()
    if ext == ".bak":
        return True, "bak"
    elif ext == ".dat":
        return True, "dat"
    return False, "Formato no válido (solo .bak o .dat)"

def guardar_archivo(nombre, datos_bytes, file_type, usuario):
    """Guarda el archivo en la subcarpeta correspondiente (bak/dat) con timestamp (sin ID tienda)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo_nombre = f"{timestamp}_{nombre}"
    target_dir = os.path.join(BACKUP_PATH, file_type)
    os.makedirs(target_dir, exist_ok=True)
    ruta = os.path.join(target_dir, nuevo_nombre)
    with open(ruta, "wb") as f:
        f.write(datos_bytes)
    registrar_log(usuario, "FILE_SAVE", f"Guardado {nuevo_nombre} en {file_type}")
    return ruta

def process_bak(ruta, usuario):
    """Simulación de procesamiento de backup SQL"""
    st.info(f"🔧 Procesando BACKUP SQL - Archivo: {ruta}")
    registrar_log(usuario, "SQL_RESTORE", f"Archivo: {ruta}")

def process_dat(ruta, usuario):
    """Simulación de transformación de DAT a CSV"""
    st.info(f"🐍 Transformando DAT a CSV - Archivo: {ruta}")
    registrar_log(usuario, "DAT_TRANSFORM", f"Archivo: {ruta}")

def actualizar_reporte_excel(usuario, total_procesados, cant_bak, cant_dat):
    """Agrega una fila al reporte Excel (sin columna Tienda)"""
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

def mostrar_logo_black(ancho=250):
    """Muestra el logo con filtro para hacerlo completamente negro"""
    logo_path = "LogoBlack.jpeg"
    if os.path.exists(logo_path):
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/jpeg;base64,{image_to_base64(logo_path)}" width="{ancho}" style="filter: grayscale(100%) brightness(0);">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.warning("LogoBlack.jpeg no encontrado. Añade el archivo a la raíz del proyecto.")

def image_to_base64(path):
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ------------------------------------------------------------
# CONFIGURACIÓN GLOBAL DE ESTILOS (Courier y centrado)
# ------------------------------------------------------------
st.set_page_config(page_title="Gestor de Backups", layout="wide")

st.markdown("""
<style>
    /* Tipografía Courier para toda la app */
    html, body, [class*="css"] {
        font-family: 'Courier New', Courier, monospace;
    }
    /* Centrar contenido de la página de login */
    .login-container {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 70vh;
    }
    .login-card {
        width: 100%;
        max-width: 350px;
        margin: 0 auto;
    }
    /* Hacer que los input ocupen el 100% del contenedor */
    .stTextInput > div {
        width: 100%;
    }
    input {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# INTERFAZ STREAMLIT
# ------------------------------------------------------------

# --- Autenticación ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario_activo = None

if not st.session_state.logged_in:
    # Página de login centrada
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        # Logo centrado y en negro (filtro aplicado)
        mostrar_logo_black(ancho=250)
        st.subheader("🔐 Acceso restringido")
        with st.form("login_form"):
            # Campos con el mismo ancho que el logo (controlado por CSS y contenedor)
            usuario = st.text_input("Usuario", key="login_user")
            contrasena = st.text_input("Contraseña", type="password", key="login_pass")
            submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)
            if submitted:
                if usuario in USUARIOS_VALIDOS and contrasena == CONTRASENA_COMPARTIDA:
                    st.session_state.logged_in = True
                    st.session_state.usuario_activo = usuario
                    registrar_log(usuario, "LOGIN", "Acceso exitoso")
                    st.success(f"✅ Bienvenido, {usuario}.")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- Sesión iniciada ---
usuario_actual = st.session_state.usuario_activo
st.sidebar.success(f"Conectado como: **{usuario_actual}**")
if st.sidebar.button("Cerrar sesión"):
    registrar_log(usuario_actual, "LOGOUT", "Cierre de sesión")
    st.session_state.logged_in = False
    st.session_state.usuario_activo = None
    st.rerun()

# --- Mostrar logo (ahora centrado y en negro) en el área principal ---
mostrar_logo_black(ancho=150)

st.title("📦 Central de Backups")

# --- Subida de archivos ---
st.header("📤 Subir archivos")
uploaded_files = st.file_uploader(
    "Seleccione uno o varios archivos (.bak / .dat)",
    type=["bak", "dat"],
    accept_multiple_files=True
)

# Guardar en session_state para persistencia
if "archivos_subidos" not in st.session_state:
    st.session_state.archivos_subidos = {}

if uploaded_files:
    for file in uploaded_files:
        key = file.name
        if key not in st.session_state.archivos_subidos:
            st.session_state.archivos_subidos[key] = file.getvalue()
    st.success(f"{len(uploaded_files)} archivo(s) cargado(s).")

# Mostrar resumen de archivos subidos
if st.session_state.archivos_subidos:
    st.subheader("📋 Archivos en espera")
    resumen = {"bak": 0, "dat": 0, "error": 0}
    for nombre, datos in st.session_state.archivos_subidos.items():
        valido, tipo = validate_file(nombre, datos)
        if valido:
            resumen[tipo] += 1
        else:
            resumen["error"] += 1
    col1, col2, col3 = st.columns(3)
    col1.metric("Archivos .bak", resumen["bak"])
    col2.metric("Archivos .dat", resumen["dat"])
    col3.metric("No soportados", resumen["error"])
else:
    st.info("No hay archivos cargados. Use el botón de arriba para subir.")

# --- Selección de archivos a procesar ---
if st.session_state.archivos_subidos:
    st.subheader("✔️ Seleccione los archivos a procesar")
    seleccionados = {}
    for nombre in st.session_state.archivos_subidos.keys():
        seleccionados[nombre] = st.checkbox(nombre, value=True, key=f"cb_{nombre}")

    if st.button("🚀 Procesar archivos seleccionados"):
        archivos_a_procesar = [nom for nom, sel in seleccionados.items() if sel]
        if not archivos_a_procesar:
            st.warning("No seleccionó ningún archivo.")
        else:
            with st.spinner("Procesando..."):
                total_procesados = 0
                contadores = {"bak": 0, "dat": 0}
                for nombre in archivos_a_procesar:
                    datos = st.session_state.archivos_subidos[nombre]
                    valido, tipo = validate_file(nombre, datos)
                    if not valido:
                        st.error(f"❌ {nombre}: {tipo} - No se procesará.")
                        continue

                    # Guardar físicamente (sin ID tienda)
                    ruta = guardar_archivo(nombre, datos, tipo, usuario_actual)

                    # Procesar según tipo
                    if tipo == "bak":
                        process_bak(ruta, usuario_actual)
                        contadores["bak"] += 1
                    elif tipo == "dat":
                        process_dat(ruta, usuario_actual)
                        contadores["dat"] += 1

                    total_procesados += 1
                    st.success(f"✅ {nombre} procesado correctamente.")

                # Actualizar reporte Excel
                actualizar_reporte_excel(usuario_actual, total_procesados, contadores["bak"], contadores["dat"])
                st.balloons()
                st.success(f"🎉 Lote finalizado: {total_procesados} archivos procesados.")

                # Eliminar los archivos procesados de session_state
                for nom in archivos_a_procesar:
                    if nom in st.session_state.archivos_subidos:
                        del st.session_state.archivos_subidos[nom]
                st.rerun()

# --- Reporte de actividad ---
st.header("📊 Reporte de actividad")

if os.path.exists(EXCEL_REPORTE):
    df_reporte = pd.read_excel(EXCEL_REPORTE, engine='openpyxl')
    st.dataframe(df_reporte)

    col1, col2 = st.columns(2)
    with col1:
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            df_reporte.to_excel(writer, index=False)
        st.download_button(
            label="📥 Descargar reporte Excel",
            data=output_excel.getvalue(),
            file_name="reporte_actividad.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col2:
        csv = df_reporte.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Descargar reporte CSV",
            data=csv,
            file_name="reporte_actividad.csv",
            mime="text/csv"
        )
else:
    st.info("Aún no se ha generado ningún reporte. Procese archivos para crearlo.")

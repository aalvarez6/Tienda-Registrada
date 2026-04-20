import streamlit as st
import hashlib
import tempfile
from pathlib import Path
from db import init_db, save_incident, save_log, get_all_incidents
from validators import detect_file_type, validate_sqlite, validate_dat, validate_csv

# Configuración inicial
st.set_page_config(page_title="Mesa de Servicio TI - T.R Analytics", layout="wide")

# Logo corporativo
logo_path = Path(__file__).parent / "assets" / "logo.png"
if logo_path.exists():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(str(logo_path), width=250)
else:
    st.warning("Logo no encontrado. Coloque 'logo.png' en la carpeta 'assets'.")

st.title("📡 Mesa de Servicio Digital Automatizada")
st.markdown("Validación de backups POS (HIOPOS, KF)")

# Inicializar base de datos
init_db()

# Funciones de procesamiento (agentes)
def procesar_archivo(file_bytes, original_filename):
    # 1. INGESTA
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(original_filename).suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    # 2. DETECTOR DE TIPO
    file_type = detect_file_type(tmp_path)
    st.info(f"Tipo detectado: {file_type.upper()}")

    # 3. VALIDACIÓN SEGÚN TIPO
    if file_type == 'sqlite':
        errors, warnings = validate_sqlite(tmp_path)
    elif file_type == 'dat':
        errors, warnings = validate_dat(tmp_path)
    elif file_type == 'csv':
        errors, warnings = validate_csv(tmp_path)
    else:
        errors = ["Tipo de archivo no reconocido (no es SQLite, DAT o CSV válido)"]
        warnings = []

    # 4. GENERADOR DE DIAGNÓSTICO
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

    # 5. REGISTRADOR
    incident_id = save_incident(original_filename, file_type, status, diagnosis, recommendation, file_hash)
    save_log(incident_id, "INFO", f"Archivo procesado: {original_filename}")

    # Limpiar archivo temporal
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

# Interfaz de usuario
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
            [{"ID": i[0], "Archivo": i[1], "Tipo": i[2], "Fecha": i[3], "Estado": i[4], "Diagnóstico": i[5][:100] + "..."} for i in incidents]
        )
    else:
        st.info("No hay incidentes registrados aún.")

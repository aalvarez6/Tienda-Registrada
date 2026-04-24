import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import hashlib

# Intentar importar reportlab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_DISPONIBLE = True
except ImportError:
    REPORTLAB_DISPONIBLE = False

# ============================================================
# CONFIGURACIÓN CENTRALIZADA
# ============================================================

@dataclass
class AppConfig:
    usuarios_validos: list = field(default_factory=lambda: [
        "Admin", "Captura1", "Captura2", "Captura3", "Captura4",
        "Captura5", "Captura6", "Captura7", "Captura8", "Captura9", "Captura10"
    ])
    contrasena_hash: str = field(default_factory=lambda: hashlib.sha256("TRC1234".encode()).hexdigest())
    backup_path: Path = Path("./backups")
    log_path: Path = Path("./data/logs")
    csv_path: Path = Path("./data/csv")
    excel_reporte: Path = Path("./data/reporte_actividad.xlsx")
    tipos_validos: tuple = (".bak", ".dat", ".zip", ".rar")
    logo_login: str = "LogoBlue.jpeg"   # Solo se usa en la pantalla de login

CONFIG = AppConfig()

# ============================================================
# INICIALIZACIÓN DE DIRECTORIOS
# ============================================================

def init_directories():
    for d in [CONFIG.backup_path / "bak", CONFIG.backup_path / "dat",
              CONFIG.backup_path / "compressed", CONFIG.log_path,
              CONFIG.csv_path, CONFIG.excel_reporte.parent]:
        d.mkdir(parents=True, exist_ok=True)

init_directories()
LOG_FILE = CONFIG.log_path / "logs.txt"

# ============================================================
# FUNCIONES DE NEGOCIO
# ============================================================

def registrar_log(usuario: str, accion: str, detalle: str, estado: str = "OK"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = f"[{timestamp}] | {usuario:12} | {accion:20} | {estado:6} | {detalle}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entrada)

def verificar_credenciales(usuario: str, contrasena: str) -> bool:
    return usuario in CONFIG.usuarios_validos and hashlib.sha256(contrasena.encode()).hexdigest() == CONFIG.contrasena_hash

def validate_file(file_name: str, file_bytes: bytes) -> tuple[bool, str]:
    if not file_bytes:
        return False, "Archivo vacío"
    ext = Path(file_name).suffix.lower()
    return (True, ext.lstrip(".")) if ext in CONFIG.tipos_validos else (False, f"Formato no soportado: {ext or 'sin extensión'}")

def guardar_archivo(nombre: str, datos_bytes: bytes, file_type: str, usuario: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo_nombre = f"{ts}_{nombre}"
    target_dir = CONFIG.backup_path / ("compressed" if file_type in ["zip", "rar"] else file_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    ruta = target_dir / nuevo_nombre
    ruta.write_bytes(datos_bytes)
    registrar_log(usuario, "GUARDAR_ARCHIVO", f"{nuevo_nombre} → /{target_dir.name}")
    return ruta

def process_bak(ruta: Path, usuario: str) -> dict:
    registrar_log(usuario, "RESTAURAR_SQL", str(ruta))
    return {"tipo": "BAK", "estado": "OK", "ruta": str(ruta)}

def process_dat(ruta: Path, usuario: str) -> dict:
    registrar_log(usuario, "TRANSFORMAR_DAT", str(ruta))
    return {"tipo": "DAT", "estado": "OK", "ruta": str(ruta)}

def process_compressed(ruta: Path, usuario: str, file_type: str) -> dict:
    registrar_log(usuario, "GUARDAR_COMPRIMIDO", f"{file_type.upper()} guardado: {ruta.name}")
    return {"tipo": file_type.upper(), "estado": "OK", "ruta": str(ruta)}

def actualizar_reporte_excel(usuario: str, total: int, cant_bak: int, cant_dat: int):
    nueva_fila = pd.DataFrame([{
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Total_Subidos": total,
        "Cantidad_BAK": cant_bak,
        "Cantidad_DAT": cant_dat,
    }])
    df_existente = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl") if CONFIG.excel_reporte.exists() else None
    df_nuevo = pd.concat([df_existente, nueva_fila], ignore_index=True) if df_existente is not None else nueva_fila
    df_nuevo.to_excel(CONFIG.excel_reporte, index=False, engine="openpyxl")

def leer_reporte(usuario: str) -> Optional[pd.DataFrame]:
    if not CONFIG.excel_reporte.exists():
        return None
    df = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
    return df if usuario == "Admin" else df[df["Usuario"] == usuario]

def exportar_pdf(df: pd.DataFrame, titulo: str) -> Optional[bytes]:
    if not REPORTLAB_DISPONIBLE:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = [Paragraph(titulo, ParagraphStyle('TitleStyle', parent=getSampleStyleSheet()['Heading1'], fontSize=14, alignment=1, spaceAfter=12)), Spacer(1, 12)]
    table = Table([df.columns.tolist()] + df.values.tolist())
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                               ('ALIGN',(0,0),(-1,-1),'CENTER'), ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                               ('FONTSIZE',(0,0),(-1,0),10), ('BOTTOMPADDING',(0,0),(-1,0),8),
                               ('BACKGROUND',(0,1),(-1,-1),colors.beige), ('GRID',(0,0),(-1,-1),1,colors.black),
                               ('FONTSIZE',(0,1),(-1,-1),8)]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()

# ============================================================
# CSS CORREGIDO (elimina espacios en login y mejora tablas)
# ============================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Avenir+Light&display=swap');

:root {
    --bg-primary: #0d0f12; --bg-secondary: #141720; --bg-card: #1a1e28;
    --border: #2a3040; --border-light: #3a4558; --accent: #0066FF;
    --accent-light: #2389FF; --accent-glow: rgba(0,102,255,0.25);
    --success: #10b981; --error: #ef4444; --text-primary: #e8eaf0;
    --text-secondary: #8b95a8; --font-sans: 'Avenir Light', 'Avenir', sans-serif;
    --font-mono: 'Courier New', monospace; --radius: 6px;
}

html, body, .stApp { font-family: var(--font-sans) !important; background-color: var(--bg-primary) !important; color: var(--text-primary) !important; font-size: 14pt; }
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding: 1rem 2rem 1rem 2rem !important; max-width: 1200px !important; }

/* --- TOPBAR --- */
.topbar { display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 1rem; margin-bottom: 1.5rem; }
.topbar-brand { font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); }
.topbar-status { display: flex; align-items: center; gap: 0.5rem; font-family: var(--font-mono); font-size: 0.65rem; color: var(--text-secondary); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--success); box-shadow: 0 0 6px var(--success); animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

/* --- SECCIONES --- */
.section-header { border-left: 2px solid var(--accent); padding-left: 0.75rem; margin: 1.5rem 0 1rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--text-secondary); font-size: 0.85rem; }

/* --- MÉTRICAS HORIZONTALES --- */
.metric-grid { display: flex; flex-wrap: wrap; gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; margin-bottom: 1.5rem; }
.metric-card { flex: 1; background: var(--bg-card); padding: 1rem 1.2rem; transition: background 0.2s; }
.metric-card:hover { background: #1f2535; }
.metric-label { font-size: 0.6rem; letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-secondary); }
.metric-value { font-size: 1.8rem; font-weight: 600; color: var(--accent); line-height: 1; }
.metric-value.green { color: var(--success); }
.metric-value.red { color: var(--error); }

/* --- TABLA DE ARCHIVOS (CORREGIDA) --- */
.file-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-bottom: 1.5rem; }
.file-table thead tr { border-bottom: 1px solid var(--border); }
.file-table th { text-align: left; font-size: 0.6rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-secondary); padding: 0.5rem 0.8rem; font-weight: 500; }
.file-table td { padding: 0.6rem 0.8rem; border-bottom: 1px solid var(--border); color: var(--text-primary); }
.file-table tr:hover td { background: var(--bg-card); }
.badge { display: inline-block; font-size: 0.55rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.2rem 0.5rem; border-radius: 2px; }
.badge-bak { background: rgba(59,130,246,0.12); color: #3b82f6; border: 1px solid #3b82f6; }
.badge-dat { background: rgba(0,102,255,0.15); color: var(--accent-light); border: 1px solid var(--accent); }
.badge-zip, .badge-rar { background: rgba(16,185,129,0.12); color: var(--success); border: 1px solid var(--success); }
.badge-error { background: rgba(239,68,68,0.12); color: var(--error); border: 1px solid var(--error); }

/* --- LOGIN CORREGIDO (sin espacio entre logo y título) --- */
.login-wrapper { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 80vh; }
.login-box { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 2rem; width: 100%; max-width: 420px; margin-top: 0.5rem; }
.login-title { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); text-align: center; margin-bottom: 1.5rem; }
.login-divider { height: 1px; background: var(--border); margin: 1.2rem 0; }

/* --- INPUTS Y BOTONES --- */
.stTextInput > div > div > input, .stTextInput > div > div > input[type="password"] {
    background: var(--bg-primary) !important; border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important; color: var(--text-primary) !important;
    font-family: var(--font-mono) !important; font-size: 0.85rem !important; padding: 0.5rem 0.8rem !important;
}
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 2px var(--accent-glow) !important; }
.stTextInput label { font-size: 0.6rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; color: var(--text-secondary) !important; }

.stButton > button, .stButton > button[kind="secondary"] {
    background: var(--accent) !important; color: #fff !important; border: none !important;
    border-radius: var(--radius) !important; font-weight: 600 !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important; font-size: 0.7rem !important; padding: 0.5rem 1.2rem !important;
}
.stButton > button:hover, .stButton > button[kind="secondary"]:hover { background: var(--accent-light) !important; box-shadow: 0 0 20px var(--accent-glow) !important; }

/* Botones de descarga: PDF rojo, CSV verde */
.stDownloadButton > button { background: transparent !important; border: 2px solid !important; font-weight: 600 !important; }
.stDownloadButton:first-child > button { border-color: #dc2626 !important; color: #dc2626 !important; }
.stDownloadButton:first-child > button:hover { background: rgba(220,38,38,0.1) !important; }
.stDownloadButton:last-child > button { border-color: #10b981 !important; color: #10b981 !important; }
.stDownloadButton:last-child > button:hover { background: rgba(16,185,129,0.1) !important; }

.stFileUploader > div { background: var(--bg-card) !important; border: 1px dashed var(--border-light) !important; border-radius: var(--radius) !important; }
.stFileUploader > div:hover { border-color: var(--accent) !important; }
.stFileUploader label { font-size: 0.65rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; color: var(--text-secondary) !important; }

.stCheckbox > label { font-size: 0.78rem !important; }
.stDataFrame { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; overflow-x: auto !important; }
.stDataFrame th { background: var(--bg-secondary) !important; font-size: 0.6rem !important; text-transform: uppercase !important; }
.stDataFrame td { font-size: 0.75rem !important; background: var(--bg-card) !important; }

.sidebar .css-1d391kg, [data-testid="stSidebar"] { background: var(--bg-secondary) !important; border-right: 1px solid var(--border) !important; }
</style>
"""

# ============================================================
# COMPONENTES UI
# ============================================================

def render_section_header(texto: str):
    st.markdown(f'<div class="section-header">{texto}</div>', unsafe_allow_html=True)

def render_metric_grid(metricas: list):
    cards = "".join(f'<div class="metric-card"><div class="metric-label">{m["label"]}</div><div class="metric-value {m.get("color","")}">{m["value"]}</div></div>' for m in metricas)
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)

def render_file_table(archivos: dict):
    if not archivos:
        return
    rows = []
    for nombre, datos in archivos.items():
        valido, tipo = validate_file(nombre, datos)
        badge_class = f"badge-{tipo}" if valido else "badge-error"
        tipo_texto = tipo.upper() if valido else "ERR"
        size_kb = round(len(datos) / 1024, 1)
        rows.append(f"<tr><td>{nombre}</td><td><span class='badge {badge_class}'>{tipo_texto}</span></td><td>{size_kb} KB</td></tr>")
    html = f'<table class="file-table"><thead><tr><th>Nombre</th><th>Tipo</th><th>Tamaño</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)

def render_topbar(usuario: str):
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-brand">▶ CENTRAL DE BACKUPS  /  SISTEMA TRC</div>
        <div class="topbar-status"><div class="status-dot"></div>{usuario.upper()} &nbsp;·&nbsp; {datetime.now().strftime("%Y-%m-%d  %H:%M")}</div>
    </div>""", unsafe_allow_html=True)

# ============================================================
# INICIALIZACIÓN DE SESIÓN
# ============================================================

def init_session():
    defaults = {"logged_in": False, "usuario_activo": None, "archivos_subidos": {}, "resultados_proceso": []}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ============================================================
# PÁGINAS
# ============================================================

def pagina_login():
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists(CONFIG.logo_login):
            st.image(CONFIG.logo_login, use_column_width=True)
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">ACCESO RESTRINGIDO</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                if not usuario or not contrasena:
                    st.error("Complete todos los campos.")
                elif verificar_credenciales(usuario, contrasena):
                    st.session_state.logged_in = True
                    st.session_state.usuario_activo = usuario
                    registrar_log(usuario, "LOGIN", "Acceso exitoso")
                    st.rerun()
                else:
                    registrar_log(usuario, "FALLO_LOGIN", "Credenciales incorrectas", "ERROR")
                    st.error("Credenciales no válidas.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def pagina_principal():
    usuario = st.session_state.usuario_activo

    # Sidebar
    with st.sidebar:
        st.markdown(f'<div style="font-family:var(--font-mono); font-size:0.8rem; letter-spacing:0.12em; text-transform:uppercase; color:#8b95a8;">Sesión activa</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:var(--accent); font-weight:600; margin-bottom:1rem;">{usuario}</div>', unsafe_allow_html=True)
        if st.button("CERRAR SESIÓN", type="secondary", use_container_width=True):
            registrar_log(usuario, "LOGOUT", "Cierre manual")
            st.session_state.logged_in = False
            st.session_state.usuario_activo = None
            st.session_state.archivos_subidos = {}
            st.rerun()

        st.markdown("---")
        arch = st.session_state.archivos_subidos
        n_bak = n_dat = n_zip = n_rar = 0
        for fn, data in arch.items():
            val, typ = validate_file(fn, data)
            if val:
                if typ == "bak": n_bak += 1
                elif typ == "dat": n_dat += 1
                elif typ == "zip": n_zip += 1
                elif typ == "rar": n_rar += 1
        st.markdown(f'<div style="font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; color:#8b95a8;">Cola de archivos</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex; flex-direction:column; gap:0.3rem; font-size:0.85rem;">
            <div style="display:flex; justify-content:space-between;"><span style="color:#3b82f6;">BAK</span><span>{n_bak}</span></div>
            <div style="display:flex; justify-content:space-between;"><span style="color:var(--accent)">DAT</span><span>{n_dat}</span></div>
            <div style="display:flex; justify-content:space-between;"><span style="color:#10b981">ZIP/RAR</span><span>{n_zip + n_rar}</span></div>
            <div style="display:flex; justify-content:space-between; border-top:1px solid #2a3040; padding-top:0.4rem; margin-top:0.2rem;"><span style="color:#8b95a8">TOTAL</span><span>{len(arch)}</span></div>
        </div>
        """, unsafe_allow_html=True)

    render_topbar(usuario)

    # Botón extra de cerrar sesión
    if st.button("🚪 CERRAR SESIÓN", type="secondary"):
        registrar_log(usuario, "LOGOUT", "Cierre desde botón principal")
        st.session_state.logged_in = False
        st.session_state.usuario_activo = None
        st.session_state.archivos_subidos = {}
        st.rerun()

    # Subida de archivos
    render_section_header("SUBIR ARCHIVOS")
    uploaded_files = st.file_uploader("Arrastre o seleccione archivos (.bak / .dat / .zip / .rar)",
                                      type=["bak","dat","zip","rar"], accept_multiple_files=True)
    if uploaded_files:
        nuevos = 0
        for file in uploaded_files:
            if file.name not in st.session_state.archivos_subidos:
                st.session_state.archivos_subidos[file.name] = file.getvalue()
                nuevos += 1
        if nuevos:
            st.success(f"✓ {nuevos} archivo(s) agregado(s) a la cola.")
            st.rerun()

    arch = st.session_state.archivos_subidos
    if arch:
        render_section_header("COLA DE PROCESO")
        n_bak = sum(1 for n,d in arch.items() if validate_file(n,d)[1]=="bak")
        n_dat = sum(1 for n,d in arch.items() if validate_file(n,d)[1]=="dat")
        n_comp = sum(1 for n,d in arch.items() if validate_file(n,d)[1] in ["zip","rar"])
        n_err = sum(1 for n,d in arch.items() if not validate_file(n,d)[0])
        total_kb = round(sum(len(d) for d in arch.values()) / 1024, 1)
        render_metric_grid([
            {"label": "Total Archivos", "value": len(arch)},
            {"label": "BAK (SQL)", "value": n_bak},
            {"label": "DAT", "value": n_dat},
            {"label": "ZIP / RAR", "value": n_comp},
            {"label": "No soportados", "value": n_err, "color": "red" if n_err else ""},
            {"label": "Tamaño total", "value": f"{total_kb} KB"},
        ])
        render_file_table(arch)

        render_section_header("SELECCIÓN DE ARCHIVOS")
        col_sel, col_clear = st.columns([4,1])
        with col_clear:
            if st.button("LIMPIAR COLA", type="secondary"):
                st.session_state.archivos_subidos = {}
                st.rerun()

        seleccionados = {}
        for nombre in arch:
            valido, tipo = validate_file(nombre, arch[nombre])
            seleccionados[nombre] = st.checkbox(nombre, value=valido, key=f"cb_{nombre}", disabled=not valido)
            if not valido:
                st.caption(f"  ↳ ⚠ {tipo}")
        n_sel = sum(seleccionados.values())
        st.markdown(f'<div style="font-size:0.8rem; color:#8b95a8; margin:0.5rem 0">{n_sel} de {len(arch)} archivo(s) seleccionado(s)</div>', unsafe_allow_html=True)

        if st.button(f"▶  PROCESAR {n_sel} ARCHIVO(S)", use_container_width=True):
            archivos_a_procesar = [n for n, s in seleccionados.items() if s]
            if not archivos_a_procesar:
                st.warning("Seleccione al menos un archivo.")
            else:
                resultados = []
                progress_bar = st.progress(0)
                total = len(archivos_a_procesar)
                contadores = {"bak":0, "dat":0, "zip":0, "rar":0, "error":0}
                with st.spinner(f"Procesando {total} archivo(s)..."):
                    for i, nombre in enumerate(archivos_a_procesar):
                        datos = arch[nombre]
                        valido, tipo = validate_file(nombre, datos)
                        if not valido:
                            resultados.append({"archivo": nombre, "estado": "ERROR", "detalle": tipo})
                            contadores["error"] += 1
                        else:
                            ruta = guardar_archivo(nombre, datos, tipo, usuario)
                            if tipo == "bak":
                                process_bak(ruta, usuario)
                                contadores["bak"] += 1
                            elif tipo == "dat":
                                process_dat(ruta, usuario)
                                contadores["dat"] += 1
                            else:
                                process_compressed(ruta, usuario, tipo)
                                contadores[tipo] += 1
                            resultados.append({"archivo": nombre, "estado": "OK", "detalle": str(ruta)})
                        progress_bar.progress((i+1)/total)

                total_bak_dat = contadores["bak"] + contadores["dat"]
                if total_bak_dat > 0:
                    actualizar_reporte_excel(usuario, total_bak_dat, contadores["bak"], contadores["dat"])

                for r in resultados:
                    if r["archivo"] in st.session_state.archivos_subidos:
                        del st.session_state.archivos_subidos[r["archivo"]]
                st.session_state.resultados_proceso = resultados
                st.rerun()
    else:
        st.markdown('<div style="border:1px dashed #2a3040; border-radius:6px; padding:2rem; text-align:center;">Cola vacía — Suba archivos .bak, .dat, .zip o .rar</div>', unsafe_allow_html=True)

    if st.session_state.get("resultados_proceso"):
        render_section_header("RESULTADO DEL ÚLTIMO LOTE")
        for r in st.session_state.resultados_proceso:
            (st.success if r["estado"] == "OK" else st.error)(f"{'✓' if r['estado']=='OK' else '✗'} {r['archivo']}" + (f" — {r['detalle']}" if r['estado']!='OK' else ""))

    render_section_header("REPORTE DE ACTIVIDAD")
    df_reporte = leer_reporte(usuario)
    if df_reporte is not None and not df_reporte.empty:
        render_metric_grid([
            {"label": "Sesiones registradas", "value": len(df_reporte), "color": "green"},
            {"label": "BAK procesados", "value": int(df_reporte["Cantidad_BAK"].sum())},
            {"label": "DAT procesados", "value": int(df_reporte["Cantidad_DAT"].sum())},
            {"label": "Total archivos", "value": int(df_reporte["Total_Subidos"].sum())},
        ])
        st.dataframe(df_reporte.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

        col1, col2, _ = st.columns([1,1,2])
        if REPORTLAB_DISPONIBLE:
            pdf = exportar_pdf(df_reporte, f"Reporte Actividad - {usuario}")
            if pdf:
                with col1:
                    st.download_button("⬇ PDF", data=pdf, file_name=f"reporte_{usuario}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)
            else:
                with col1:
                    st.error("Error al generar PDF.")
        else:
            with col1:
                st.warning("PDF no disponible. Instale reportlab.")
        if usuario == "Admin":
            with col2:
                csv = df_reporte.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button("⬇ CSV", data=csv, file_name=f"reporte_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
    else:
        st.markdown('<div style="border:1px dashed #2a3040; border-radius:6px; padding:2rem; text-align:center;">Sin datos de actividad — Procese archivos BAK o DAT para generar el reporte.</div>', unsafe_allow_html=True)

# ============================================================
# ENTRYPOINT
# ============================================================

st.set_page_config(page_title="Central de Backups | TRC", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
init_session()

if not st.session_state.logged_in:
    pagina_login()
else:
    pagina_principal()

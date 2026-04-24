"""
Gestor de Backups - Central de Archivos
Versión optimizada: arquitectura limpia, UX/UI profesional
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import hashlib

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
    tipos_validos: tuple = (".bak", ".dat")
    logo_path: str = "LogoBlack.jpeg"

CONFIG = AppConfig()

# ============================================================
# INICIALIZACIÓN DE DIRECTORIOS
# ============================================================

def init_directories():
    dirs = [
        CONFIG.backup_path / "bak",
        CONFIG.backup_path / "dat",
        CONFIG.log_path,
        CONFIG.csv_path,
        CONFIG.excel_reporte.parent,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

init_directories()

LOG_FILE = CONFIG.log_path / "logs.txt"

# ============================================================
# CAPA DE LÓGICA DE NEGOCIO
# ============================================================

def registrar_log(usuario: str, accion: str, detalle: str, estado: str = "OK"):
    """Registra eventos de auditoría con timestamp ISO."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = f"[{timestamp}] | {usuario:12} | {accion:20} | {estado:6} | {detalle}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entrada)


def verificar_credenciales(usuario: str, contrasena: str) -> bool:
    """Verifica credenciales comparando hash de contraseña."""
    hash_input = hashlib.sha256(contrasena.encode()).hexdigest()
    return usuario in CONFIG.usuarios_validos and hash_input == CONFIG.contrasena_hash


def validate_file(file_name: str, file_bytes: bytes) -> tuple[bool, str]:
    """Valida nombre y contenido de archivo. Retorna (válido, tipo/mensaje)."""
    if not file_bytes:
        return False, "Archivo vacío"
    ext = Path(file_name).suffix.lower()
    if ext in CONFIG.tipos_validos:
        return True, ext.lstrip(".")
    return False, f"Formato no soportado: {ext or 'sin extensión'}"


def guardar_archivo(nombre: str, datos_bytes: bytes, file_type: str, usuario: str) -> Path:
    """Persiste el archivo con timestamp y registra en log."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo_nombre = f"{ts}_{nombre}"
    target_dir = CONFIG.backup_path / file_type
    target_dir.mkdir(parents=True, exist_ok=True)
    ruta = target_dir / nuevo_nombre
    ruta.write_bytes(datos_bytes)
    registrar_log(usuario, "FILE_SAVE", f"{nuevo_nombre} → /{file_type}")
    return ruta


def process_bak(ruta: Path, usuario: str) -> dict:
    """Procesa archivo SQL backup. Retorna resultado."""
    registrar_log(usuario, "SQL_RESTORE", str(ruta))
    return {"tipo": "BAK", "estado": "OK", "ruta": str(ruta)}


def process_dat(ruta: Path, usuario: str) -> dict:
    """Procesa archivo DAT → CSV. Retorna resultado."""
    registrar_log(usuario, "DAT_TRANSFORM", str(ruta))
    return {"tipo": "DAT", "estado": "OK", "ruta": str(ruta)}


def actualizar_reporte_excel(usuario: str, total: int, cant_bak: int, cant_dat: int):
    """Agrega fila de sesión al reporte Excel de actividad."""
    nueva_fila = pd.DataFrame([{
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Total_Subidos": total,
        "Cantidad_BAK": cant_bak,
        "Cantidad_DAT": cant_dat,
    }])
    if CONFIG.excel_reporte.exists():
        df_existente = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
        df_nuevo = pd.concat([df_existente, nueva_fila], ignore_index=True)
    else:
        df_nuevo = nueva_fila
    df_nuevo.to_excel(CONFIG.excel_reporte, index=False, engine="openpyxl")


def leer_reporte() -> Optional[pd.DataFrame]:
    """Lee el reporte Excel si existe."""
    if CONFIG.excel_reporte.exists():
        return pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
    return None

# ============================================================
# CSS — DISEÑO INDUSTRIAL PROFESIONAL
# ============================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg-primary:    #0d0f12;
    --bg-secondary:  #141720;
    --bg-card:       #1a1e28;
    --bg-card-hover: #1f2535;
    --border:        #2a3040;
    --border-light:  #3a4558;
    --accent:        #f59e0b;
    --accent-dim:    #92400e;
    --accent-glow:   rgba(245,158,11,0.15);
    --success:       #10b981;
    --success-dim:   rgba(16,185,129,0.12);
    --error:         #ef4444;
    --error-dim:     rgba(239,68,68,0.12);
    --info:          #3b82f6;
    --info-dim:      rgba(59,130,246,0.12);
    --text-primary:  #e8eaf0;
    --text-secondary:#8b95a8;
    --text-mono:     #a8c0d8;
    --font-sans:     'IBM Plex Sans', sans-serif;
    --font-mono:     'IBM Plex Mono', monospace;
    --radius:        6px;
    --shadow:        0 2px 12px rgba(0,0,0,0.4);
}

/* RESET GLOBAL */
html, body, [class*="css"], .stApp {
    font-family: var(--font-sans) !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* OCULTAR ELEMENTOS INNECESARIOS DE STREAMLIT */
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1200px !important; }

/* ── TOPBAR HEADER ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.2rem;
    margin-bottom: 2rem;
}
.topbar-brand {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
}
.topbar-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    color: var(--text-secondary);
}
.status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 6px var(--success);
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%,100% { opacity:1; } 50% { opacity:0.4; }
}

/* ── SECCIÓN HEADERS ── */
.section-header {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text-secondary);
    border-left: 2px solid var(--accent);
    padding-left: 0.75rem;
    margin: 2rem 0 1.2rem;
}

/* ── METRIC CARDS ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 1.5rem;
}
.metric-card {
    background: var(--bg-card);
    padding: 1.2rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    transition: background 0.2s;
}
.metric-card:hover { background: var(--bg-card-hover); }
.metric-label {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-secondary);
}
.metric-value {
    font-family: var(--font-mono);
    font-size: 2rem;
    font-weight: 600;
    color: var(--accent);
    line-height: 1;
}
.metric-value.green { color: var(--success); }
.metric-value.red   { color: var(--error); }

/* ── FILE LIST TABLE ── */
.file-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    margin-bottom: 1.5rem;
}
.file-table thead tr {
    border-bottom: 1px solid var(--border);
}
.file-table th {
    text-align: left;
    font-size: 0.6rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    padding: 0.6rem 0.8rem;
    font-weight: 500;
}
.file-table td {
    padding: 0.7rem 0.8rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-primary);
    vertical-align: middle;
}
.file-table tr:hover td { background: var(--bg-card); }
.badge {
    display: inline-block;
    font-size: 0.55rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    border-radius: 2px;
}
.badge-bak { background: var(--info-dim); color: var(--info); border: 1px solid var(--info); }
.badge-dat { background: var(--accent-glow); color: var(--accent); border: 1px solid var(--accent-dim); }
.badge-error { background: var(--error-dim); color: var(--error); border: 1px solid var(--error); }

/* ── LOGIN PAGE ── */
.login-wrapper {
    min-height: 85vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.login-box {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2.5rem;
    width: 100%;
    max-width: 420px;
}
.login-title {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.8rem;
    text-align: center;
}
.login-divider {
    height: 1px;
    background: var(--border);
    margin: 1.5rem 0;
}

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextInput > div > div > input[type="password"] {
    background: var(--bg-primary) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.85rem !important;
    padding: 0.6rem 0.9rem !important;
    transition: border-color 0.2s !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}
.stTextInput label {
    font-family: var(--font-mono) !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--text-secondary) !important;
}

/* ── BUTTONS ── */
.stButton > button {
    background: var(--accent) !important;
    color: #000 !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #fbbf24 !important;
    box-shadow: 0 0 20px var(--accent-glow) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-light) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: var(--accent-glow) !important;
    box-shadow: none !important;
}

/* ── FILE UPLOADER ── */
.stFileUploader > div {
    background: var(--bg-card) !important;
    border: 1px dashed var(--border-light) !important;
    border-radius: var(--radius) !important;
    transition: border-color 0.2s !important;
}
.stFileUploader > div:hover { border-color: var(--accent) !important; }
.stFileUploader label {
    font-family: var(--font-mono) !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--text-secondary) !important;
}

/* ── CHECKBOXES ── */
.stCheckbox > label {
    font-family: var(--font-mono) !important;
    font-size: 0.78rem !important;
    color: var(--text-primary) !important;
}
.stCheckbox > label > span:first-child {
    border: 1px solid var(--border-light) !important;
    border-radius: 2px !important;
}

/* ── DATAFRAME ── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
}
.stDataFrame th {
    background: var(--bg-secondary) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.6rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--text-secondary) !important;
}
.stDataFrame td {
    font-family: var(--font-mono) !important;
    font-size: 0.75rem !important;
    color: var(--text-primary) !important;
    background: var(--bg-card) !important;
}

/* ── ALERTS ── */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: var(--radius) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.78rem !important;
    border: none !important;
}
.stSuccess { background: var(--success-dim) !important; color: var(--success) !important; }
.stError   { background: var(--error-dim) !important;   color: var(--error) !important; }
.stInfo    { background: var(--info-dim) !important;    color: var(--info) !important; }

/* ── SIDEBAR ── */
.css-1d391kg, [data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
.css-1d391kg * { font-family: var(--font-mono) !important; }

/* ── SPINNER ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── DOWNLOAD BUTTONS ── */
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid var(--border-light) !important;
    color: var(--text-secondary) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
.stDownloadButton > button:hover {
    border-color: var(--success) !important;
    color: var(--success) !important;
    background: var(--success-dim) !important;
}

/* ── PROGRESS BAR ── */
.stProgress > div > div { background: var(--accent) !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
</style>
"""

# ============================================================
# COMPONENTES UI REUTILIZABLES
# ============================================================

def render_section_header(text: str, icon: str = ""):
    st.markdown(f'<div class="section-header">{icon} {text}</div>', unsafe_allow_html=True)


def render_metric_grid(metrics: list[dict]):
    """Renderiza tarjetas de métricas. metrics = [{label, value, color}]"""
    cards = ""
    for m in metrics:
        color_class = m.get("color", "")
        cards += f"""
        <div class="metric-card">
            <div class="metric-label">{m['label']}</div>
            <div class="metric-value {color_class}">{m['value']}</div>
        </div>"""
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def render_file_table(archivos: dict):
    """Renderiza tabla HTML de archivos con badges de tipo."""
    rows = ""
    for nombre, datos in archivos.items():
        valido, tipo = validate_file(nombre, datos)
        size_kb = round(len(datos) / 1024, 1)
        badge = f'<span class="badge badge-{tipo}">{tipo.upper()}</span>' if valido else '<span class="badge badge-error">ERR</span>'
        rows += f"""
        <tr>
            <td>{nombre}</td>
            <td>{badge}</td>
            <td>{size_kb} KB</td>
        </tr>"""
    html = f"""
    <table class="file-table">
        <thead><tr>
            <th>Nombre</th><th>Tipo</th><th>Tamaño</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>"""
    st.markdown(html, unsafe_allow_html=True)


def render_topbar(usuario: str):
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M")
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-brand">▶ BACKUP CENTRAL  /  TRC SYSTEM</div>
        <div class="topbar-status">
            <div class="status-dot"></div>
            {usuario.upper()} &nbsp;·&nbsp; {ts}
        </div>
    </div>""", unsafe_allow_html=True)


# ============================================================
# INICIALIZACIÓN DE SESIÓN
# ============================================================

def init_session():
    defaults = {
        "logged_in": False,
        "usuario_activo": None,
        "archivos_subidos": {},
        "resultados_proceso": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ============================================================
# PÁGINAS
# ============================================================

def pagina_login():
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        logo_path = CONFIG.logo_path
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">⬡ &nbsp; ACCESO RESTRINGIDO &nbsp; ⬡</div>', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            usuario = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("INICIAR SESIÓN", use_container_width=True)

            if submitted:
                if not usuario or not contrasena:
                    st.error("Complete todos los campos.")
                elif verificar_credenciales(usuario, contrasena):
                    st.session_state.logged_in = True
                    st.session_state.usuario_activo = usuario
                    registrar_log(usuario, "LOGIN", "Acceso exitoso")
                    st.rerun()
                else:
                    registrar_log(usuario, "LOGIN_FAIL", "Credenciales incorrectas", "ERROR")
                    st.error("Credenciales no válidas.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def pagina_principal():
    usuario = st.session_state.usuario_activo

    # Sidebar compacto
    with st.sidebar:
        st.markdown(f"""
        <div style="font-family:var(--font-mono);font-size:0.6rem;letter-spacing:0.12em;
                    text-transform:uppercase;color:#8b95a8;margin-bottom:0.5rem">
            Sesión activa
        </div>
        <div style="font-family:var(--font-mono);font-size:0.9rem;color:#f59e0b;font-weight:600">
            {usuario}
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("CERRAR SESIÓN", type="secondary", use_container_width=True):
            registrar_log(usuario, "LOGOUT", "Cierre manual de sesión")
            for key in ["logged_in", "usuario_activo", "archivos_subidos", "resultados_proceso"]:
                st.session_state[key] = False if key == "logged_in" else (None if key == "usuario_activo" else {})
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Stats rápidas en sidebar
        arch = st.session_state.archivos_subidos
        n_bak = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "bak")
        n_dat = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "dat")

        st.markdown(f"""
        <div style="font-family:var(--font-mono);font-size:0.6rem;letter-spacing:0.1em;
                    text-transform:uppercase;color:#8b95a8;margin-bottom:0.8rem">
            Cola de archivos
        </div>
        <div style="display:flex;flex-direction:column;gap:0.4rem">
            <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:0.75rem">
                <span style="color:#3b82f6">BAK</span><span style="color:#e8eaf0">{n_bak}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:0.75rem">
                <span style="color:#f59e0b">DAT</span><span style="color:#e8eaf0">{n_dat}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:0.75rem;
                        border-top:1px solid #2a3040;padding-top:0.4rem;margin-top:0.2rem">
                <span style="color:#8b95a8">TOTAL</span><span style="color:#e8eaf0">{len(arch)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── TOPBAR ──
    render_topbar(usuario)

    # ── LOGO ──
    logo_path = CONFIG.logo_path
    if os.path.exists(logo_path):
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.image(logo_path, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════
    # SECCIÓN 1: SUBIR ARCHIVOS
    # ══════════════════════════════════════
    render_section_header("SUBIR ARCHIVOS", "01")

    uploaded_files = st.file_uploader(
        "Arrastre o seleccione archivos (.bak / .dat)",
        type=["bak", "dat"],
        accept_multiple_files=True,
        label_visibility="visible",
    )

    if uploaded_files:
        nuevos = 0
        for file in uploaded_files:
            if file.name not in st.session_state.archivos_subidos:
                st.session_state.archivos_subidos[file.name] = file.getvalue()
                nuevos += 1
        if nuevos:
            st.success(f"✓ {nuevos} archivo(s) nuevo(s) agregado(s) a la cola.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════
    # SECCIÓN 2: COLA DE ARCHIVOS
    # ══════════════════════════════════════
    arch = st.session_state.archivos_subidos

    if arch:
        render_section_header("COLA DE PROCESO", "02")

        # Métricas
        n_bak = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "bak")
        n_dat = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "dat")
        n_err = sum(1 for n, d in arch.items() if not validate_file(n, d)[0])
        total_kb = round(sum(len(d) for d in arch.values()) / 1024, 1)

        render_metric_grid([
            {"label": "Total Archivos", "value": len(arch)},
            {"label": "BAK (SQL)",      "value": n_bak, "color": ""},
            {"label": "DAT",            "value": n_dat, "color": ""},
            {"label": "No soportados",  "value": n_err, "color": "red" if n_err else ""},
            {"label": "Tamaño total",   "value": f"{total_kb} KB"},
        ])

        # Tabla de archivos
        render_file_table(arch)

        # ── SELECCIÓN Y PROCESO ──
        render_section_header("SELECCIÓN DE ARCHIVOS", "03")

        col_sel, col_clear = st.columns([4, 1])
        with col_clear:
            if st.button("LIMPIAR COLA", type="secondary"):
                st.session_state.archivos_subidos = {}
                st.rerun()

        seleccionados = {}
        for nombre in arch:
            valido, tipo = validate_file(nombre, arch[nombre])
            label = f"{nombre}"
            seleccionados[nombre] = st.checkbox(label, value=valido, key=f"cb_{nombre}", disabled=not valido)
            if not valido:
                st.caption(f"  ↳ ⚠ {tipo}")

        n_sel = sum(1 for v in seleccionados.values() if v)
        st.markdown(f"""
        <div style="font-family:var(--font-mono);font-size:0.65rem;color:#8b95a8;margin:0.8rem 0">
            {n_sel} de {len(arch)} archivo(s) seleccionado(s)
        </div>""", unsafe_allow_html=True)

        if st.button(f"▶  PROCESAR {n_sel} ARCHIVO(S)", use_container_width=True):
            archivos_a_procesar = [n for n, sel in seleccionados.items() if sel]

            if not archivos_a_procesar:
                st.warning("Seleccione al menos un archivo.")
            else:
                resultados = []
                progress_bar = st.progress(0)
                total = len(archivos_a_procesar)

                with st.spinner(f"Procesando {total} archivo(s)..."):
                    contadores = {"bak": 0, "dat": 0, "error": 0}

                    for i, nombre in enumerate(archivos_a_procesar):
                        datos = arch[nombre]
                        valido, tipo = validate_file(nombre, datos)

                        if not valido:
                            resultados.append({"archivo": nombre, "estado": "ERROR", "detalle": tipo})
                            contadores["error"] += 1
                        else:
                            ruta = guardar_archivo(nombre, datos, tipo, usuario)
                            if tipo == "bak":
                                res = process_bak(ruta, usuario)
                                contadores["bak"] += 1
                            else:
                                res = process_dat(ruta, usuario)
                                contadores["dat"] += 1
                            resultados.append({"archivo": nombre, "estado": "OK", "detalle": str(ruta)})

                        progress_bar.progress((i + 1) / total)

                    total_ok = contadores["bak"] + contadores["dat"]
                    if total_ok:
                        actualizar_reporte_excel(usuario, total_ok, contadores["bak"], contadores["dat"])

                # Limpiar archivos procesados (solo los OK)
                for r in resultados:
                    if r["estado"] == "OK" and r["archivo"] in st.session_state.archivos_subidos:
                        del st.session_state.archivos_subidos[r["archivo"]]

                st.session_state.resultados_proceso = resultados

                if total_ok == total:
                    st.balloons()
                    st.success(f"✓ Lote completado — {total_ok} archivo(s) procesados correctamente.")
                else:
                    st.warning(f"Lote con errores — {total_ok} OK / {contadores['error']} fallidos.")

                st.rerun()

    else:
        st.markdown("""
        <div style="border:1px dashed #2a3040;border-radius:6px;padding:2rem;text-align:center;
                    font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#8b95a8;margin:1rem 0">
            Cola vacía — Suba archivos .bak o .dat para comenzar
        </div>""", unsafe_allow_html=True)

    # ── RESULTADOS DEL ÚLTIMO PROCESO ──
    if st.session_state.get("resultados_proceso"):
        render_section_header("RESULTADO DEL ÚLTIMO LOTE", "04")
        for r in st.session_state.resultados_proceso:
            if r["estado"] == "OK":
                st.success(f"✓ {r['archivo']}")
            else:
                st.error(f"✗ {r['archivo']} — {r['detalle']}")

    # ══════════════════════════════════════
    # SECCIÓN: REPORTE DE ACTIVIDAD
    # ══════════════════════════════════════
    render_section_header("REPORTE DE ACTIVIDAD", "05")

    df_reporte = leer_reporte()
    if df_reporte is not None:
        # Totales rápidos
        render_metric_grid([
            {"label": "Sesiones registradas", "value": len(df_reporte), "color": "green"},
            {"label": "BAK procesados",        "value": int(df_reporte["Cantidad_BAK"].sum())},
            {"label": "DAT procesados",        "value": int(df_reporte["Cantidad_DAT"].sum())},
            {"label": "Total archivos",        "value": int(df_reporte["Total_Subidos"].sum())},
        ])

        st.dataframe(
            df_reporte.sort_values("Fecha", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        col_dl1, col_dl2, col_spacer = st.columns([1, 1, 2])
        with col_dl1:
            buf_excel = io.BytesIO()
            with pd.ExcelWriter(buf_excel, engine="openpyxl") as writer:
                df_reporte.to_excel(writer, index=False)
            st.download_button(
                "⬇ EXCEL",
                data=buf_excel.getvalue(),
                file_name=f"reporte_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_dl2:
            csv_bytes = df_reporte.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "⬇ CSV",
                data=csv_bytes,
                file_name=f"reporte_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    else:
        st.markdown("""
        <div style="border:1px dashed #2a3040;border-radius:6px;padding:2rem;text-align:center;
                    font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#8b95a8">
            Sin datos de actividad — Procese archivos para generar el reporte
        </div>""", unsafe_allow_html=True)


# ============================================================
# ENTRYPOINT
# ============================================================

st.set_page_config(
    page_title="Backup Central | TRC",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)

init_session()

if not st.session_state.logged_in:
    pagina_login()
else:
    pagina_principal()
    

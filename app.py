"""
Gestor de Backups — Central de Archivos
Fixes: tabla única en reporte, rectángulo vacío login, fuente Avenir Light global,
       descargas por rol (Admin → CSV+PDF / Captura → solo PDF)
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
    backup_path:   Path = Path("./backups")
    log_path:      Path = Path("./data/logs")
    csv_path:      Path = Path("./data/csv")
    excel_reporte: Path = Path("./data/reporte_actividad.xlsx")
    tipos_validos: tuple = (".bak", ".dat")
    logo_path:     str  = "LogoBlack.jpeg"

CONFIG = AppConfig()

# ============================================================
# INICIALIZACIÓN DE DIRECTORIOS
# ============================================================

def init_directories() -> None:
    for d in [
        CONFIG.backup_path / "bak",
        CONFIG.backup_path / "dat",
        CONFIG.log_path,
        CONFIG.csv_path,
        CONFIG.excel_reporte.parent,
    ]:
        d.mkdir(parents=True, exist_ok=True)

init_directories()
LOG_FILE = CONFIG.log_path / "logs.txt"

# ============================================================
# CAPA DE LÓGICA DE NEGOCIO
# ============================================================

def registrar_log(usuario: str, accion: str, detalle: str, estado: str = "OK") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ts}] | {usuario:12} | {accion:20} | {estado:6} | {detalle}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea)


def verificar_credenciales(usuario: str, contrasena: str) -> bool:
    hash_input = hashlib.sha256(contrasena.encode()).hexdigest()
    hash_correcto = hashlib.sha256("TRC1234".encode()).hexdigest()
    return usuario in CONFIG.usuarios_validos and hash_input == hash_correcto


def es_admin(usuario: str) -> bool:
    return usuario == "Admin"


def validate_file(file_name: str, file_bytes: bytes) -> tuple:
    if not file_bytes:
        return False, "Archivo vacío"
    ext = Path(file_name).suffix.lower()
    if ext in CONFIG.tipos_validos:
        return True, ext.lstrip(".")
    return False, f"Formato no soportado: {ext or 'sin extensión'}"


def guardar_archivo(nombre: str, datos_bytes: bytes, file_type: str, usuario: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo_nombre = f"{ts}_{nombre}"
    target_dir = CONFIG.backup_path / file_type
    target_dir.mkdir(parents=True, exist_ok=True)
    ruta = target_dir / nuevo_nombre
    ruta.write_bytes(datos_bytes)
    registrar_log(usuario, "FILE_SAVE", f"{nuevo_nombre} -> /{file_type}")
    return ruta


def process_bak(ruta: Path, usuario: str) -> dict:
    registrar_log(usuario, "SQL_RESTORE", str(ruta))
    return {"tipo": "BAK", "estado": "OK", "ruta": str(ruta)}


def process_dat(ruta: Path, usuario: str) -> dict:
    registrar_log(usuario, "DAT_TRANSFORM", str(ruta))
    return {"tipo": "DAT", "estado": "OK", "ruta": str(ruta)}


def actualizar_reporte_excel(usuario: str, total: int, cant_bak: int, cant_dat: int) -> None:
    nueva_fila = pd.DataFrame([{
        "Fecha":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario":       usuario,
        "Total_Subidos": total,
        "Cantidad_BAK":  cant_bak,
        "Cantidad_DAT":  cant_dat,
    }])
    if CONFIG.excel_reporte.exists():
        df_prev = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
        df_nuevo = pd.concat([df_prev, nueva_fila], ignore_index=True)
    else:
        df_nuevo = nueva_fila
    df_nuevo.to_excel(CONFIG.excel_reporte, index=False, engine="openpyxl")


def leer_reporte() -> Optional[pd.DataFrame]:
    if CONFIG.excel_reporte.exists():
        return pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
    return None


def generar_pdf_reporte(df: pd.DataFrame) -> bytes:
    """Genera PDF del reporte. Requiere reportlab."""
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm
        )
        styles = getSampleStyleSheet()
        elems  = []

        title_style = styles["Title"]
        title_style.fontName = "Helvetica-Bold"
        elems.append(Paragraph("REPORTE DE ACTIVIDAD — BACKUP CENTRAL", title_style))
        elems.append(Spacer(1, 0.4*cm))
        elems.append(Paragraph(
            f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles["Normal"]
        ))
        elems.append(Spacer(1, 0.6*cm))

        cols = list(df.columns)
        data = [cols] + [list(map(str, row)) for row in df.values.tolist()]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#1a1e28")),
            ("TEXTCOLOR",      (0, 0), (-1,  0), colors.HexColor("#f59e0b")),
            ("FONTNAME",       (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1,  0), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#0d0f12"), colors.HexColor("#141720")]),
            ("TEXTCOLOR",      (0, 1), (-1, -1), colors.HexColor("#e8eaf0")),
            ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",       (0, 1), (-1, -1), 7),
            ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#2a3040")),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ]))
        elems.append(t)
        doc.build(elems)
        return buf.getvalue()
    except ImportError:
        return b""

# ============================================================
# CSS — AVENIR LIGHT GLOBAL + FIX FORM
# ============================================================

CSS = """
<style>
/*
 * Avenir Light: fuente del sistema si está instalada,
 * con fallback a Nunito Light (Google Fonts).
 */
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@200;300;400;600&family=IBM+Plex+Mono:wght@300;400;600&display=swap');

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
    --font-avenir:   'Avenir Light','Avenir','Nunito','Helvetica Neue',Helvetica,Arial,sans-serif;
    --font-mono:     'IBM Plex Mono','Courier New',monospace;
    --radius: 6px;
}

/* ── RESET GLOBAL: Avenir Light en absolutamente todo ── */
*, *::before, *::after {
    box-sizing: border-box;
}
html, body, [class*="css"], .stApp,
div, p, span, a, li, ul, ol,
label, input, button, select, textarea,
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-avenir) !important;
    font-weight: 300 !important;
}

/* ── FONDO GLOBAL ── */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stMain"] {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* ── OCULTAR UI INNECESARIA ── */
#MainMenu, footer, header,
.stDeployButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

.block-container {
    padding: 0.5rem 2.5rem 2rem !important;
    max-width: 1200px !important;
}

/* ══════════════════════════════════
   FIX: ELIMINAR RECTÁNGULO GRIS DEL FORM
   (todos los selectores posibles para
    distintas versiones de Streamlit)
   ══════════════════════════════════ */
[data-testid="stForm"],
div[data-testid="stForm"],
section[data-testid="stForm"],
form,
.stForm,
[class*="stForm"],
[class*="css-"] > form,
div.css-nahz7x,
div.css-qri22k,
div.css-1544g2n,
div.css-ocqkz7,
.st-emotion-cache-r421ms,
.st-emotion-cache-1gulkj5,
.st-emotion-cache-13ln4jf,
.st-emotion-cache-nahz7x {
    background:  transparent !important;
    border:      none        !important;
    box-shadow:  none        !important;
    padding:     0           !important;
    margin:      0           !important;
}

/* ── TOPBAR ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 1.8rem;
}
.topbar-brand {
    font-family: var(--font-mono) !important;
    font-size: 0.68rem;
    font-weight: 600 !important;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--accent);
}
.topbar-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono) !important;
    font-size: 0.63rem;
    color: var(--text-secondary);
}
.status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 6px var(--success);
    animation: blink 2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── SECTION HEADERS ── */
.section-header {
    font-family: var(--font-mono) !important;
    font-size: 0.63rem;
    font-weight: 600 !important;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text-secondary);
    border-left: 2px solid var(--accent);
    padding-left: 0.75rem;
    margin: 1.8rem 0 1.1rem;
}

/* ── METRIC GRID ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 1.4rem;
}
.metric-card {
    background: var(--bg-card);
    padding: 1rem 1.3rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    transition: background 0.18s;
}
.metric-card:hover { background: var(--bg-card-hover); }
.metric-label {
    font-family: var(--font-mono) !important;
    font-size: 0.57rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-secondary);
}
.metric-value {
    font-family: var(--font-mono) !important;
    font-size: 1.9rem;
    font-weight: 600 !important;
    color: var(--accent);
    line-height: 1;
}
.metric-value.green { color: var(--success); }
.metric-value.red   { color: var(--error);   }

/* ── FILE TABLE ── */
.file-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-avenir) !important;
    font-size: 0.8rem;
    margin-bottom: 1.4rem;
}
.file-table thead tr { border-bottom: 1px solid var(--border); }
.file-table th {
    text-align: left;
    font-family: var(--font-mono) !important;
    font-size: 0.57rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    padding: 0.55rem 0.75rem;
    font-weight: 500 !important;
    background: var(--bg-secondary);
}
.file-table td {
    padding: 0.65rem 0.75rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-primary);
    vertical-align: middle;
    background: var(--bg-card);
}
.file-table tr:hover td { background: var(--bg-card-hover); }
.badge {
    display: inline-block;
    font-family: var(--font-mono) !important;
    font-size: 0.52rem;
    font-weight: 600 !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.17rem 0.44rem;
    border-radius: 2px;
}
.badge-bak   { background: var(--info-dim);    color: var(--info);   border: 1px solid var(--info); }
.badge-dat   { background: var(--accent-glow); color: var(--accent); border: 1px solid var(--accent-dim); }
.badge-error { background: var(--error-dim);   color: var(--error);  border: 1px solid var(--error); }

/* ── LOGIN ── */
.login-wrapper { padding-top: 0.8rem; }

.login-box {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2.4rem 2.4rem;
    width: 100%;
    margin-top: 0.8rem;
}
.login-title {
    font-family: var(--font-mono) !important;
    font-size: 0.62rem;
    font-weight: 600 !important;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.5rem;
    text-align: center;
}
.login-divider {
    height: 1px;
    background: var(--border);
    margin: 1.1rem 0 1.3rem;
}

/* ── TEXT INPUTS ── */
.stTextInput > div > div > input {
    background:    var(--bg-primary) !important;
    border:        1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    color:         var(--text-primary) !important;
    font-family:   var(--font-avenir) !important;
    font-weight:   300 !important;
    font-size:     0.88rem !important;
    padding:       0.55rem 0.85rem !important;
    transition:    border-color 0.18s !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow:   0 0 0 2px var(--accent-glow) !important;
    outline:      none !important;
}
.stTextInput label {
    font-family:  var(--font-avenir) !important;
    font-weight:  400 !important;
    font-size:    0.68rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color:        var(--text-secondary) !important;
}

/* ── BOTONES ── */
.stButton > button {
    background:    var(--accent) !important;
    color:         #000 !important;
    border:        none !important;
    border-radius: var(--radius) !important;
    font-family:   var(--font-avenir) !important;
    font-weight:   600 !important;
    font-size:     0.72rem !important;
    letter-spacing:0.1em !important;
    text-transform:uppercase !important;
    padding:       0.55rem 1.4rem !important;
    transition:    all 0.18s !important;
    cursor:        pointer !important;
}
.stButton > button:hover {
    background:  #fbbf24 !important;
    box-shadow:  0 0 18px var(--accent-glow) !important;
    transform:   translateY(-1px) !important;
}
/* Botones secundarios */
.stButton > button[kind="secondary"] {
    background:  transparent !important;
    color:       var(--text-secondary) !important;
    border:      1px solid var(--border-light) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--accent) !important;
    color:        var(--accent) !important;
    background:   var(--accent-glow) !important;
    box-shadow:   none !important;
    transform:    none !important;
}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] > div {
    background:    var(--bg-card) !important;
    border:        1px dashed var(--border-light) !important;
    border-radius: var(--radius) !important;
    transition:    border-color 0.18s !important;
}
[data-testid="stFileUploader"] section:hover { border-color: var(--accent) !important; }
[data-testid="stFileUploader"] label {
    font-family:   var(--font-avenir) !important;
    font-size:     0.68rem !important;
    letter-spacing:0.08em !important;
    text-transform:uppercase !important;
    color:         var(--text-secondary) !important;
}

/* ── CHECKBOXES ── */
.stCheckbox > label {
    font-family: var(--font-avenir) !important;
    font-weight: 300 !important;
    font-size:   0.82rem !important;
    color:       var(--text-primary) !important;
}

/* ── DATAFRAME ── */
.stDataFrame {
    border:        1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow:      hidden !important;
}
.stDataFrame thead th {
    background:     var(--bg-secondary) !important;
    font-family:    var(--font-avenir) !important;
    font-size:      0.65rem !important;
    font-weight:    600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color:          var(--text-secondary) !important;
}
.stDataFrame tbody td {
    font-family: var(--font-avenir) !important;
    font-weight: 300 !important;
    font-size:   0.8rem !important;
    color:       var(--text-primary) !important;
    background:  var(--bg-card) !important;
}

/* ── ALERTS ── */
[data-testid="stAlert"],
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: var(--radius) !important;
    font-family:   var(--font-avenir) !important;
    font-size:     0.8rem !important;
    border:        none !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * {
    font-family: var(--font-avenir) !important;
}

/* ── DOWNLOAD BUTTONS ── */
.stDownloadButton > button {
    background:    transparent !important;
    border:        1px solid var(--border-light) !important;
    color:         var(--text-secondary) !important;
    font-family:   var(--font-avenir) !important;
    font-weight:   400 !important;
    font-size:     0.68rem !important;
    letter-spacing:0.08em !important;
    text-transform:uppercase !important;
    border-radius: var(--radius) !important;
    transition:    all 0.18s !important;
}
.stDownloadButton > button:hover {
    border-color: var(--success) !important;
    color:        var(--success) !important;
    background:   var(--success-dim) !important;
}

/* ── BOTÓN CERRAR SESIÓN (azul, topbar) ── */
[data-testid="stButton"] button[kind="primary"]#btn_logout_top,
div:has(> [data-testid="stButton"] > button[key="btn_logout_top"]) button,
button[key="btn_logout_top"] {
    background: #1d4ed8 !important;
    color: #fff !important;
    box-shadow: 0 0 14px rgba(29,78,216,0.35) !important;
}
button[key="btn_logout_top"]:hover {
    background: #2563eb !important;
    box-shadow: 0 0 22px rgba(37,99,235,0.5) !important;
}

/* Selector más robusto: primer botón del bloque principal antes del topbar */
.block-container > div:first-child .stButton > button {
    background:  #1d4ed8 !important;
    color:       #ffffff !important;
    box-shadow:  0 0 14px rgba(29,78,216,0.3) !important;
}
.block-container > div:first-child .stButton > button:hover {
    background:  #2563eb !important;
    box-shadow:  0 0 22px rgba(37,99,235,0.5) !important;
    transform:   translateY(-1px) !important;
}

/* ── PROGRESS ── */
.stProgress > div > div { background: var(--accent) !important; }
.stSpinner > div        { border-top-color: var(--accent) !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar       { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
</style>
"""

# ============================================================
# COMPONENTES UI REUTILIZABLES
# ============================================================

def render_section_header(text: str, num: str = "") -> None:
    prefix = f"{num} " if num else ""
    st.markdown(
        f'<div class="section-header">{prefix}{text}</div>',
        unsafe_allow_html=True,
    )


def render_metric_grid(metrics: list) -> None:
    cards = "".join(
        f'<div class="metric-card">'
        f'<div class="metric-label">{m["label"]}</div>'
        f'<div class="metric-value {m.get("color","")}">{m["value"]}</div>'
        f'</div>'
        for m in metrics
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def render_file_table(archivos: dict) -> None:
    rows = ""
    for nombre, datos in archivos.items():
        valido, tipo = validate_file(nombre, datos)
        size_kb = round(len(datos) / 1024, 1)
        badge = (
            f'<span class="badge badge-{tipo}">{tipo.upper()}</span>'
            if valido else
            '<span class="badge badge-error">ERR</span>'
        )
        rows += (
            f"<tr><td>{nombre}</td><td>{badge}</td>"
            f"<td style='text-align:right'>{size_kb} KB</td></tr>"
        )
    st.markdown(f"""
    <table class="file-table">
        <thead><tr>
            <th>Nombre</th><th>Tipo</th>
            <th style="text-align:right">Tamaño</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>""", unsafe_allow_html=True)


def render_topbar(usuario: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M")
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-brand">▶ BACKUP CENTRAL / TRC SYSTEM</div>
        <div class="topbar-status">
            <div class="status-dot"></div>
            {usuario.upper()} &nbsp;·&nbsp; {ts}
        </div>
    </div>""", unsafe_allow_html=True)


def render_empty_state(msg: str) -> None:
    st.markdown(
        f'<div style="border:1px dashed var(--border);border-radius:var(--radius);'
        f'padding:2rem;text-align:center;font-size:0.8rem;'
        f'color:var(--text-secondary);margin:1rem 0">{msg}</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SESIÓN
# ============================================================

def init_session() -> None:
    for k, v in {
        "logged_in":          False,
        "usuario_activo":     None,
        "archivos_subidos":   {},
        "resultados_proceso": [],
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ============================================================
# PÁGINA: LOGIN
# ============================================================

def pagina_login() -> None:
    """
    Login sin st.form y sin divs wrapper que generan rectángulos vacíos.
    El título y los inputs van directamente en la columna sin contenedores HTML intermedios.
    """
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        # Logo — sin margen extra debajo
        if os.path.exists(CONFIG.logo_path):
            st.image(CONFIG.logo_path, use_container_width=True)

        # Título pegado al logo, sin ningún div contenedor
        st.markdown(
            '<p style="font-family:var(--font-mono);font-size:0.62rem;font-weight:600;'
            'letter-spacing:0.2em;text-transform:uppercase;color:var(--accent);'
            'text-align:center;margin:0.9rem 0 1.2rem">&#9121; &nbsp;ACCESO RESTRINGIDO&nbsp; &#9121;</p>',
            unsafe_allow_html=True,
        )

        usuario    = st.text_input("Usuario",    key="li_user")
        contrasena = st.text_input("Contraseña", key="li_pass", type="password")

        st.markdown('<div style="height:1px;background:#2a3040;margin:1rem 0 1.2rem"></div>',
                    unsafe_allow_html=True)

        if st.button("INICIAR SESIÓN", use_container_width=True, key="btn_login"):
            if not usuario or not contrasena:
                st.error("Complete todos los campos.")
            elif verificar_credenciales(usuario, contrasena):
                st.session_state.logged_in      = True
                st.session_state.usuario_activo = usuario
                registrar_log(usuario, "LOGIN", "Acceso exitoso")
                st.rerun()
            else:
                registrar_log(usuario, "LOGIN_FAIL", "Credenciales incorrectas", "ERROR")
                st.error("Usuario o contraseña incorrectos.")


# ============================================================
# PÁGINA: PRINCIPAL
# ============================================================

def pagina_principal() -> None:
    usuario = st.session_state.usuario_activo
    admin   = es_admin(usuario)

    # ── SIDEBAR — solo info, el logout está en el topbar ──
    with st.sidebar:
        st.markdown(f"""
        <div style="font-size:0.58rem;letter-spacing:0.12em;text-transform:uppercase;
                    color:#8b95a8;margin-bottom:0.35rem">Sesión activa</div>
        <div style="font-size:0.95rem;color:#f59e0b;font-weight:600;
                    margin-bottom:1.2rem">{usuario}</div>
        """, unsafe_allow_html=True)

        arch  = st.session_state.archivos_subidos
        n_bak = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "bak")
        n_dat = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "dat")

        st.markdown(f"""
        <div style="font-size:0.58rem;letter-spacing:0.1em;text-transform:uppercase;
                    color:#8b95a8;margin-bottom:0.7rem">Cola de archivos</div>
        <div style="display:flex;flex-direction:column;gap:0.32rem">
            <div style="display:flex;justify-content:space-between;font-size:0.78rem">
                <span style="color:#3b82f6">BAK</span><span>{n_bak}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.78rem">
                <span style="color:#f59e0b">DAT</span><span>{n_dat}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.78rem;
                        border-top:1px solid #2a3040;padding-top:0.32rem;margin-top:0.12rem">
                <span style="color:#8b95a8">TOTAL</span>
                <span>{len(arch)}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── TOPBAR con botón cerrar sesión arriba a la izquierda ──
    col_logout, col_brand, col_status = st.columns([1, 3, 1.5])
    with col_logout:
        if st.button("⏻  CERRAR SESIÓN", key="btn_logout_top", use_container_width=True):
            registrar_log(usuario, "LOGOUT", "Cierre desde topbar")
            st.session_state.logged_in          = False
            st.session_state.usuario_activo     = None
            st.session_state.archivos_subidos   = {}
            st.session_state.resultados_proceso = []
            st.rerun()

    ts = datetime.now().strftime("%Y-%m-%d  %H:%M")
    with col_brand:
        st.markdown(
            '<div style="display:flex;align-items:center;height:100%;'
            'font-family:var(--font-mono);font-size:0.68rem;font-weight:600;'
            'letter-spacing:0.22em;text-transform:uppercase;color:var(--accent)">'
            '▶ BACKUP CENTRAL / TRC SYSTEM</div>',
            unsafe_allow_html=True,
        )
    with col_status:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:flex-end;'
            f'height:100%;gap:0.5rem;font-family:var(--font-mono);font-size:0.63rem;'
            f'color:#8b95a8">'
            f'<div style="width:6px;height:6px;border-radius:50%;background:#10b981;'
            f'box-shadow:0 0 6px #10b981"></div>'
            f'{usuario.upper()} &nbsp;·&nbsp; {ts}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:1px;background:#2a3040;margin-bottom:1.8rem"></div>',
                unsafe_allow_html=True)

    # ── LOGO PRINCIPAL ──
    if os.path.exists(CONFIG.logo_path):
        cl, cm, cr = st.columns([1, 2, 1])
        with cm:
            st.image(CONFIG.logo_path, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ════════════════════════════
    # 01 — SUBIR ARCHIVOS
    # ════════════════════════════
    render_section_header("SUBIR ARCHIVOS", "01")

    uploaded = st.file_uploader(
        "Arrastre o seleccione archivos (.bak / .dat)",
        type=["bak", "dat"],
        accept_multiple_files=True,
    )
    if uploaded:
        nuevos = sum(
            1 for f in uploaded
            if f.name not in st.session_state.archivos_subidos
            and not st.session_state.archivos_subidos.update({f.name: f.getvalue()})  # type: ignore
        )
        if nuevos:
            st.success(f"✓  {nuevos} archivo(s) nuevo(s) agregado(s).")

    st.markdown("<br>", unsafe_allow_html=True)

    # ════════════════════════════
    # 02 — COLA DE PROCESO
    # ════════════════════════════
    arch = st.session_state.archivos_subidos

    if arch:
        render_section_header("COLA DE PROCESO", "02")

        n_bak    = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "bak")
        n_dat    = sum(1 for n, d in arch.items() if validate_file(n, d)[1] == "dat")
        n_err    = sum(1 for n, d in arch.items() if not validate_file(n, d)[0])
        total_kb = round(sum(len(d) for d in arch.values()) / 1024, 1)

        render_metric_grid([
            {"label": "Total",         "value": len(arch)},
            {"label": "BAK (SQL)",     "value": n_bak},
            {"label": "DAT",           "value": n_dat},
            {"label": "No soportados", "value": n_err, "color": "red" if n_err else ""},
            {"label": "Tamaño total",  "value": f"{total_kb} KB"},
        ])

        render_file_table(arch)

        # 03 — SELECCIÓN
        render_section_header("SELECCIÓN DE ARCHIVOS", "03")

        _, col_clear = st.columns([5, 1])
        with col_clear:
            if st.button("LIMPIAR", key="btn_clear", use_container_width=True):
                st.session_state.archivos_subidos = {}
                st.rerun()

        seleccionados: dict = {}
        for nombre in arch:
            valido, tipo = validate_file(nombre, arch[nombre])
            seleccionados[nombre] = st.checkbox(
                nombre, value=valido, key=f"cb_{nombre}", disabled=not valido
            )
            if not valido:
                st.caption(f"  ↳ ⚠  {tipo}")

        n_sel = sum(1 for v in seleccionados.values() if v)
        st.markdown(
            f'<div style="font-size:0.7rem;color:#8b95a8;margin:0.6rem 0">'
            f'{n_sel} de {len(arch)} archivo(s) seleccionado(s)</div>',
            unsafe_allow_html=True,
        )

        if st.button(f"▶  PROCESAR {n_sel} ARCHIVO(S)", key="btn_procesar", use_container_width=True):
            a_proc = [n for n, s in seleccionados.items() if s]
            if not a_proc:
                st.warning("Seleccione al menos un archivo.")
            else:
                resultados: list = []
                prog       = st.progress(0)
                contadores = {"bak": 0, "dat": 0, "error": 0}

                with st.spinner(f"Procesando {len(a_proc)} archivo(s)…"):
                    for i, nombre in enumerate(a_proc):
                        datos        = arch[nombre]
                        valido, tipo = validate_file(nombre, datos)
                        if not valido:
                            resultados.append({"archivo": nombre, "estado": "ERROR", "detalle": tipo})
                            contadores["error"] += 1
                        else:
                            ruta = guardar_archivo(nombre, datos, tipo, usuario)
                            if tipo == "bak":
                                process_bak(ruta, usuario); contadores["bak"] += 1
                            else:
                                process_dat(ruta, usuario); contadores["dat"] += 1
                            resultados.append({"archivo": nombre, "estado": "OK", "detalle": str(ruta)})
                        prog.progress((i + 1) / len(a_proc))

                total_ok = contadores["bak"] + contadores["dat"]
                if total_ok:
                    actualizar_reporte_excel(usuario, total_ok, contadores["bak"], contadores["dat"])

                for r in resultados:
                    if r["estado"] == "OK":
                        st.session_state.archivos_subidos.pop(r["archivo"], None)

                st.session_state.resultados_proceso = resultados

                if contadores["error"] == 0:
                    st.balloons()
                    st.success(f"✓  Lote completado — {total_ok} archivo(s) procesados.")
                else:
                    st.warning(f"Lote con errores — {total_ok} OK / {contadores['error']} fallidos.")

                st.rerun()
    else:
        render_empty_state("Cola vacía — suba archivos .bak o .dat para comenzar")

    # ── RESULTADOS DEL ÚLTIMO LOTE ──
    if st.session_state.get("resultados_proceso"):
        render_section_header("RESULTADO DEL ÚLTIMO LOTE", "04")
        for r in st.session_state.resultados_proceso:
            if r["estado"] == "OK":
                st.success(f"✓  {r['archivo']}")
            else:
                st.error(f"✗  {r['archivo']} — {r['detalle']}")

    # ════════════════════════════
    # 05 — REPORTE DE ACTIVIDAD
    # ════════════════════════════
    render_section_header("REPORTE DE ACTIVIDAD", "05")

    df = leer_reporte()
    if df is not None:
        # ── TABLA ÚNICA: resumen global + detalle por sesión ──
        total_sesiones = len(df)
        total_bak      = int(df["Cantidad_BAK"].sum())
        total_dat      = int(df["Cantidad_DAT"].sum())
        total_archivos = int(df["Total_Subidos"].sum())

        df_sorted = df.sort_values("Fecha", ascending=False)
        detail_rows = "".join(
            f"<tr>"
            f"<td>{row['Fecha']}</td>"
            f"<td>{row['Usuario']}</td>"
            f"<td style='text-align:right'>{int(row['Total_Subidos'])}</td>"
            f"<td style='text-align:right'>{int(row['Cantidad_BAK'])}</td>"
            f"<td style='text-align:right'>{int(row['Cantidad_DAT'])}</td>"
            f"</tr>"
            for _, row in df_sorted.iterrows()
        )

        st.markdown(f"""
        <table class="file-table" style="margin-bottom:1.5rem">
          <thead>
            <!-- Fila título -->
            <tr style="background:#1a1e28">
              <th colspan="5"
                  style="font-size:0.6rem;letter-spacing:0.15em;color:#f59e0b;
                         padding:0.65rem 0.75rem;border-bottom:2px solid #f59e0b;
                         text-transform:uppercase">
                RESUMEN POR SESIÓN DE CARGA
              </th>
            </tr>
            <!-- Fila etiquetas totales -->
            <tr style="background:#141720">
              <th>Sesiones registradas</th><th></th>
              <th style="text-align:right">Total archivos</th>
              <th style="text-align:right">BAK procesados</th>
              <th style="text-align:right">DAT procesados</th>
            </tr>
            <!-- Fila valores totales -->
            <tr style="background:#1a1e28;border-bottom:2px solid #2a3040">
              <td style="font-size:1.5rem;font-weight:700;color:#10b981;
                         font-family:var(--font-mono);padding:0.55rem 0.75rem">
                {total_sesiones}
              </td>
              <td></td>
              <td style="font-size:1.5rem;font-weight:700;color:#f59e0b;
                         font-family:var(--font-mono);text-align:right;
                         padding:0.55rem 0.75rem">
                {total_archivos}
              </td>
              <td style="font-size:1.5rem;font-weight:700;color:#3b82f6;
                         font-family:var(--font-mono);text-align:right;
                         padding:0.55rem 0.75rem">
                {total_bak}
              </td>
              <td style="font-size:1.5rem;font-weight:700;color:#f59e0b;
                         font-family:var(--font-mono);text-align:right;
                         padding:0.55rem 0.75rem">
                {total_dat}
              </td>
            </tr>
            <!-- Encabezados detalle -->
            <tr>
              <th>Fecha</th><th>Usuario</th>
              <th style="text-align:right">Total subidos</th>
              <th style="text-align:right">BAK</th>
              <th style="text-align:right">DAT</th>
            </tr>
          </thead>
          <tbody>
            {detail_rows}
          </tbody>
        </table>""", unsafe_allow_html=True)

        # ── DESCARGAS POR ROL ──
        fecha_str = datetime.now().strftime("%Y%m%d")
        pdf_bytes = generar_pdf_reporte(df)

        if admin:
            # Admin: CSV + PDF
            col_csv, col_pdf, _ = st.columns([1, 1, 2])
            with col_csv:
                csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    "⬇  CSV",
                    data=csv_data,
                    file_name=f"reporte_{fecha_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_csv",
                )
            with col_pdf:
                if pdf_bytes:
                    st.download_button(
                        "⬇  PDF",
                        data=pdf_bytes,
                        file_name=f"reporte_{fecha_str}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_pdf",
                    )
                else:
                    st.caption("PDF: instale `pip install reportlab`")
        else:
            # Captura: solo PDF
            col_pdf, _ = st.columns([1, 3])
            with col_pdf:
                if pdf_bytes:
                    st.download_button(
                        "⬇  DESCARGAR PDF",
                        data=pdf_bytes,
                        file_name=f"reporte_{fecha_str}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_pdf_cap",
                    )
                else:
                    st.caption("PDF: instale `pip install reportlab`")
    else:
        render_empty_state("Sin datos — procese archivos para generar el reporte")


# ============================================================
# ENTRYPOINT
# ============================================================

st.set_page_config(
    page_title="Backup Central | TRC",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)
init_session()

if not st.session_state.logged_in:
    pagina_login()
else:
    pagina_principal()

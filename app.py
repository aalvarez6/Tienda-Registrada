import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import hashlib

# ReportLab opcional
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_DISPONIBLE = True
except ImportError:
    REPORTLAB_DISPONIBLE = False

# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------
@dataclass
class AppConfig:
    usuarios_validos: list = field(default_factory=lambda: [
        "Admin", "Captura1", "Captura2", "Captura3", "Captura4",
        "Captura5", "Captura6", "Captura7", "Captura8", "Captura9", "Captura10"
    ])
    contrasena_hash: str = hashlib.sha256("TRC1234".encode()).hexdigest()
    backup_path: Path = Path("./backups")
    log_path: Path = Path("./data/logs")
    excel_reporte: Path = Path("./data/reporte_actividad.xlsx")
    tipos_validos: tuple = (".bak", ".dat", ".zip", ".rar")
    logo_login: str = "LogoBlue.jpeg"

CONFIG = AppConfig()

# Crear directorios
for d in [CONFIG.backup_path / "bak", CONFIG.backup_path / "dat",
          CONFIG.backup_path / "compressed", CONFIG.log_path,
          CONFIG.excel_reporte.parent]:
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = CONFIG.log_path / "logs.txt"

# ------------------------------------------------------------
# Funciones de negocio
# ------------------------------------------------------------
def registrar_log(usuario, accion, detalle, estado="OK"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] | {usuario:12} | {accion:20} | {estado:6} | {detalle}\n")

def verificar_credenciales(usuario, contrasena):
    return (usuario in CONFIG.usuarios_validos and
            hashlib.sha256(contrasena.encode()).hexdigest() == CONFIG.contrasena_hash)

def validar_archivo(nombre, datos):
    if not datos:
        return False, "Archivo vacío"
    ext = Path(nombre).suffix.lower()
    if ext in CONFIG.tipos_validos:
        return True, ext[1:]
    return False, f"Formato no soportado: {ext or 'sin extensión'}"

def guardar_archivo(nombre, datos, tipo, usuario):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nuevo = f"{ts}_{nombre}"
    carpeta = CONFIG.backup_path / ("compressed" if tipo in ["zip","rar"] else tipo)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nuevo
    ruta.write_bytes(datos)
    registrar_log(usuario, "GUARDAR", str(ruta))
    return ruta

def procesar_bak(ruta, usuario):
    registrar_log(usuario, "PROC_BAK", str(ruta))
def procesar_dat(ruta, usuario):
    registrar_log(usuario, "PROC_DAT", str(ruta))
def procesar_zip(ruta, usuario, tipo):
    registrar_log(usuario, f"GUARDAR_{tipo.upper()}", str(ruta))

def actualizar_reporte(usuario, total, bak, dat):
    nueva = pd.DataFrame([{
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Total_Subidos": total,
        "Cantidad_BAK": bak,
        "Cantidad_DAT": dat,
    }])
    if CONFIG.excel_reporte.exists():
        df_old = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
        df_new = pd.concat([df_old, nueva], ignore_index=True)
    else:
        df_new = nueva
    df_new.to_excel(CONFIG.excel_reporte, index=False, engine="openpyxl")

def leer_reporte(usuario):
    if not CONFIG.excel_reporte.exists():
        return None
    df = pd.read_excel(CONFIG.excel_reporte, engine="openpyxl")
    return df if usuario == "Admin" else df[df["Usuario"] == usuario]

def exportar_pdf(df, titulo):
    if not REPORTLAB_DISPONIBLE:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = [Paragraph(titulo, ParagraphStyle('Title', parent=getSampleStyleSheet()['Heading1'],
                                              fontSize=14, alignment=1, spaceAfter=12)),
             Spacer(1, 12)]
    data = [df.columns.tolist()] + df.values.tolist()
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTSIZE', (0,1), (-1,-1), 8),
    ]))
    story.append(t)
    doc.build(story)
    return buffer.getvalue()

# ------------------------------------------------------------
# CSS (optimizado, sin márgenes extra en login)
# ------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Avenir+Light&display=swap');
* { font-family: 'Avenir Light', 'Avenir', sans-serif !important; }
html, body, .stApp { background: #0d0f12 !important; color: #e8eaf0 !important; font-size: 14pt !important; }
#MainMenu, footer, header, .stDeployButton { display: none; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1200px !important; }

:root {
    --bg: #0d0f12; --card: #1a1e28; --border: #2a3040;
    --accent: #0066FF; --accent-light: #2389FF;
    --red: #dc2626; --green: #10b981;
}
.topbar {
    display: flex; justify-content: space-between;
    border-bottom: 1px solid var(--border); padding-bottom: 0.8rem; margin-bottom: 1.5rem;
}
.topbar-brand { color: var(--accent); font-size: 0.7rem; letter-spacing: 0.2em; text-transform: uppercase; }
.topbar-status { font-size: 0.65rem; color: #8b95a8; }
.status-dot { display: inline-block; width: 6px; height: 6px; background: #10b981; border-radius: 50%; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

.section-header {
    border-left: 2px solid var(--accent); padding-left: 0.7rem;
    margin: 1.5rem 0 1rem; font-size: 0.7rem; letter-spacing: 0.18em;
    text-transform: uppercase; color: #8b95a8;
}

.metric-grid {
    display: flex; flex-wrap: wrap; gap: 1px; background: var(--border);
    border: 1px solid var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 1.5rem;
}
.metric-card {
    flex: 1; background: var(--card); padding: 1rem 1.2rem; transition: 0.2s;
}
.metric-card:hover { background: #1f2535; }
.metric-label { font-size: 0.6rem; text-transform: uppercase; color: #8b95a8; }
.metric-value { font-size: 1.8rem; font-weight: 600; color: var(--accent); line-height: 1; }
.metric-value.green { color: var(--green); }
.metric-value.red { color: var(--red); }

.file-table {
    width: 100%; border-collapse: collapse; margin-bottom: 1.5rem;
}
.file-table th, .file-table td {
    padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border);
}
.file-table th { font-size: 0.6rem; text-transform: uppercase; color: #8b95a8; font-weight: 500; }
.file-table td { font-size: 0.78rem; }
.file-table tr:hover td { background: var(--card); }
.badge {
    display: inline-block; font-size: 0.55rem; font-weight: 600; text-transform: uppercase;
    padding: 0.2rem 0.5rem; border-radius: 2px;
}
.badge-bak { background: rgba(59,130,246,0.12); color: #3b82f6; border: 1px solid #3b82f6; }
.badge-dat { background: rgba(0,102,255,0.15); color: #2389FF; border: 1px solid var(--accent); }
.badge-zip, .badge-rar { background: rgba(16,185,129,0.12); color: #10b981; border: 1px solid #10b981; }
.badge-error { background: rgba(239,68,68,0.12); color: #ef4444; border: 1px solid #ef4444; }

.login-wrapper { display: flex; flex-direction: column; align-items: center; padding-top: 0.5rem; }
.login-box {
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    padding: 1.8rem; width: 100%; max-width: 420px; margin-top: 0.5rem;
}
.login-title {
    font-size: 0.7rem; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--accent); text-align: center; margin-bottom: 1.2rem;
}
.login-divider { height: 1px; background: var(--border); margin: 1rem 0; }

.stTextInput > div > div > input, .stTextInput > div > div > input[type="password"] {
    background: var(--bg) !important; border: 1px solid #3a4558 !important;
    border-radius: 6px !important; color: #e8eaf0 !important;
    font-size: 0.85rem !important; padding: 0.4rem 0.8rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(0,102,255,0.25) !important;
}
.stTextInput label { font-size: 0.6rem !important; text-transform: uppercase !important; color: #8b95a8 !important; }

.stButton > button {
    background: var(--accent) !important; color: #fff !important; border: none !important;
    border-radius: 6px !important; font-size: 0.7rem !important; font-weight: 600 !important;
    letter-spacing: 0.12em !important; text-transform: uppercase !important;
    padding: 0.4rem 1.2rem !important;
}
.stButton > button:hover { background: var(--accent-light) !important; transform: translateY(-1px); }
.stButton > button[kind="secondary"] { background: var(--accent) !important; color: #fff !important; }

.stDownloadButton > button {
    background: transparent !important; border: 2px solid !important; font-weight: 600 !important;
}
.stDownloadButton:first-child > button { border-color: var(--red) !important; color: var(--red) !important; }
.stDownloadButton:first-child > button:hover { background: rgba(220,38,38,0.1) !important; }
.stDownloadButton:last-child > button { border-color: var(--green) !important; color: var(--green) !important; }
.stDownloadButton:last-child > button:hover { background: rgba(16,185,129,0.1) !important; }

.stFileUploader > div { background: var(--card) !important; border: 1px dashed #3a4558 !important; border-radius: 6px; }
.stFileUploader > div:hover { border-color: var(--accent) !important; }
.stFileUploader label { font-size: 0.65rem !important; text-transform: uppercase !important; color: #8b95a8 !important; }

.stCheckbox > label { font-size: 0.78rem !important; }
.stCheckbox > label > span:first-child { border: 1px solid #3a4558 !important; border-radius: 2px; }

.stDataFrame { border: 1px solid var(--border) !important; border-radius: 6px; overflow-x: auto; }
.stDataFrame th { background: #141720 !important; font-size: 0.6rem !important; text-transform: uppercase; }
.stDataFrame td { font-size: 0.75rem !important; background: var(--card); }

[data-testid="stSidebar"] { background: #141720 !important; border-right: 1px solid var(--border); }
.stSpinner > div { border-top-color: var(--accent) !important; }
</style>
"""

# ------------------------------------------------------------
# Componentes UI
# ------------------------------------------------------------
def render_section_header(texto):
    st.markdown(f'<div class="section-header">{texto}</div>', unsafe_allow_html=True)

def render_metric_grid(metrica_lista):
    html = '<div class="metric-grid">'
    for m in metrica_lista:
        color = f' {m.get("color", "")}' if m.get("color") else ''
        html += f'''
        <div class="metric-card">
            <div class="metric-label">{m["label"]}</div>
            <div class="metric-value{color}">{m["value"]}</div>
        </div>'''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_file_table(archivos):
    filas = ''
    for nom, datos in archivos.items():
        valido, tipo = validar_archivo(nom, datos)
        badge = f'<span class="badge badge-{tipo}">{tipo.upper()}</span>' if valido else '<span class="badge badge-error">ERR</span>'
        size = round(len(datos)/1024, 1)
        filas += f'<tr><td>{nom}</td><td>{badge}</td><td>{size} KB</td></tr>'
    st.markdown(f'''
    <table class="file-table">
        <thead><tr><th>Nombre</th><th>Tipo</th><th>Tamaño</th></tr></thead>
        <tbody>{filas}</tbody>
    </table>''', unsafe_allow_html=True)

def render_topbar(usuario):
    ahora = datetime.now().strftime("%Y-%m-%d  %H:%M")
    st.markdown(f'''
    <div class="topbar">
        <div class="topbar-brand">▶ CENTRAL DE BACKUPS  /  SISTEMA TRC</div>
        <div class="topbar-status"><div class="status-dot"></div> {usuario.upper()} · {ahora}</div>
    </div>''', unsafe_allow_html=True)

# ------------------------------------------------------------
# Sesión
# ------------------------------------------------------------
def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.usuario = None
        st.session_state.archivos = {}
        st.session_state.resultados = []

init_session()

# ------------------------------------------------------------
# Páginas
# ------------------------------------------------------------
def pagina_login():
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if os.path.exists(CONFIG.logo_login):
            st.image(CONFIG.logo_login, use_column_width=True)
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">ACCESO RESTRINGIDO</div>', unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                if not user or not pwd:
                    st.error("Complete todos los campos.")
                elif verificar_credenciales(user, pwd):
                    st.session_state.logged_in = True
                    st.session_state.usuario = user
                    registrar_log(user, "LOGIN", "OK")
                    st.rerun()
                else:
                    registrar_log(user, "LOGIN_FAIL", "Credenciales incorrectas", "ERROR")
                    st.error("Credenciales no válidas.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def pagina_principal():
    user = st.session_state.usuario

    # Sidebar
    with st.sidebar:
        st.markdown(f'<div style="font-size:0.8rem; text-transform:uppercase; color:#8b95a8;">Sesión activa</div>'
                    f'<div style="font-size:1rem; color:#0066FF; font-weight:600;">{user}</div>', unsafe_allow_html=True)
        if st.button("CERRAR SESIÓN", type="secondary", use_container_width=True):
            registrar_log(user, "LOGOUT", "Manual")
            st.session_state.logged_in = False
            st.session_state.usuario = None
            st.session_state.archivos = {}
            st.session_state.resultados = []
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

        arch = st.session_state.archivos
        bak = dat = zip = rar = 0
        for n, d in arch.items():
            ok, t = validar_archivo(n, d)
            if ok:
                if t == 'bak': bak += 1
                elif t == 'dat': dat += 1
                elif t == 'zip': zip += 1
                elif t == 'rar': rar += 1
        st.markdown(f'''
        <div style="font-size:0.7rem; text-transform:uppercase; color:#8b95a8;">Cola de archivos</div>
        <div style="display:flex; flex-direction:column; gap:0.3rem; margin-top:0.5rem;">
            <div><span style="color:#3b82f6">BAK</span> <span style="float:right">{bak}</span></div>
            <div><span style="color:#0066FF">DAT</span> <span style="float:right">{dat}</span></div>
            <div><span style="color:#10b981">ZIP/RAR</span> <span style="float:right">{zip+rar}</span></div>
            <hr style="margin:0.2rem 0;"><div><span style="color:#8b95a8">TOTAL</span> <span style="float:right">{len(arch)}</span></div>
        </div>''', unsafe_allow_html=True)

    render_topbar(user)
    # Botón extra cerrar
    if st.button("🚪 CERRAR SESIÓN", type="secondary"):
        registrar_log(user, "LOGOUT", "Botón principal")
        st.session_state.logged_in = False
        st.session_state.usuario = None
        st.session_state.archivos = {}
        st.session_state.resultados = []
        st.rerun()

    # Subida
    render_section_header("SUBIR ARCHIVOS")
    subidos = st.file_uploader("Arrastre o seleccione archivos (.bak / .dat / .zip / .rar)",
                               type=["bak","dat","zip","rar"], accept_multiple_files=True)
    if subidos:
        nuevos = 0
        for f in subidos:
            if f.name not in st.session_state.archivos:
                st.session_state.archivos[f.name] = f.getvalue()
                nuevos += 1
        if nuevos:
            st.success(f"✓ {nuevos} archivo(s) agregado(s)")
            st.rerun()

    arch = st.session_state.archivos
    if arch:
        render_section_header("COLA DE PROCESO")
        n_bak = sum(1 for n,d in arch.items() if validar_archivo(n,d)[1]=='bak')
        n_dat = sum(1 for n,d in arch.items() if validar_archivo(n,d)[1]=='dat')
        n_zip = sum(1 for n,d in arch.items() if validar_archivo(n,d)[1] in ['zip','rar'])
        n_err = sum(1 for n,d in arch.items() if not validar_archivo(n,d)[0])
        total_kb = round(sum(len(d) for d in arch.values())/1024, 1)
        render_metric_grid([
            {"label": "Total Archivos", "value": len(arch)},
            {"label": "BAK (SQL)", "value": n_bak},
            {"label": "DAT", "value": n_dat},
            {"label": "ZIP / RAR", "value": n_zip},
            {"label": "No soportados", "value": n_err, "color": "red" if n_err else ""},
            {"label": "Tamaño total", "value": f"{total_kb} KB"},
        ])
        render_file_table(arch)

        render_section_header("SELECCIÓN DE ARCHIVOS")
        col1, col2 = st.columns([4,1])
        with col2:
            if st.button("LIMPIAR COLA", type="secondary"):
                st.session_state.archivos = {}
                st.rerun()
        selec = {}
        for n in arch:
            ok, _ = validar_archivo(n, arch[n])
            selec[n] = st.checkbox(n, value=ok, key=f"ch_{n}", disabled=not ok)
        n_sel = sum(selec.values())
        st.markdown(f'<div style="font-size:0.8rem; color:#8b95a8;">{n_sel} de {len(arch)} archivo(s) seleccionado(s)</div>', unsafe_allow_html=True)

        if st.button(f"▶  PROCESAR {n_sel} ARCHIVO(S)", use_container_width=True):
            a_proc = [n for n, sel in selec.items() if sel]
            if not a_proc:
                st.warning("Seleccione al menos un archivo.")
            else:
                prog = st.progress(0)
                total = len(a_proc)
                cont = {"bak":0, "dat":0, "zip":0, "rar":0, "error":0}
                resultados = []
                for i, nom in enumerate(a_proc):
                    datos = arch[nom]
                    ok, tipo = validar_archivo(nom, datos)
                    if not ok:
                        resultados.append({"archivo": nom, "estado": "ERROR", "detalle": tipo})
                        cont["error"] += 1
                    else:
                        ruta = guardar_archivo(nom, datos, tipo, user)
                        if tipo == "bak":
                            procesar_bak(ruta, user)
                            cont["bak"] += 1
                        elif tipo == "dat":
                            procesar_dat(ruta, user)
                            cont["dat"] += 1
                        else:
                            procesar_zip(ruta, user, tipo)
                            cont[tipo] += 1
                        resultados.append({"archivo": nom, "estado": "OK", "detalle": str(ruta)})
                    prog.progress((i+1)/total)

                total_bak_dat = cont["bak"] + cont["dat"]
                if total_bak_dat > 0:
                    actualizar_reporte(user, total_bak_dat, cont["bak"], cont["dat"])
                for r in resultados:
                    if r["archivo"] in st.session_state.archivos:
                        del st.session_state.archivos[r["archivo"]]
                st.session_state.resultados = resultados
                st.rerun()
    else:
        st.markdown('<div style="border:1px dashed #2a3040; border-radius:6px; padding:2rem; text-align:center; color:#8b95a8;">Cola vacía — Suba archivos .bak, .dat, .zip o .rar</div>', unsafe_allow_html=True)

    if st.session_state.resultados:
        render_section_header("RESULTADO DEL ÚLTIMO LOTE")
        for r in st.session_state.resultados:
            if r["estado"] == "OK":
                st.success(f"✓ {r['archivo']}")
            else:
                st.error(f"✗ {r['archivo']} — {r['detalle']}")

    render_section_header("REPORTE DE ACTIVIDAD")
    df = leer_reporte(user)
    if df is not None and not df.empty:
        render_metric_grid([
            {"label": "Sesiones", "value": len(df), "color": "green"},
            {"label": "BAK", "value": int(df["Cantidad_BAK"].sum())},
            {"label": "DAT", "value": int(df["Cantidad_DAT"].sum())},
            {"label": "Total archivos", "value": int(df["Total_Subidos"].sum())},
        ])
        st.dataframe(df.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

        c1, c2, _ = st.columns([1,1,2])
        if REPORTLAB_DISPONIBLE:
            pdf = exportar_pdf(df, f"Reporte Actividad - {user}")
            if pdf:
                with c1:
                    st.download_button("⬇ PDF", data=pdf, file_name=f"reporte_{user}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)
            else:
                with c1:
                    st.error("Error PDF")
        else:
            with c1:
                st.warning("PDF no disponible: pip install reportlab")
        if user == "Admin":
            with c2:
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button("⬇ CSV", data=csv, file_name=f"reporte_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
    else:
        st.markdown('<div style="border:1px dashed #2a3040; border-radius:6px; padding:2rem; text-align:center; color:#8b95a8;">Sin datos — Procese archivos BAK/DAT</div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# Punto de entrada
# ------------------------------------------------------------
st.set_page_config(page_title="Central de Backups | TRC", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

if not st.session_state.logged_in:
    pagina_login()
else:
    pagina_principal()

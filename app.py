import re
import time
import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# Configurazione della pagina
st.set_page_config(page_title="Simulatore Percorsi 3D - Web App", layout="wide")

st.title("🌐 Simulatore Percorsi 3D - Visualizzatore SPF")

# Inizializzazione dello stato della sessione
if 'parsed_points' not in st.session_state:
    st.session_state.parsed_points = []
if 'lines' not in st.session_state:
    st.session_state.lines = []
if 'sim_idx' not in st.session_state:
    st.session_state.sim_idx = 0
if 'camera_base' not in st.session_state:
    st.session_state.camera_base = dict(x=0, y=-2.5, z=0)
if 'proj_type' not in st.session_state:
    st.session_state.proj_type = 'orthographic'
if 'ui_rev' not in st.session_state:
    st.session_state.ui_rev = 0
if 'show_code' not in st.session_state:
    st.session_state.show_code = True

# --- FUNZIONE MESH UTENSILE 3D ---
def get_3d_tool_data(x0, y0, z0, b_deg, cone_len=15, cone_rad=5, box_w=20, box_h=20, box_len=35):
    b_rad = math.radians(b_deg)
    cos_b, sin_b = math.cos(b_rad), math.sin(b_rad)
    
    def transform(pts):
        pts = np.array(pts)
        rx = pts[:, 0] * cos_b + pts[:, 2] * sin_b + x0
        ry = pts[:, 1] + y0
        rz = -pts[:, 0] * sin_b + pts[:, 2] * cos_b + z0
        return rx, ry, rz

    # 1. Cono (Punta)
    n_pts = 16
    angles = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    cone_pts = [[0, 0, 0]]
    for a in angles:
        cone_pts.append([cone_rad * math.cos(a), cone_rad * math.sin(a), cone_len])
    
    c_x, c_y, c_z = transform(cone_pts)
    c_i, c_j, c_k = [], [], []
    for m in range(1, n_pts + 1):
        next_m = 1 if m == n_pts else m + 1
        c_i.append(0)
        c_j.append(m)
        c_k.append(next_m)
        
    # 2. Parallelepipedo (Mandrino / Corpo)
    hw, hh = box_w / 2.0, box_h / 2.0
    z1, z2 = cone_len, cone_len + box_len
    
    box_pts = [
        [-hw, -hh, z1], [hw, -hh, z1], [hw, hh, z1], [-hw, hh, z1],
        [-hw, -hh, z2], [hw, -hh, z2], [hw, hh, z2], [-hw, hh, z2]
    ]
    b_x, b_y, b_z = transform(box_pts)
    
    b_i = [0, 0, 4, 4, 0, 0, 3, 3, 1, 1, 2, 2]
    b_j = [1, 2, 5, 6, 4, 7, 2, 6, 5, 6, 3, 7]
    b_k = [2, 3, 6, 7, 7, 3, 6, 7, 6, 2, 7, 6]
    
    return {
        'cone': (c_x, c_y, c_z, c_i, c_j, c_k),
        'box': (b_x, b_y, b_z, b_i, b_j, b_k)
    }

# --- FUNZIONE COSTRUZIONE FIGURA ---
def create_figure(sim_idx, camera_eye, proj_type, ui_rev):
    pts_data = st.session_state.parsed_points
    p_act = pts_data[sim_idx]
    x_act, y_act, z_act, b_act = p_act['X'], p_act['Y'], p_act['Z'], p_act['B']

    xs = [p['X'] for p in pts_data]
    ys = [p['Y'] for p in pts_data]
    zs = [p['Z'] for p in pts_data]
    
    # Calcolo Zoom all'Estensione
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    
    max_dim = max(x_max - x_min, y_max - y_min, z_max - z_min, 20.0)
    pad = max_dim * 0.15  
    
    cx, cy, cz = (x_min + x_max)/2, (y_min + y_max)/2, (z_min + z_max)/2
    half_len = (max_dim / 2) + pad

    point_colors = ['#4CAF50' if i < sim_idx else ('#F44336' if i == sim_idx else '#2196F3') for i in range(len(xs))]
            
    fig = go.Figure()

    # Percorso Linea
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs, mode='lines',
        line=dict(color='#888888', width=2, dash='dash'), name='Percorso'
    ))

    # Punti
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs, mode='markers',
        marker=dict(size=4, color=point_colors), name='Punti'
    ))

    # Utensile 3D (Cono + Parallelepipedo)
    tool_data = get_3d_tool_data(x_act, y_act, z_act, b_act)
    c_x, c_y, c_z, c_i, c_j, c_k = tool_data['cone']
    b_x, b_y, b_z, b_i, b_j, b_k = tool_data['box']

    fig.add_trace(go.Mesh3d(
        x=c_x, y=c_y, z=c_z, i=c_i, j=c_j, k=c_k,
        color='#FF5722', opacity=0.95, name='Punta'
    ))
    fig.add_trace(go.Mesh3d(
        x=b_x, y=b_y, z=b_z, i=b_i, j=b_j, k=b_k,
        color='#78909C', opacity=0.85, name='Mandrino'
    ))
    
    # Marker Punta
    fig.add_trace(go.Scatter3d(
        x=[x_act], y=[y_act], z=[z_act], mode='markers',
        marker=dict(size=5, color='black'), name='Punta Marker'
    ))

    fig.update_layout(
        uirevision=ui_rev,
        title=dict(text=f"Punto: {sim_idx}/{len(pts_data)-1} | X: {x_act:.2f} Y: {y_act:.2f} Z: {z_act:.2f} | B: {b_act:.1f}°", font=dict(size=13)),
        scene=dict(
            xaxis=dict(title='X (mm)', range=[cx - half_len, cx + half_len]),
            yaxis=dict(title='Y (mm)', range=[cy - half_len, cy + half_len]),
            zaxis=dict(title='Z (mm)', range=[cz - half_len, cz + half_len]),
            aspectmode='cube',
            camera=dict(
                eye=camera_eye,
                projection=dict(type=proj_type)
            )
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=500,
        showlegend=False
    )
    return fig


# --- SIDEBAR: Caricamento File e Telecamera ---
st.sidebar.header("📁 Controllo File")
uploaded_file = st.sidebar.file_uploader("Carica file SPF", type=["SPF", "spf", "txt"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    decoded_lines = file_bytes.decode("utf-8").splitlines(keepends=True)
    
    if decoded_lines != st.session_state.lines:
        st.session_state.lines = decoded_lines
        parsed = []
        last_b = 0.0  
        
        for idx, line in enumerate(st.session_state.lines):
            xm = re.search(r'X([+-]?\d*\.?\d+)', line)
            ym = re.search(r'Y([+-]?\d*\.?\d+)', line)
            zm = re.search(r'Z([+-]?\d*\.?\d+)', line)
            bm = re.search(r'B([+-]?\d*\.?\d+)', line)
            
            if xm and zm:
                if bm:
                    last_b = float(bm.group(1))
                    
                parsed.append({
                    'line_index': idx,
                    'raw_line': line.strip(),
                    'X': float(xm.group(1)),
                    'Y': float(ym.group(1)) if ym else 0.0,
                    'Z': float(zm.group(1)),
                    'B': last_b
                })
        st.session_state.parsed_points = parsed
        st.session_state.sim_idx = 0
        st.session_state.ui_rev += 1 
        st.session_state.camera_base = dict(x=0, y=-2.5, z=0)  # Default Vista Y+

if st.session_state.parsed_points:
    st.sidebar.markdown("---")
    st.sidebar.header("🎥 Controllo Viste 3D")
    
    col_v1, col_v2 = st.sidebar.columns(2)
    if col_v1.button("Vista Y+ (Default)"):
        st.session_state.camera_base = dict(x=0, y=-2.5, z=0)
        st.session_state.ui_rev += 1
    if col_v2.button("Vista Z+ (Alto)"):
        st.session_state.camera_base = dict(x=0, y=0, z=2.5)
        st.session_state.ui_rev += 1
        
    col_v3, col_v4 = st.sidebar.columns(2)
    if col_v3.button("Vista X+"):
        st.session_state.camera_base = dict(x=-2.5, y=0, z=0)
        st.session_state.ui_rev += 1
    if col_v4.button("Isometrica"):
        st.session_state.camera_base = dict(x=1.5, y=-1.5, z=1.5)
        st.session_state.ui_rev += 1
        
    proj_mode = st.sidebar.radio("Proiezione", ["Ortogonale", "Prospettica"], 
                                 index=0 if st.session_state.proj_type == 'orthographic' else 1,
                                 horizontal=True)
    
    st.session_state.proj_type = 'orthographic' if proj_mode == "Ortogonale" else 'perspective'

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Opzioni Animazione")
    sim_speed = st.sidebar.slider("Pausa tra punti (secondi)", 0.01, 0.30, 0.05, 0.01)

    # --- AREA PRINCIPALE ---
    max_p = len(st.session_state.parsed_points) - 1
    
    st.markdown("---")
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 2])
    
    start_anim = col_ctrl1.button("▶ AVVIA SIMULAZIONE", type="primary")
    reset_anim = col_ctrl2.button("⏮ Riavvolgi")
    
    if reset_anim:
        st.session_state.sim_idx = 0

    st.session_state.sim_idx = st.slider(
        "Posizione del percorso", 
        0, max_p, 
        st.session_state.sim_idx
    )

    # Contenitore Dinamico per Grafico e Codice
    chart_holder = st.empty()
    code_holder = st.empty()

    def render_state(idx):
        fig = create_figure(idx, st.session_state.camera_base, st.session_state.proj_type, st.session_state.ui_rev)
        chart_holder.plotly_chart(fig, use_container_width=True, config={'responsive': True})
        
        # Aggiornamento riga G-code
        p_act = st.session_state.parsed_points[idx]
        active_line_idx = p_act['line_index']
        
        code_html = "<div style='height: 140px; overflow-y: scroll; background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 5px; padding: 8px; font-family: monospace; font-size: 12px;'>"
        for l_idx, line in enumerate(st.session_state.lines):
            clean_line = line.strip()
            if l_idx == active_line_idx:
                code_html += f"<div style='background-color: #ffeb3b; color: #000; font-weight: bold; padding: 2px 4px;'>&rarr; {clean_line}</div>"
            else:
                code_html += f"<div style='color: #495057; padding: 2px 4px;'>&nbsp;&nbsp;&nbsp;&nbsp;{clean_line}</div>"
        code_html += "</div>"
        code_holder.markdown(code_html, unsafe_allow_html=True)

    # LOOP ANIMAZIONE SENZA RERUN
    if start_anim:
        for idx in range(st.session_state.sim_idx, max_p + 1):
            st.session_state.sim_idx = idx
            render_state(idx)
            time.sleep(sim_speed)
    else:
        render_state(st.session_state.sim_idx)

else:
    st.info("👈 Per iniziare, carica un file SPF dal pannello di sinistra.")

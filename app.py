import re
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
if 'camera_base' not in st.session_state:
    st.session_state.camera_base = dict(x=0, y=-2.5, z=0)
if 'proj_type' not in st.session_state:
    st.session_state.proj_type = 'orthographic'

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
        st.session_state.camera_base = dict(x=0, y=-2.5, z=0)  # Default Vista Y+

if st.session_state.parsed_points:
    st.sidebar.markdown("---")
    st.sidebar.header("🎥 Controllo Viste 3D")
    
    col_v1, col_v2 = st.sidebar.columns(2)
    if col_v1.button("Vista Y+ (Default)"):
        st.session_state.camera_base = dict(x=0, y=-2.5, z=0)
    if col_v2.button("Vista Z+ (Alto)"):
        st.session_state.camera_base = dict(x=0, y=0, z=2.5)
        
    col_v3, col_v4 = st.sidebar.columns(2)
    if col_v3.button("Vista X+"):
        st.session_state.camera_base = dict(x=-2.5, y=0, z=0)
    if col_v4.button("Isometrica"):
        st.session_state.camera_base = dict(x=1.5, y=-1.5, z=1.5)
        
    proj_mode = st.sidebar.radio("Proiezione", ["Ortogonale", "Prospettica"], 
                                 index=0 if st.session_state.proj_type == 'orthographic' else 1,
                                 horizontal=True)
    st.session_state.proj_type = 'orthographic' if proj_mode == "Ortogonale" else 'perspective'

    # --- COSTRUZIONE GRAFICO CON ANIMAZIONE NATIVA PLOTLY ---
    pts_data = st.session_state.parsed_points
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

    # Stato Iniziale (Punto 0)
    p0 = pts_data[0]
    tool0 = get_3d_tool_data(p0['X'], p0['Y'], p0['Z'], p0['B'])
    c_x, c_y, c_z, c_i, c_j, c_k = tool0['cone']
    b_x, b_y, b_z, b_i, b_j, b_k = tool0['box']

    # Tracce di Base
    trace_path = go.Scatter3d(
        x=xs, y=ys, z=zs, mode='lines',
        line=dict(color='#888888', width=2, dash='dash'), name='Percorso'
    )
    trace_points = go.Scatter3d(
        x=xs, y=ys, z=zs, mode='markers',
        marker=dict(size=4, color='#2196F3'), name='Punti'
    )
    trace_cone = go.Mesh3d(
        x=c_x, y=c_y, z=c_z, i=c_i, j=c_j, k=c_k,
        color='#FF5722', opacity=0.95, name='Punta'
    )
    trace_box = go.Mesh3d(
        x=b_x, y=b_y, z=b_z, i=b_i, j=b_j, k=b_k,
        color='#78909C', opacity=0.85, name='Mandrino'
    )
    trace_tip = go.Scatter3d(
        x=[p0['X']], y=[p0['Y']], z=[p0['Z']], mode='markers',
        marker=dict(size=5, color='black'), name='Punta Marker'
    )

    # Creazione dei Frame dell'Animazione per il Browser
    frames = []
    for k, p in enumerate(pts_data):
        t_data = get_3d_tool_data(p['X'], p['Y'], p['Z'], p['B'])
        cx_k, cy_k, cz_k, _, _, _ = t_data['cone']
        bx_k, by_k, bz_k, _, _, _ = t_data['box']
        
        # Colori dei punti durante la progressione
        p_colors = ['#4CAF50' if i < k else ('#F44336' if i == k else '#2196F3') for i in range(len(xs))]
        
        frames.append(go.Frame(
            data=[
                trace_path,
                go.Scatter3d(x=xs, y=ys, z=zs, mode='markers', marker=dict(size=4, color=p_colors)),
                go.Mesh3d(x=cx_k, y=cy_k, z=cz_k, i=c_i, j=c_j, k=c_k, color='#FF5722', opacity=0.95),
                go.Mesh3d(x=bx_k, y=by_k, z=bz_k, i=b_i, j=b_j, k=b_k, color='#78909C', opacity=0.85),
                go.Scatter3d(x=[p['X']], y=[p['Y']], z=[p['Z']], mode='markers', marker=dict(size=5, color='black'))
            ],
            name=f"frame_{k}"
        ))

    fig = go.Figure(
        data=[trace_path, trace_points, trace_cone, trace_box, trace_tip],
        frames=frames
    )

    # Pulsanti di riproduzione integrati nel grafico
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='X (mm)', range=[cx - half_len, cx + half_len]),
            yaxis=dict(title='Y (mm)', range=[cy - half_len, cy + half_len]),
            zaxis=dict(title='Z (mm)', range=[cz - half_len, cz + half_len]),
            aspectmode='cube',
            camera=dict(
                eye=st.session_state.camera_base,
                projection=dict(type=st.session_state.proj_type)
            )
        ),
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {
                    "label": "▶ AVVIA ANIMAZIONE",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 50, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}]
                },
                {
                    "label": "⏸ PAUSA",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}]
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 10},
            "showactive": False,
            "x": 0.1,
            "y": 0,
            "xanchor": "right",
            "yanchor": "top"
        }],
        margin=dict(l=0, r=0, b=0, t=30),
        height=550,
        showlegend=False
    )

    # Rendering del grafico Plotly
    st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

    # Visualizzatore Codice SPF
    with st.expander("📜 Visualizzatore Codice SPF (G-code)", expanded=True):
        code_html = "<div style='height: 150px; overflow-y: scroll; background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 5px; padding: 8px; font-family: monospace; font-size: 12px;'>"
        for line in st.session_state.lines:
            code_html += f"<div style='color: #495057; padding: 1px 4px;'>{line.strip()}</div>"
        code_html += "</div>"
        st.markdown(code_html, unsafe_allow_html=True)

else:
    st.info("👈 Per iniziare, carica un file SPF dal pannello di sinistra.")

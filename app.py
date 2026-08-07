import re
import math
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

# Configurazione della pagina
st.set_page_config(page_title="Simulatore 3D - Cinematica Inversa Tavola", layout="wide")

st.title("🌐 Simulatore 3D - Cinematica Inversa (Tavola Rotante B)")

# Inizializzazione dello stato della sessione
if 'parsed_points' not in st.session_state:
    st.session_state.parsed_points = []
if 'lines' not in st.session_state:
    st.session_state.lines = []
if 'camera_base' not in st.session_state:
    st.session_state.camera_base = dict(x=0, y=-2.5, z=0)
if 'proj_type' not in st.session_state:
    st.session_state.proj_type = 'orthographic'
if 'show_gcode' not in st.session_state:
    st.session_state.show_gcode = True
if 'sim_idx' not in st.session_state:
    st.session_state.sim_idx = 0

# --- 1. UTENSILE FISSO VERTICALE (Punta orientata verso Z-) ---
def get_fixed_vertical_tool(x0, y0, z0, cone_len=15, cone_rad=5, box_w=20, box_h=20, box_len=35):
    n_pts = 16
    angles = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    
    c_x = [x0] + [(cone_rad * math.cos(a)) + x0 for a in angles]
    c_y = [y0] + [(cone_rad * math.sin(a)) + y0 for a in angles]
    c_z = [z0] + [cone_len + z0 for _ in angles]
    
    c_i, c_j, c_k = [], [], []
    for m in range(1, n_pts + 1):
        next_m = 1 if m == n_pts else m + 1
        c_i.append(0)
        c_j.append(m)
        c_k.append(next_m)
        
    hw, hh = box_w / 2.0, box_h / 2.0
    z1, z2 = cone_len + z0, cone_len + box_len + z0
    
    box_pts = [
        [-hw + x0, -hh + y0, z1], [hw + x0, -hh + y0, z1], [hw + x0, hh + y0, z1], [-hw + x0, hh + y0, z1],
        [-hw + x0, -hh + y0, z2], [hw + x0, -hh + y0, z2], [hw + x0, hh + y0, z2], [-hw + x0, hh + y0, z2]
    ]
    b_pts = np.array(box_pts)
    b_x, b_y, b_z = b_pts[:, 0], b_pts[:, 1], b_pts[:, 2]
    
    b_i = [0, 0, 4, 4, 0, 0, 3, 3, 1, 1, 2, 2]
    b_j = [1, 2, 5, 6, 4, 7, 2, 6, 5, 6, 3, 7]
    b_k = [2, 3, 6, 7, 7, 3, 6, 7, 6, 2, 7, 6]
    
    return {
        'cone': (c_x, c_y, c_z, c_i, c_j, c_k),
        'box': (b_x, b_y, b_z, b_i, b_j, b_k)
    }

# --- 2. CINEMATICA INVERSA TAVOLA ---
def rotate_point_around_table_y(x, y, z, b_deg):
    b_rad = math.radians(-b_deg)
    cos_b, sin_b = math.cos(b_rad), math.sin(b_rad)
    
    rx = x * cos_b + z * sin_b
    ry = y
    rz = -x * sin_b + z * cos_b
    return rx, ry, rz

# --- SIDEBAR: Controllo File e Visualizzazione ---
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
        st.session_state.camera_base = dict(x=0, y=-2.5, z=0)

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

    st.sidebar.markdown("---")
    st.sidebar.header("📜 Opzioni Codice")
    st.session_state.show_gcode = st.sidebar.checkbox("Mostra Codice G-code", value=st.session_state.show_gcode)

    # --- SIMULAZIONE E TRASFORMAZIONE ---
    pts_data = st.session_state.parsed_points
    
    transformed_frames_pts = []
    for p in pts_data:
        b_act = p['B']
        pts_rot = [rotate_point_around_table_y(pt['X'], pt['Y'], pt['Z'], b_act) for pt in pts_data]
        transformed_frames_pts.append(pts_rot)

    LIMIT_MIN = -350.0
    LIMIT_MAX = 350.0

    # Frame 0
    frame0_pts = np.array(transformed_frames_pts[0])
    x0_rot, y0_rot, z0_rot = frame0_pts[0]
    
    tool0 = get_fixed_vertical_tool(x0_rot, y0_rot, z0_rot)
    c_x, c_y, c_z, c_i, c_j, c_k = tool0['cone']
    b_x, b_y, b_z, b_i, b_j, b_k = tool0['box']

    trace_path = go.Scatter3d(
        x=frame0_pts[:, 0], y=frame0_pts[:, 1], z=frame0_pts[:, 2], mode='lines',
        line=dict(color='#888888', width=2, dash='dash'), name='Percorso (Tavola)'
    )
    trace_points = go.Scatter3d(
        x=frame0_pts[:, 0], y=frame0_pts[:, 1], z=frame0_pts[:, 2], mode='markers',
        marker=dict(size=2, color='#2196F3'), name='Punti'
    )
    trace_cone = go.Mesh3d(
        x=c_x, y=c_y, z=c_z, i=c_i, j=c_j, k=c_k,
        color='#FF5722', opacity=0.95, name='Punta Utensile'
    )
    trace_box = go.Mesh3d(
        x=b_x, y=b_y, z=b_z, i=b_i, j=b_j, k=b_k,
        color='#78909C', opacity=0.85, name='Testa Fissa'
    )
    trace_origin = go.Scatter3d(
        x=[0], y=[0], z=[0], mode='markers+text',
        marker=dict(size=6, color='purple', symbol='diamond'),
        text=["Centro Tavola (0,0,0)"], textposition="bottom center", name='Centro Tavola'
    )

    frames = []
    for k, p in enumerate(pts_data):
        frame_k_pts = np.array(transformed_frames_pts[k])
        xk_rot, yk_rot, zk_rot = frame_k_pts[k]
        
        t_data = get_fixed_vertical_tool(xk_rot, yk_rot, zk_rot)
        cx_k, cy_k, cz_k, _, _, _ = t_data['cone']
        bx_k, by_k, bz_k, _, _, _ = t_data['box']
        
        p_colors = ['#4CAF50' if i < k else ('#F44336' if i == k else '#2196F3') for i in range(len(pts_data))]
        
        frames.append(go.Frame(
            data=[
                go.Scatter3d(x=frame_k_pts[:, 0], y=frame_k_pts[:, 1], z=frame_k_pts[:, 2], mode='lines', line=dict(color='#888888', width=2, dash='dash')),
                go.Scatter3d(x=frame_k_pts[:, 0], y=frame_k_pts[:, 1], z=frame_k_pts[:, 2], mode='markers', marker=dict(size=2, color=p_colors)),
                go.Mesh3d(x=cx_k, y=cy_k, z=cz_k, i=c_i, j=c_j, k=c_k, color='#FF5722', opacity=0.95),
                go.Mesh3d(x=bx_k, y=by_k, z=bz_k, i=b_i, j=b_j, k=b_k, color='#78909C', opacity=0.85),
                trace_origin
            ],
            name=f"frame_{k}"
        ))

    fig = go.Figure(
        data=[trace_path, trace_points, trace_cone, trace_box, trace_origin],
        frames=frames
    )

    # SELETTORE VELOCITÀ NEL PLAYER E CONTROLLI
    speed_factor = st.select_slider(
        "⚡ Velocità Animazione Player:",
        options=[0.2, 0.5, 1.0, 2.0, 5.0],
        value=1.0,
        format_func=lambda x: f"{x}x (" + ("Fast" if x > 1 else ("Slow" if x < 1 else "Normal") + ")")
    )
    
    base_duration = 60
    adjusted_duration = max(10, int(base_duration / speed_factor))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='X (mm)', range=[LIMIT_MIN, LIMIT_MAX]),
            yaxis=dict(title='Y (mm)', range=[LIMIT_MIN, LIMIT_MAX]),
            zaxis=dict(title='Z (mm)', range=[LIMIT_MIN, LIMIT_MAX]),
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
                    "label": "▶ AVVIA ANIMAZIONE TAVOLA",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": adjusted_duration, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}]
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

    st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

    # CURSORE PUNTO
    selected_idx = st.slider("Ispeziona punto / blocco specifico:", 0, len(pts_data) - 1, st.session_state.sim_idx)
    st.session_state.sim_idx = selected_idx
    
    # VISUALIZZATORE NATIVO COORDINATE
    p_curr = pts_data[st.session_state.sim_idx]
    
    st.markdown("---")
    st.subheader("📌 Coordinate Punto Selezionato")
    col_x, col_y, col_z, col_b = st.columns(4)
    col_x.metric("Asse X", f"{p_curr['X']:.3f} mm")
    col_y.metric("Asse Y", f"{p_curr['Y']:.3f} mm")
    col_z.metric("Asse Z", f"{p_curr['Z']:.3f} mm")
    col_b.metric("Asse Tavola (B)", f"{p_curr['B']:.2f}°")

    # VISUALIZZATORE CODICE OPZIONALE CON AUTO-SCROLL GARANTITO VIA IFRAME
    if st.session_state.show_gcode:
        st.markdown("### 📜 Codice G-code Sincronizzato")
        active_line_idx = p_curr['line_index']
        
        # Generazione HTML + JS nativo isolato che forza lo scroll al blocco attivo
        lines_html = ""
        for idx, line in enumerate(st.session_state.lines):
            clean_line = line.strip()
            if idx == active_line_idx:
                lines_html += f"<div id='active-line' style='background-color: #ffeb3b; color: #000; font-weight: bold; padding: 4px 8px; border-left: 5px solid #ff9800;'>&rarr; {clean_line}</div>"
            else:
                lines_html += f"<div style='color: #333; padding: 2px 8px;'>&nbsp;&nbsp;&nbsp;&nbsp;{clean_line}</div>"
        
        custom_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    font-family: monospace;
                    font-size: 13px;
                }}
                #gcode-container {{
                    height: 180px;
                    overflow-y: auto;
                    background-color: #f8f9fa;
                    border: 1px solid #ced4da;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <div id="gcode-container">
                {lines_html}
            </div>
            <script>
                window.onload = function() {{
                    var active = document.getElementById('active-line');
                    if (active) {{
                        active.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}
                }};
            </script>
        </body>
        </html>
        """
        components.html(custom_html, height=200)

else:
    st.info("👈 Per iniziare, carica un file SPF dal pannello di sinistra.")

import re
import time
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# Configurazione della pagina a tutto schermo
st.set_page_config(page_title="Simulatore Percorsi 3D - Web App", layout="wide")

st.title("🌐 Simulatore Percorsi 3D - Visualizzatore SPF")

# Inizializzazione dello stato della sessione di Streamlit
if 'parsed_points' not in st.session_state:
    st.session_state.parsed_points = []
if 'lines' not in st.session_state:
    st.session_state.lines = []
if 'sim_idx' not in st.session_state:
    st.session_state.sim_idx = 0
if 'is_animating' not in st.session_state:
    st.session_state.is_animating = False
if 'camera_base' not in st.session_state:
    st.session_state.camera_base = (0, -2.5, 0)
if 'zoom_level' not in st.session_state:
    st.session_state.zoom_level = 1.0
if 'proj_type' not in st.session_state:
    st.session_state.proj_type = 'orthographic'

# --- SIDEBAR: Controlli e Caricamento File ---
st.sidebar.header("📁 Controllo File")
uploaded_file = st.sidebar.file_uploader("Carica file SPF", type=["SPF", "spf", "txt"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    decoded_lines = file_bytes.decode("utf-8").splitlines(keepends=True)
    
    if decoded_lines != st.session_state.lines:
        st.session_state.lines = decoded_lines
        
        parsed = []
        last_b = 0.0  # Memoria dell'ultima B incontrata (modalità CNC)
        
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
        st.session_state.is_animating = False

if st.session_state.parsed_points:
    st.sidebar.markdown("---")
    st.sidebar.header("🎥 Controllo Viste 3D")
    
    col_v1, col_v2 = st.sidebar.columns(2)
    if col_v1.button("Vista Y+"):
        st.session_state.camera_base = (0, -2.5, 0)
    if col_v2.button("Vista Z+ (Alto)"):
        st.session_state.camera_base = (0, 0, 2.5)
        
    col_v3, col_v4 = st.sidebar.columns(2)
    if col_v3.button("Vista X+"):
        st.session_state.camera_base = (-2.5, 0, 0)
    if col_v4.button("Isometrica"):
        st.session_state.camera_base = (1.5, -1.5, 1.5)
        
    # Cursore di Zoom stabile
    st.session_state.zoom_level = st.sidebar.slider(
        "🔍 Livello Zoom", 
        min_value=0.2, 
        max_value=5.0, 
        value=st.session_state.zoom_level, 
        step=0.1
    )
        
    proj_mode = st.sidebar.radio("Proiezione", ["Ortogonale", "Prospettica"], 
                                 index=0 if st.session_state.proj_type == 'orthographic' else 1,
                                 horizontal=True)
    st.session_state.proj_type = 'orthographic' if proj_mode == "Ortogonale" else 'perspective'

    # --- FRAMMENTO PRINCIPALE ---
    @st.fragment
    def render_simulation():
        max_p = len(st.session_state.parsed_points) - 1
        
        st.markdown("---")
        st.subheader("🕹️ Controlli di Movimento")
        
        # Pulsanti Step-by-Step
        col_b1, col_b2, col_b3 = st.columns(3)
        if col_b1.button("◀ Step Indietro"):
            st.session_state.is_animating = False
            if st.session_state.sim_idx > 0:
                st.session_state.sim_idx -= 1
            else:
                st.session_state.sim_idx = max_p
                
        if col_b2.button("Step Avanti ▶"):
            st.session_state.is_animating = False
            if st.session_state.sim_idx < max_p:
                st.session_state.sim_idx += 1
            else:
                st.session_state.sim_idx = 0

        if col_b3.button("⏮ Riavvolgi"):
            st.session_state.is_animating = False
            st.session_state.sim_idx = 0

        # Pulsanti Start e Pausa
        col_p1, col_p2 = st.columns(2)
        if col_p1.button("▶ Avvia"):
            if st.session_state.sim_idx >= max_p:
                st.session_state.sim_idx = 0
            st.session_state.is_animating = True
        if col_p2.button("⏸ Pausa"):
            st.session_state.is_animating = False

        # Cursore di simulazione
        sim_idx = st.slider(
            "Cursore Simulazione Percorso", 
            0, max_p, 
            st.session_state.sim_idx
        )
        if sim_idx != st.session_state.sim_idx:
            st.session_state.is_animating = False
            st.session_state.sim_idx = sim_idx
        
        p_act = st.session_state.parsed_points[st.session_state.sim_idx]
        x_act, y_act, z_act, b_act = p_act['X'], p_act['Y'], p_act['Z'], p_act['B']
        
        # Riquadro Coordinate compatte
        st.info(f"**Coordinate WCS** ➔ X: {x_act:.3f} mm | Y: {y_act:.3f} mm | Z: {z_act:.3f} mm | B: {b_act:.3f}°")

        # Calcolo dinamico della telecamera applicando il fattore di zoom stabile
        bx, by, bz = st.session_state.camera_base
        z_factor = st.session_state.zoom_level
        current_eye = dict(x=bx * z_factor, y=by * z_factor, z=bz * z_factor)

        # Estrazione coordinate assolute per il percorso fisso
        sim_idx = st.session_state.sim_idx
        xs = [p['X'] for p in st.session_state.parsed_points]
        ys = [p['Y'] for p in st.session_state.parsed_points]
        zs = [p['Z'] for p in st.session_state.parsed_points]
        
        point_colors = []
        for i in range(len(st.session_state.parsed_points)):
            if i < sim_idx:
                point_colors.append('green')  # Già passato
            elif i == sim_idx:
                point_colors.append('red')    # In contatto / Attivo
            else:
                point_colors.append('blue')   # Futuro
                
        # Creazione grafico interattivo con Plotly
        fig = go.Figure()

        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode='lines',
            line=dict(color='gray', width=2, dash='dash'),
            name='Percorso'
        ))

        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode='markers+text',
            marker=dict(size=4, color=point_colors),
            text=[str(i) for i in range(len(xs))],
            textposition="top center",
            textfont=dict(size=8, color='navy'),
            name='Punti'
        ))

        fig.add_trace(go.Scatter3d(
            x=[x_act], y=[y_act], z=[z_act],
            mode='markers',
            marker=dict(size=10, color='red', symbol='diamond'),
            name='Posizione Utensile'
        ))

        fig.update_layout(
            title=dict(text=f"Simulazione - Punto: {sim_idx} (B: {b_act:.2f}°)", font=dict(size=13)),
            scene=dict(
                xaxis_title='X',
                yaxis_title='Y',
                zaxis_title='Z',
                aspectmode='data',
                camera=dict(
                    eye=current_eye,
                    projection=dict(type=st.session_state.proj_type)
                )
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            height=400
        )

        config_mobile = {
            'scrollZoom': True,
            'displayModeBar': 'hover',
            'responsive': True
        }

        st.plotly_chart(fig, use_container_width=True, config=config_mobile)
        
        # --- Visualizzatore Codice SPF pulito ---
        st.subheader("📜 Visualizzatore Codice SPF")
        
        active_line_idx = p_act['line_index']
        
        code_html = """
        <div id='code-container' style='height: 180px; overflow-y: scroll; background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 5px; padding: 8px; font-family: monospace; font-size: 12px;'>
        """
        
        for idx, line in enumerate(st.session_state.lines):
            clean_line = line.strip()
            if idx == active_line_idx:
                code_html += f"<div id='active-line' style='background-color: #ffeb3b; color: #000; font-weight: bold; padding: 2px 4px; margin: 1px 0; border-left: 3px solid #ff9800;'>&rarr; {clean_line}</div>"
            else:
                code_html += f"<div style='color: #495057; padding: 2px 4px; margin: 1px 0;'>&nbsp;&nbsp;&nbsp;&nbsp;{clean_line}</div>"
                
        code_html += """
        </div>
        <script>
            const activeLine = document.getElementById('active-line');
            if (activeLine) {
                activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        </script>
        """
        st.markdown(code_html, unsafe_allow_html=True)
        
        # Gestione ciclo di animazione automatica
        if st.session_state.is_animating:
            if st.session_state.sim_idx < max_p:
                st.session_state.sim_idx += 1
                time.sleep(0.05)
                st.rerun()
            else:
                st.session_state.is_animating = False

    render_simulation()
    
else:
    st.info("👈 Per iniziare, carica un file SPF dal pannello di sinistra.")

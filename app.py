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
    max_p = len(st.session_state.parsed_points) - 1
    
    st.sidebar.markdown("---")
    st.sidebar.header("🕹️ Controlli di Movimento")
    
    # Pulsanti Step-by-Step
    col_b1, col_b2 = st.sidebar.columns(2)
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

    if st.sidebar.button("⏮ Riavvolgi a Inizio"):
        st.session_state.is_animating = False
        st.session_state.sim_idx = 0

    # Pulsanti Start e Pausa
    col_p1, col_p2 = st.sidebar.columns(2)
    if col_p1.button("▶ Avvia"):
        if st.session_state.sim_idx >= max_p:
            st.session_state.sim_idx = 0
        st.session_state.is_animating = True
    if col_p2.button("⏸ Pausa"):
        st.session_state.is_animating = False

    # Cursore di simulazione
    sim_idx = st.sidebar.slider(
        "Cursore Simulazione Percorso", 
        0, max_p, 
        st.session_state.sim_idx
    )
    if sim_idx != st.session_state.sim_idx:
        st.session_state.is_animating = False
        st.session_state.sim_idx = sim_idx
    
    p_act = st.session_state.parsed_points[st.session_state.sim_idx]
    x_act, y_act, z_act, b_act = p_act['X'], p_act['Y'], p_act['Z'], p_act['B']
    
    # Riquadro Coordinate Assolute
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 Coordinate WCS (Pezzo Fermo)")
    st.sidebar.info(f"**X:** {x_act:.3f} mm\n\n**Y:** {y_act:.3f} mm\n\n**Z:** {z_act:.3f} mm\n\n**B:** {b_act:.3f}°")

# --- LAYOUT PRINCIPALE: Grafico 3D Sopra, Codice Sotto ---
col_main = st.container()

with col_main:
    if st.session_state.parsed_points:
        sim_idx = st.session_state.sim_idx
        p_act = st.session_state.parsed_points[sim_idx]
        x_act, y_act, z_act, b_act = p_act['X'], p_act['Y'], p_act['Z'], p_act['B']
        
        # Trasformazione cinematica inversa (Utensile Fisso, Path Movente)
        b_rad = np.radians(b_act)
        cos_b = np.cos(-b_rad)
        sin_b = np.sin(-b_rad)
        
        trans_xs, trans_ys, trans_zs = [], [], []
        point_colors = []
        
        for i, p in enumerate(st.session_state.parsed_points):
            dx = p['X'] - x_act
            dy = p['Y'] - y_act
            dz = p['Z'] - z_act
            
            xr = dx * cos_b + dz * sin_b
            yr = dy
            zr = -dx * sin_b + dz * cos_b
            
            trans_xs.append(xr)
            trans_ys.append(yr)
            trans_zs.append(zr)
            
            if i < sim_idx:
                point_colors.append('green')  # Già passato
            elif i == sim_idx:
                point_colors.append('red')    # In contatto / Attivo
            else:
                point_colors.append('blue')   # Futuro
                
        # Creazione grafico interattivo con Plotly
        fig = go.Figure()

        # Linea del percorso
        fig.add_trace(go.Scatter3d(
            x=trans_xs, y=trans_ys, z=trans_zs,
            mode='lines',
            line=dict(color='gray', width=2, dash='dash'),
            name='Percorso'
        ))

        # Punti del percorso con colori specifici
        fig.add_trace(go.Scatter3d(
            x=trans_xs, y=trans_ys, z=trans_zs,
            mode='markers+text',
            marker=dict(size=4, color=point_colors),
            text=[str(i) for i in range(len(trans_xs))],
            textposition="top center",
            textfont=dict(size=8, color='navy'),
            name='Punti'
        ))

        # Utensile fisso all'origine (0,0,0)
        fig.add_trace(go.Scatter3d(
            x=[0.0], y=[0.0], z=[0.0],
            mode='markers',
            marker=dict(size=8, color='red', symbol='diamond'),
            name='Utensile Fisso (Z+)'
        ))

        # Impostazioni di layout con aspectmode='data'
        fig.update_layout(
            title=dict(text=f"Simulazione Utensile Fisso - Punto Attivo: {sim_idx} (B: {b_act:.2f}°)", font=dict(size=14)),
            scene=dict(
                xaxis_title='Asse X (mm)',
                yaxis_title='Asse Y (mm)',
                zaxis_title='Asse Z (mm)',
                aspectmode='data',  # Corretto per Plotly
                camera=dict(
                    eye=dict(x=0, y=-2.5, z=0)  # Vista di default iniziale orientata su Y+
                )
            ),
            margin=dict(l=0, r=0, b=0, t=40),
            height=600
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # --- Visualizzatore Codice SPF in basso con evidenziazione attiva ---
        st.subheader("📜 Visualizzatore Codice SPF")
        
        active_line_idx = p_act['line_index']
        
        code_html = """
        <div style='height: 250px; overflow-y: scroll; background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 5px; padding: 10px; font-family: monospace; font-size: 13px;'>
        """
        
        for idx, line in enumerate(st.session_state.lines):
            clean_line = line.strip()
            if idx == active_line_idx:
                code_html += f"<div style='background-color: #ffeb3b; color: #000; font-weight: bold; padding: 3px 6px; margin: 2px 0; border-left: 4px solid #ff9800;'>&rarr; [Riga {idx+1}] {clean_line}</div>"
            else:
                code_html += f"<div style='color: #495057; padding: 2px 6px; margin: 2px 0;'>&nbsp;&nbsp;&nbsp;&nbsp;[Riga {idx+1}] {clean_line}</div>"
                
        code_html += "</div>"
        st.markdown(code_html, unsafe_allow_html=True)
        
        # Gestione ciclo di animazione automatica (Start / Pause)
        if st.session_state.is_animating:
            if st.session_state.sim_idx < max_p:
                st.session_state.sim_idx += 1
                time.sleep(0.08)
                st.rerun()
            else:
                st.session_state.is_animating = False
        
    else:
        st.info("👈 Per iniziare, carica un file SPF dal pannello di sinistra.")

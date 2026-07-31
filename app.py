import re
import time
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

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
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection='3d')
        
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
                
        # Disegno punti e percorso
        ax.scatter(trans_xs, trans_ys, trans_zs, c=point_colors, s=15)
        ax.plot(trans_xs, trans_ys, trans_zs, color='gray', linestyle='--', alpha=0.5)
        
        # Numerazione punti
        for i, (xr, yr, zr) in enumerate(zip(trans_xs, trans_ys, trans_zs)):
            ax.text(xr, yr, zr, f" {i}", fontsize=6, color='navy')
            
        # Utensile fisso all'origine (0,0,0) puntato verso Z+
        h_len = 100.0
        r_tip, r_base = 0.1, 7.5
        h = np.linspace(0, h_len, 15)
        theta = np.linspace(0, 2 * np.pi, 15)
        H, Theta = np.meshgrid(h, theta)
        R = r_tip + (r_base - r_tip) * (H / h_len)
        X_loc = R * np.cos(Theta)
        Y_loc = R * np.sin(Theta)
        Z_loc = H
        
        ax.plot_surface(X_loc, Y_loc, Z_loc, color='cyan', alpha=0.4, edgecolor='teal', lw=0.1)
        ax.scatter([0.0], [0.0], [0.0], color='red', s=100, marker='o')

        ax.set_title(f"Simulazione Utensile Fisso - Punto Attivo: {sim_idx} (B: {b_act:.2f}°)")
        ax.set_xlabel("Asse X (mm)")
        ax.set_ylabel("Asse Y (mm)")
        ax.set_zlabel("Asse Z (mm)")
        
        # Impostazioni Vista e Proiezione Ortogonale Richieste
        ax.view_init(elev=0, azim=-90)
        try:
            ax.set_proj_type('ortho')
        except AttributeError:
            pass
        
        st.pyplot(fig)
        
        # --- Visualizzatore Codice SPF in basso ---
        st.subheader("📜 Visualizzatore Codice SPF")
        code_container = st.container(height=250)
        
        active_line_idx = p_act['line_index']
        code_lines_formatted = []
        
        for idx, line in enumerate(st.session_state.lines):
            clean_line = line.strip()
            if idx == active_line_idx:
                code_lines_formatted.append(f"➡️ **[RIGA {idx+1}]  {clean_line}**")
            else:
                code_lines_formatted.append(f"&nbsp;&nbsp;&nbsp;&nbsp;[Riga {idx+1}]  {clean_line}")
                
        code_text_display = "\n\n".join(code_lines_formatted)
        code_container.markdown(code_text_display, unsafe_allow_html=True)
        
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

import streamlit as st
import osmnx as ox
import networkx as nx
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Ottimizzatore Sud v4.2", page_icon="🚚")

# --- STILE E FIRMA ---
st.title("🚚 Sistema Logistico Puglia/Basilicata")
st.markdown("**Copyright © 2026 - Creato da VMMG**")
st.divider()

# --- CARICAMENTO MAPPA (SCARICAMENTO DIRETTO) ---
@st.cache_resource
def carica_mappa():
    try:
        # Se il file non c'è, lo scarichiamo direttamente dai server OpenStreetMap
        # Definiamo le regioni
        luoghi = ["Puglia, Italy", "Basilicata, Italy"]
        st.info("⌛ Scaricamento dati stradali in corso (solo al primo avvio)...")
        G = ox.graph_from_place(luoghi, network_type='drive', simplify=True)
        return G
    except Exception as e:
        st.error(f"❌ Errore durante lo scaricamento della mappa: {e}")
        return None

G = carica_mappa()

if G is None:
    st.error("❌ File 'mappa_sud.graphml' non trovato nel server!")
    st.stop()

# --- SIDEBAR: INSERIMENTO DATI ---
st.sidebar.header("📍 Inserimento Tappe")
if 'tappe' not in st.session_state:
    st.session_state.tappe = []

with st.sidebar.form("form_tappa", clear_on_submit=True):
    seriale = st.text_input("Seriale Cliente (es. Nome o Ordine)")
    coord_raw = st.text_input("Coordinate (lat, lon)")
    urgente = st.checkbox("Segna come URGENTE")
    submit = st.form_submit_button("Aggiungi Tappa")

    if submit and seriale and coord_raw:
        try:
            pulito = coord_raw.replace(" ", "").replace("(", "").replace(")", "")
            lat, lon = map(float, pulito.split(","))
            priorita = 1 if urgente else 2
            st.session_state.tappe.append({"seriale": seriale, "lat": lat, "lon": lon, "prio": priorita})
            st.success(f"Tappa {seriale} aggiunta!")
        except:
            st.error("Formato coordinate errato!")

if st.sidebar.button("🗑️ Svuota Lista"):
    st.session_state.tappe = []
    st.rerun()

# --- VISUALIZZAZIONE LISTA ---
if st.session_state.tappe:
    st.subheader("📋 Tappe Inserite")
    df_preview = pd.DataFrame(st.session_state.tappe)
    st.table(df_preview[['seriale', 'lat', 'lon', 'prio']])

    modalita = st.radio("Scegli modalità operativa:", ["Standard (Percorso breve)", "Urgenze (Priorità)"])
    
    if st.button("🚀 CALCOLA PERCORSO OTTIMALE"):
        # Logica di calcolo
        partenza_gps = (40.88662985769151, 16.852016478389977)
        nodo_partenza = ox.distance.nearest_nodes(G, partenza_gps[1], partenza_gps[0])
        ordine_finale = [(nodo_partenza, "MAGAZZINO")]
        km_totali = 0

        def trova_prossimo(lista_rimanenti, attuale):
            prossimo = min(lista_rimanenti, key=lambda n: nx.shortest_path_length(G, attuale, n[0], weight='length'))
            dist = nx.shortest_path_length(G, attuale, prossimo[0], weight='length')
            return prossimo, dist

        # Conversione tappe in nodi
        tappe_lavoro = st.session_state.tappe.copy()
        
        if "Urgenze" in modalita:
            urgenti = [(ox.distance.nearest_nodes(G, t['lon'], t['lat']), t['seriale']) for t in tappe_lavoro if t['prio'] == 1]
            standard = [(ox.distance.nearest_nodes(G, t['lon'], t['lat']), t['seriale']) for t in tappe_lavoro if t['prio'] == 2]
            
            for gruppo in [urgenti, standard]:
                while gruppo:
                    prossimo, d = trova_prossimo(gruppo, ordine_finale[-1][0])
                    km_totali += d
                    ordine_finale.append(prossimo)
                    gruppo.remove(prossimo)
        else:
            rimanenti = [(ox.distance.nearest_nodes(G, t['lon'], t['lat']), t['seriale']) for t in tappe_lavoro]
            while rimanenti:
                prossimo, d = trova_prossimo(rimanenti, ordine_finale[-1][0])
                km_totali += d
                ordine_finale.append(prossimo)
                rimanenti.remove(prossimo)

        # --- RISULTATI ---
        st.success(f"✅ Percorso Ottimizzato: {km_totali/1000:.2f} km totali")
        
        tabella_marcia = []
        for i, (nodo, ser) in enumerate(ordine_finale):
            lat, lon = G.nodes[nodo]['y'], G.nodes[nodo]['x']
            tipo = "PARTENZA" if i == 0 else "STOP"
            tabella_marcia.append({"Ordine": i, "Tipo": tipo, "Cliente": ser, "Lat": lat, "Lon": lon})
        
        st.dataframe(tabella_marcia, use_container_width=True)
        
        # Download risultati
        testo_export = "\n".join([f"{r['Ordine']}: {r['Cliente']} -> {r['Lat']}, {r['Lon']}" for r in tabella_marcia])
        st.download_button("📥 Scarica Tabella di Marcia", testo_export, file_name="percorso.txt")
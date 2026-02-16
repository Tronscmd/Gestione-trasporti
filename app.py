import streamlit as st
import osmnx as ox
import networkx as nx
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Ottimizzatore Sud v4.2", page_icon="🚚", layout="wide")

st.title("🚚 Sistema Logistico Puglia/Basilicata v4.2")
st.markdown("Copyright © 2026 - Creato da VMMG")
st.divider()

# --- CARICAMENTO MAPPA ---
@st.cache_resource
def carica_mappa():
    try:
        # Carichiamo il file da 96MB che hai appena creato
        return ox.load_graphml("mappa_sud_final.graphml")
    except Exception as e:
        st.error(f"❌ Errore nel caricamento mappa: {e}")
        return None

G = carica_mappa()

if G is None:
    st.info("Assicurati che il file 'mappa_sud_final.graphml' sia nella cartella principale di GitHub.")
    st.stop()

# --- GESTIONE STATO APPLICAZIONE ---
if 'tappe' not in st.session_state:
    st.session_state.tappe = []

# --- INTERFACCIA DI INSERIMENTO ---
st.sidebar.header("📍 Inserimento Clienti")
with st.sidebar.form("input_form", clear_on_submit=True):
    seriale = st.text_input("Seriale Cliente")
    coord_raw = st.text_input("Coordinate (lat, lon)")
    submit = st.form_submit_button("➕ Aggiungi Tappa")

    if submit:
        if seriale and coord_raw:
            try:
                pulito = coord_raw.replace(" ", "").replace("(", "").replace(")", "")
                lat, lon = map(float, pulito.split(","))
                st.session_state.tappe.append({"seriale": seriale, "lat": lat, "lon": lon, "urgente": False})
                st.success(f"Tappa {seriale} aggiunta!")
            except:
                st.error("Formato coordinate errato! Usa: lat, lon")
        else:
            st.warning("Inserisci sia seriale che coordinate.")

if st.sidebar.button("🗑️ Svuota tutto"):
    st.session_state.tappe = []
    st.rerun()

# --- VISUALIZZAZIONE E CALCOLO ---
if st.session_state.tappe:
    st.subheader("📋 Tabella Inserimenti")
    df = pd.DataFrame(st.session_state.tappe)
    
    # Selezione urgenze tramite checkbox nell'interfaccia
    urgenti_selezionati = st.multiselect(
        "Seleziona i clienti URGENTI:", 
        options=[t['seriale'] for t in st.session_state.tappe]
    )
    
    # Aggiorna lo stato di urgenza
    for t in st.session_state.tappe:
        t['urgente'] = t['seriale'] in urgenti_selezionati

    modalita = st.radio("Modalità Operativa:", ["Standard (Percorso Breve)", "Gestione URGENZE"])

    if st.button("🚀 CALCOLA PERCORSO OTTIMALE"):
        with st.spinner("Calcolo in corso..."):
            partenza_gps = (40.88662985769151, 16.852016478389977)
            nodo_partenza = ox.distance.nearest_nodes(G, partenza_gps[1], partenza_gps[0])
            
            ordine_finale = [(nodo_partenza, "MAGAZZINO")]
            km_totali = 0

            def trova_prossimo(lista_nodi, attuale):
                prossimo = min(lista_nodi, key=lambda n: nx.shortest_path_length(G, attuale, n[0], weight='length'))
                dist = nx.shortest_path_length(G, attuale, prossimo[0], weight='length')
                return prossimo, dist

            tappe_nodi = [(ox.distance.nearest_nodes(G, t['lon'], t['lat']), t['seriale'], t['urgente']) for t in st.session_state.tappe]

            if modalita == "Gestione URGENZE":
                urgenti = [(n, s) for n, s, u in tappe_nodi if u]
                standard = [(n, s) for n, s, u in tappe_nodi if not u]
                
                # Calcolo sequenziale: prima urgenze, poi standard
                attuale = nodo_partenza
                for gruppo in [urgenti, standard]:
                    while gruppo:
                        prossimo, d = trova_prossimo(gruppo, attuale)
                        km_totali += d
                        ordine_finale.append(prossimo)
                        gruppo.remove(prossimo)
                        attuale = prossimo[0]
            else:
                rimanenti = [(n, s) for n, s, u in tappe_nodi]
                attuale = nodo_partenza
                while rimanenti:
                    prossimo, d = trova_prossimo(rimanenti, attuale)
                    km_totali += d
                    ordine_finale.append(prossimo)
                    rimanenti.remove(prossimo)
                    attuale = prossimo[0]

            # --- OUTPUT RISULTATI ---
            st.divider()
            st.success(f"🏁 Calcolo Completato! Distanza totale stimata: **{km_totali/1000:.2f} km**")
            
            risultati = []
            for i, (nodo, ser) in enumerate(ordine_finale):
                lat, lon = G.nodes[nodo]['y'], G.nodes[nodo]['x']
                risultati.append({"Stop": i, "Tipo": "START" if i==0 else "STOP", "Cliente": ser, "Lat": lat, "Lon": lon})
            
            st.table(risultati)
            
            # Bottone per scaricare il file .txt
            testo_file = "PERCORSO OTTIMIZZATO\n\n" + "\n".join([f"STOP {r['Stop']} - {r['Cliente']} -> {r['Lat']}, {r['Lon']}" for r in risultati])
            st.download_button("📥 Scarica Tabella di Marcia", testo_file, file_name="percorso_oggi.txt")

else:
    st.info("Aggiungi i clienti dalla barra laterale per iniziare.")
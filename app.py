import streamlit as st
import os
import random
import pandas as pd

# --- KONFIGURACJA ---
AUDIO_DIR = "voice_clips"
VOTES_FILE = "votes_alfa.csv"
MANUAL_ELO_FILE = "manual_elo.csv"
INITIAL_RATING = 1500
ADMIN_PASSWORD = "admin"
GOAL_VOTES = 1500 

st.set_page_config(page_title="ALFA Vibe Ranker Pro", layout="wide")

# Tworzenie folderu jeśli nie istnieje
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

# --- FUNKCJE LOGICZNE ---
def calculate_elo(df_votes, files, dynamic_k=True):
    ratings = {f: INITIAL_RATING for f in files}
    counts = {f: 0 for f in files}
    
    if not df_votes.empty:
        for _, row in df_votes.iterrows():
            f_a, f_b = row['file_a'], row['file_b']
            if f_a in ratings and f_b in ratings:
                if dynamic_k:
                    k_a = 60 if counts[f_a] < 10 else (16 if counts[f_a] > 30 else 32)
                    k_b = 60 if counts[f_b] < 10 else (16 if counts[f_b] > 30 else 32)
                else:
                    k_a = k_b = 32

                r_a, r_b = ratings[f_a], ratings[f_b]
                e_a = 1 / (1 + 10 ** ((r_b - r_a) / 400))
                e_b = 1 / (1 + 10 ** ((r_a - r_b) / 400))
                
                s_a, s_b = (1, 0) if row['winner'] == 'A' else (0, 1) if row['winner'] == 'B' else (0.5, 0.5)
                
                ratings[f_a] += k_a * (s_a - e_a)
                ratings[f_b] += k_b * (s_b - e_b)
                counts[f_a] += 1
                counts[f_b] += 1
    
    if os.path.exists(MANUAL_ELO_FILE):
        manual_df = pd.read_csv(MANUAL_ELO_FILE)
        for _, row in manual_df.iterrows():
            if row['Plik'] in ratings:
                ratings[row['Plik']] = row['Elo']
    return ratings

def pick_new_pair_for_user(user_name):
    user_voted_pairs = set()
    if os.path.exists(VOTES_FILE):
        df = pd.read_csv(VOTES_FILE)
        if 'user' in df.columns:
            user_votes = df[df['user'] == user_name]
            for _, row in user_votes.iterrows():
                user_voted_pairs.add(tuple(sorted([row['file_a'], row['file_b']])))

    available_files = st.session_state.files
    all_possible_pairs = [(available_files[i], available_files[j]) 
                          for i in range(len(available_files)) 
                          for j in range(i + 1, len(available_files))]
    
    remaining_pairs = [p for p in all_possible_pairs if tuple(sorted(p)) not in user_voted_pairs]
    if not remaining_pairs: return None, 1.0
    progress = 1.0 - (len(remaining_pairs) / len(all_possible_pairs))
    return random.choice(remaining_pairs), progress

# --- INICJALIZACJA ---
st.session_state.files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav'))]

# --- NAWIGACJA ---
page = st.sidebar.radio("Nawigacja", ["Głosowanie", "Panel Administratora"])

# --- STRONA 1: GŁOSOWANIE ---
if page == "Głosowanie":
    if 'user_name' not in st.session_state:
        _, col_mid, _ = st.columns([1, 1.5, 1])
        with col_mid:
            st.title("🎙️ Badanie Alfa Vibe")
            with st.form("login_form"):
                u_input = st.text_input("Nick:", placeholder="Twoje imię")
                if st.form_submit_button("Zaloguj", use_container_width=True) and u_input.strip():
                    st.session_state.user_name = u_input.strip()
                    st.rerun()
        st.stop()

    pair, progress_val = pick_new_pair_for_user(st.session_state.user_name)
    st.title(f"Głosuje: {st.session_state.user_name}")
    st.progress(progress_val)
    
    if pair is None:
        st.success("Wszystkie pary ocenione!")
    else:
        f_a, f_b = pair
        c1, c2 = st.columns(2)
        with c1:
            st.audio(os.path.join(AUDIO_DIR, f_a))
            if st.button("Wybierz A", use_container_width=True):
                pd.DataFrame([[st.session_state.user_name, f_a, f_b, 'A']], columns=['user','file_a','file_b','winner']).to_csv(VOTES_FILE, mode='a', header=not os.path.exists(VOTES_FILE), index=False)
                st.rerun()
        with c2:
            st.audio(os.path.join(AUDIO_DIR, f_b))
            if st.button("Wybierz B", use_container_width=True):
                pd.DataFrame([[st.session_state.user_name, f_a, f_b, 'B']], columns=['user','file_a','file_b','winner']).to_csv(VOTES_FILE, mode='a', header=not os.path.exists(VOTES_FILE), index=False)
                st.rerun()
        
        st.divider()
        if st.button("⚖️ Remis", use_container_width=True):
            pd.DataFrame([[st.session_state.user_name, f_a, f_b, 'EQUAL']], columns=['user','file_a','file_b','winner']).to_csv(VOTES_FILE, mode='a', header=not os.path.exists(VOTES_FILE), index=False)
            st.rerun()

# --- STRONA 2: PANEL ADMINISTRATORA ---
elif page == "Panel Administratora":
    st.title("🔒 Panel Administratora")
    pwd = st.sidebar.text_input("Hasło:", type="password")
    
    if pwd == ADMIN_PASSWORD:
        df_votes = pd.read_csv(VOTES_FILE) if os.path.exists(VOTES_FILE) else pd.DataFrame()
        
        # Pasek AI na górze
        num_votes = len(df_votes)
        st.write(f"**Baza AI:** {num_votes} / {GOAL_VOTES} głosów")
        st.progress(min(num_votes / GOAL_VOTES, 1.0))

        # Konfiguracja w Sidebarze Admina
        st.sidebar.divider()
        use_dyn_k = st.sidebar.checkbox("🚀 Dynamiczne K", value=True)
        edit_mode = st.sidebar.toggle("🛠️ Edycja Punktów")
        
        current_ratings = calculate_elo(df_votes, st.session_state.files, dynamic_k=use_dyn_k)
        ranking_df = pd.DataFrame([{"Plik": n, "Elo": int(e)} for n, e in current_ratings.items()]).sort_values("Elo", ascending=False).reset_index(drop=True)

        # Ranking Tabela
        if edit_mode:
            edited = st.data_editor(ranking_df, use_container_width=True)
            if st.button("Zapisz zmiany w Elo"):
                edited.to_csv(MANUAL_ELO_FILE, index=False)
                st.rerun()
        else:
            st.dataframe(ranking_df, use_container_width=True, height=300)

        # ZWIĘZŁA LISTA ODSŁUCHU I USUWANIA
        st.subheader("📋 Zarządzanie Nagraniami")
        
        for i, row in ranking_df.iterrows():
            # Kompaktowy wiersz: Pozycja | Odtwarzacz | Nazwa i Elo | Przycisk Usuń
            c_pos, c_aud, c_txt, c_del = st.columns([0.5, 3, 4, 1])
            
            c_pos.write(f"#{i+1}")
            c_aud.audio(os.path.join(AUDIO_DIR, row['Plik']))
            c_txt.markdown(f"**{row['Plik']}** \n`Elo: {row['Elo']}`")
            
            if c_del.button("🗑️", key=f"del_{row['Plik']}", help=f"Usuń {row['Plik']} na stałe"):
                try:
                    os.remove(os.path.join(AUDIO_DIR, row['Plik']))
                    st.toast(f"Usunięto: {row['Plik']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd: {e}")
            st.divider()

        st.sidebar.download_button("📥 Pobierz Wyniki", ranking_df.to_csv(index=False), "wyniki.csv")
    elif pwd != "":
        st.error("Błędne hasło!")
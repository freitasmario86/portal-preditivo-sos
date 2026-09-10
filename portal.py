import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import pypdf
import re
import gdown
from io import BytesIO
import plotly.express as px
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO E CONEXÃO COM O BANCO BANCO SQLITE LOCAL
# ==============================================================================
st.set_page_config(
    page_title="Portal Preditivo e Preventivo - S•O•S",
    page_icon="🚜",
    layout="wide"
)

DB_FILE = "sos_preditiva.db"

def init_db():
    """Cria as tabelas no banco de dados SQLite interno se não existirem"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS laudos (
            controle_lab TEXT PRIMARY KEY,
            data_coleta TEXT, cliente TEXT, modelo TEXT, frota TEXT,
            compartimento TEXT, status TEXT, hr_equip REAL, hr_oleo REAL,
            cu REAL, fe REAL, cr REAL, al REAL, pb REAL, sn REAL, si REAL,
            na REAL, k REAL, b REAL, mo REAL, ni REAL, ag REAL, ti REAL,
            v REAL, mn REAL, ca REAL, mg REAL, zn REAL, p REAL, ba REAL,
            v100 REAL, h2o REAL, iso_4u REAL, iso_6u REAL, iso_14u REAL,
            nome_arquivo TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@st.cache_data(ttl=3600)
def carregar_dados_db_rapido():
    """Leitura em milissegundos direta da memória/banco local"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM laudos", conn)
    conn.close()
    return df

df_base = carregar_dados_db_rapido()

# ==============================================================================
# FUNÇÃO DE EXTRAÇÃO DE PDF
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    mod_file = re.search(r'6612254_([A-Z0-9]+)#', filename)
    modelo = mod_file.group(1) if mod_file else "Geral"

    frota_file = re.search(r'#([A-Z0-9]+)_', filename)
    frota = frota_file.group(1) if frota_file else "Desconhecido"

    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else f"TEMP_{filename}"

    mapa_comp = {
        'FD_LT': 'COMANDO F ESQ', 'FD_RT': 'COMANDO F DIR', 'SW_DR': 'COMANDO GIRO',
        'ENG': 'MOTOR', 'HS': 'SISTEMA HIDRAULICO', 'DIFF_FR': 'DIFERENCIAL DIANT',
        'TR': 'TRANSMISSAO', 'RA': 'RADIADOR', 'AX_CE': 'EIXO CENTRAL', 'AX_RR': 'EIXO TRASEIRO'
    }
    compartimento = "Outros"
    for k, v in mapa_comp.items():
        if f"_{k}_" in filename.upper():
            compartimento = v
            break

    status = "Normal"
    if "_AR.PDF" in filename.upper() or "CRÍTICO" in texto.upper():
        status = "Crítico"
    elif "_MC.PDF" in filename.upper() or "MONITORAR" in texto.upper():
        status = "Monitorar"

    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)
    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    elementos = {
        "cu": 0.0, "fe": 0.0, "cr": 0.0, "al": 0.0, "pb": 0.0, "sn": 0.0, "si": 0.0,
        "na": 0.0, "k": 0.0, "b": 0.0, "mo": 0.0, "ni": 0.0, "ag": 0.0, "ti": 0.0,
        "v": 0.0, "mn": 0.0, "ca": 0.0, "mg": 0.0, "zn": 0.0, "p": 0.0, "ba": 0.0,
        "v100": 0.0, "h2o": 0.0, "iso_4u": 0.0, "iso_6u": 0.0, "iso_14u": 0.0
    }

    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if controle in linha:
            bloco_texto = " ".join(linhas[i:i+3])
            nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_texto)]
            if len(nums) >= 20:
                if nums[0] > 50000: nums = nums[1:]
                keys_elem = ["cu", "fe", "cr", "al", "pb", "sn", "si", "na", "k", "b", "mo", "ni", "ag", "ti", "v", "mn", "ca", "mg", "zn", "p", "ba"]
                for idx, k in enumerate(keys_elem):
                    if idx < len(nums): elementos[k] = nums[idx]

    match_v100 = re.search(r'(\d{2}\.\d{2})', texto)
    if match_v100: elementos["v100"] = float(match_v100.group(1))

    match_h2o = re.search(r'(\d\.\d{2,4})', texto)
    if match_h2o: elementos["h2o"] = float(match_h2o.group(1))

    iso_m = re.search(r'(\d{2})\/(\d{2})\/(\d{2})', texto)
    if iso_m:
        elementos["iso_4u"] = float(iso_m.group(1))
        elementos["iso_6u"] = float(iso_m.group(2))
        elementos["iso_14u"] = float(iso_m.group(3))

    dados = (
        controle, data_coleta, "3 SKAVAMINAS", modelo, frota, compartimento, status, hr_equip, hr_oleo,
        elementos["cu"], elementos["fe"], elementos["cr"], elementos["al"], elementos["pb"], elementos["sn"], elementos["si"],
        elementos["na"], elementos["k"], elementos["b"], elementos["mo"], elementos["ni"], elementos["ag"], elementos["ti"],
        elementos["v"], elementos["mn"], elementos["ca"], elementos["mg"], elementos["zn"], elementos["p"], elementos["ba"],
        elementos["v100"], elementos["h2o"], elementos["iso_4u"], elementos["iso_6u"], elementos["iso_14u"], filename
    )
    return dados

def salvar_no_banco(registros):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.executemany('''
        INSERT OR REPLACE INTO laudos VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    ''', registros)
    conn.commit()
    conn.close()
    st.cache_data.clear()

# ==============================================================================
# MENU E FILTROS
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

opcao_menu = st.sidebar.radio(
    "Navegação:",
    ["📊 Dashboard de Consultas", "⚡ Ingestão Rápida de Laudos (PDF)"]
)

# ==============================================================================
# TELA DE CONSULTA INSTANTÂNEA
# ==============================================================================
if opcao_menu == "📊 Dashboard de Consultas":
    st.title("🚜 Dashboard Preditivo - Consulta Instantânea")
    
    if df_base.empty:
        st.info("O banco de dados local está vazio. Acesse a aba 'Ingestão Rápida de Laudos' para carregar a base initial.")
    else:
        st.success(f"⚡ Base carregada instantaneamente! Total de laudos em memória: {len(df_base)}")
        
        f1, f2, f3 = st.columns(3)
        f_frota = f1.selectbox("Frota:", ["Todas"] + list(df_base["frota"].unique()))
        f_comp = f2.selectbox("Compartimento:", ["Todos"] + list(df_base["compartimento"].unique()))
        f_status = f3.selectbox("Status:", ["Todos"] + list(df_base["status"].unique()))

        df_view = df_base.copy()
        if f_frota != "Todas": df_view = df_view[df_view["frota"] == f_frota]
        if f_comp != "Todos": df_view = df_view[df_view["compartimento"] == f_comp]
        if f_status != "Todos": df_view = df_view[df_view["status"] == f_status]

        st.dataframe(df_view, use_container_width=True)

# ==============================================================================
# TELA DE PROCESSAMENTO
# ==============================================================================
elif opcao_menu == "⚡ Ingestão Rápida de Laudos (PDF)":
    st.title("⚡ Processamento Incremental de PDFs")
    
    st.subheader("1. Upload de Arquivos em Lote (Recomendado - Instantâneo)")
    uploaded_files = st.file_uploader("Arraste os arquivos PDF aqui para salvar no banco SQLite:", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 Processar e Gravar no Banco Local", type="primary"):
            novos_regs = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                dados = extrair_dados_pdf_fidedigno(BytesIO(pdf.read()), pdf.name)
                novos_regs.append(dados)
                bar.progress((idx + 1) / len(uploaded_files))
            
            salvar_no_banco(novos_regs)
            st.success("✅ Laudos gravados com sucesso no banco de alta velocidade!")
            st.rerun()

    st.markdown("---")
    st.subheader("2. Sincronização Incremental por Pasta do Google Drive")
    folder_id_input = st.text_input("ID da Pasta no Google Drive:", value="19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw")
    
    if st.button("🔄 SINCRONIZAR SOMENTE ARQUIVOS NOVOS"):
        with st.spinner("Rastreando apenas laudos inéditos..."):
            try:
                files = gdown.download_folder(f"https://drive.google.com/drive/folders/{folder_id_input}", quiet=True, use_cookies=False)
                novos_regs = []
                
                # Pega os laudos já processados no banco
                laudos_existentes = set(df_base["nome_arquivo"].tolist()) if not df_base.empty else set()
                
                if files:
                    for f_path in files:
                        filename = f_path.replace("\\", "/").split("/")[-1]
                        # Filtra e pula o arquivo se ele já existir no banco SQLite
                        if f_path.lower().endswith('.pdf') and filename not in laudos_existentes:
                            with open(f_path, 'rb') as f:
                                novos_regs.append(extrair_dados_pdf_fidedigno(BytesIO(f.read()), filename))
                
                if novos_regs:
                    salvar_no_banco(novos_regs)
                    st.success(f"✅ Sincronização concluída! {len(novos_regs)} laudos inéditos adicionados ao banco local!")
                else:
                    st.info("A base já está 100% atualizada! Nenhum laudo novo foi encontrado.")
            except Exception as e:
                st.error(f"Erro na sincronização: {e}")

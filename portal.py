import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Portal Preditivo e Preventivo - S•O•S",
    page_icon="🚜",
    layout="wide"
)

# ID da sua pasta fornecida no Google Drive
FOLDER_ID_DRIVE = "19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1hnntl9LfTqvPabewBU3PnNuZezREWi-3A5lmUM9GEwY/edit"

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA)
        df = df.dropna(how="all")
        cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "V100", "H2O"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados()

df_base = st.session_state.df_base

# ==============================================================================
# EXTRAÇÃO COMPLETA DE DADOS DO PDF
# ==============================================================================
def extrair_dados_pdf(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    modelo_m = re.search(r'_([A-Z0-9]+)#', filename)
    frota_m = re.search(r'#([A-Z0-9]+)_', filename)
    ctrl_m = re.search(r'_(U\d{3}-\d{5}-\d{4})', filename)

    modelo = modelo_m.group(1) if modelo_m else "Geral"
    frota = frota_m.group(1) if frota_m else "Desconhecido"
    controle = ctrl_m.group(1) if ctrl_m else "Desconhecido"

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
    if "_AR.PDF" in filename.upper() or "_CR.PDF" in filename.upper():
        status = "Crítico"
    elif "_MC.PDF" in filename.upper():
        status = "Monitorar"

    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)
    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    def extrair_valor_campo(padrao, text):
        m = re.search(padrao, text)
        return float(m.group(1).replace(',', '.')) if m else 0.0

    cu = extrair_valor_campo(r'Cu\s*(\d+)', texto)
    fe = extrair_valor_campo(r'Fe\s*(\d+)', texto)
    cr = extrair_valor_campo(r'Cr\s*(\d+)', texto)
    al = extrair_valor_campo(r'Al\s*(\d+)', texto)
    si = extrair_valor_campo(r'Si\s*(\d+)', texto)
    v100 = extrair_valor_campo(r'V100\s*(\d+[\.,]?\d*)', texto)
    h2o = extrair_valor_campo(r'H2O\s*(\d+[\.,]?\d*)', texto)

    return {
        "Data da Coleta": data_coleta,
        "Cliente": "3 SKAVAMINAS",
        "Modelo": modelo,
        "Frota": frota,
        "Compartimento": compartimento,
        "Status": status,
        "Horímetro Equip": hr_equip,
        "Horímetro Óleo": hr_oleo,
        "Cu": cu, "Fe": fe, "Cr": cr, "Al": al, "Si": si, "V100": v100, "H2O": h2o,
        "Nº Controle Lab": controle,
        "Nome do Arquivo PDF": filename
    }

# ==============================================================================
# CONEXÃO COM A PASTA DO GOOGLE DRIVE
# ==============================================================================
def buscar_pdfs_da_pasta_drive(folder_id):
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=creds)

        query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        arquivos = results.get('files', [])

        dados_extraidos = []
        for file in arquivos:
            file_id = file['id']
            file_name = file['name']

            request = service.files().get_media(fileId=file_id)
            file_bytes = BytesIO()
            downloader = MediaIoBaseDownload(file_bytes, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            file_bytes.seek(0)
            dados = extrair_dados_pdf(file_bytes, file_name)
            dados_extraidos.append(dados)

        return pd.DataFrame(dados_extraidos)
    except Exception as e:
        st.error(f"Erro de autenticação no Google Drive Secrets: {e}")
        return pd.DataFrame()

# ==============================================================================
# FILTROS
# ==============================================================================
st.sidebar.title("🛠️ Filtros do Portal")

empresas = ["Todas"] + list(df_base["Cliente"].unique()) if "Cliente" in df_base.columns and not df_base.empty else ["Todas"]
f_empresa = st.sidebar.selectbox("Empresa / Cliente:", empresas)

modelos = ["Todos"] + list(df_base["Modelo"].unique()) if "Modelo" in df_base.columns and not df_base.empty else ["Todos"]
f_modelo = st.sidebar.selectbox("Modelo de Equipamento:", modelos)

frotas = ["Todas"] + list(df_base["Frota"].unique()) if "Frota" in df_base.columns and not df_base.empty else ["Todas"]
f_frota = st.sidebar.selectbox("Número de Frota:", frotas)

comps = ["Todos"] + list(df_base["Compartimento"].unique()) if "Compartimento" in df_base.columns and not df_base.empty else ["Todos"]
f_comp = st.sidebar.selectbox("Compartimento Analisado:", comps)

df_filtrado = df_base.copy()
if not df_filtrado.empty:
    if f_empresa != "Todas": df_filtrado = df_filtrado[df_filtrado["Cliente"] == f_empresa]
    if f_modelo != "Todos": df_filtrado = df_filtrado[df_filtrado["Modelo"] == f_modelo]
    if f_frota != "Todas": df_filtrado = df_filtrado[df_filtrado["Frota"] == f_frota]
    if f_comp != "Todos": df_filtrado = df_filtrado[df_filtrado["Compartimento"] == f_comp]

st.sidebar.markdown("---")
opcao_menu = st.sidebar.radio(
    "Módulos:",
    [
        "📊 Dashboard Geral", 
        "🧪 Elementos de Desgaste & Condição",
        "🚨 Pior Ativo (Bad Actors) & MTBF", 
        "📈 Tendência & Intervalo de Amostragem", 
        "🔬 Distribuição Estatística (Sigma)", 
        "📉 Sobrevivência (Weibull & Risco)", 
        "🔍 Causa Raiz (RCA)", 
        "📥 Importar Laudos (Drive & PDF)"
    ]
)

# ==============================================================================
# MODULOS
# ==============================================================================
if opcao_menu == "📊 Dashboard Geral":
    st.title("🚜 Dashboard Proativo e Preventivo")
    if not df_filtrado.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total de Amostras", len(df_filtrado))
        k2.metric("Críticos", len(df_filtrado[df_filtrado["Status"] == "Crítico"]))
        k3.metric("Monitorar", len(df_filtrado[df_filtrado["Status"] == "Monitorar"]))
        k4.metric("Normais", len(df_filtrado[df_filtrado["Status"] == "Normal"]))

        col1, col2 = st.columns(2)
        with col1:
            fig_status = px.bar(df_filtrado["Status"].value_counts().reset_index(), x='Status', y='count',
                                title="Distribuição de Criticidade", text_auto=True, color='Status')
            st.plotly_chart(fig_status, use_container_width=True)
        with col2:
            fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento", hole=0.4)
            fig_comp.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_comp, use_container_width=True)

elif opcao_menu == "🧪 Elementos de Desgaste & Condição":
    st.title("🧪 Monitoramento de Elementos Químicos & Condição do Óleo")
    if not df_filtrado.empty:
        fig_elem = px.bar(
            df_filtrado, x="Frota", y=["Fe", "Cu", "Si", "Al", "Cr"],
            title="Concentração de Metais de Desgaste por Frota (ppm)",
            barmode="group", text_auto=True
        )
        st.plotly_chart(fig_elem, use_container_width=True)

elif opcao_menu == "🚨 Pior Ativo (Bad Actors) & MTBF":
    st.title("🚨 Ranking de Piores Ativos (Bad Actors) & Confiabilidade")
    if not df_filtrado.empty:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            st.plotly_chart(fig_bad, use_container_width=True)

elif opcao_menu == "📈 Tendência & Intervalo de Amostragem":
    st.title("📈 Análise de Tendência e Delta de Horímetro")
    if not df_filtrado.empty:
        df_ord = df_filtrado.sort_values(by=["Frota", "Compartimento", "Horímetro Equip"])
        df_ord["Intervalo Amostra (Δ Horímetro)"] = df_ord.groupby(["Frota", "Compartimento"])["Horímetro Equip"].diff().fillna(0)

        fig_tend = px.line(df_ord, x="Horímetro Equip", y="Horímetro Óleo", color="Frota", markers=True, text="Horímetro Óleo")
        fig_tend.update_traces(textposition="top center")
        st.plotly_chart(fig_tend, use_container_width=True)

elif opcao_menu == "🔬 Distribuição Estatística (Sigma)":
    st.title("🔬 Análise Estatística (Distribuição Normal e Sigmas)")
    if not df_filtrado.empty:
        media = df_filtrado["Horímetro Óleo"].mean()
        std = df_filtrado["Horímetro Óleo"].std()
        if pd.isna(std) or std == 0: std = 1

        fig_hist = px.histogram(df_filtrado, x="Horímetro Óleo", nbins=15, marginal="box", text_auto=True)
        fig_hist.add_vline(x=media, line_dash="dash", line_color="green", annotation_text=f"Média: {media:.0f}h")
        st.plotly_chart(fig_hist, use_container_width=True)

elif opcao_menu == "📉 Sobrevivência (Weibull & Risco)":
    st.title("📉 Curva de Sobrevivência (Weibull) & Análise de Risco")
    if not df_filtrado.empty:
        s_horas = pd.to_numeric(df_filtrado["Horímetro Óleo"], errors='coerce').dropna()
        horas = np.sort(s_horas[s_horas > 0].values)

        if len(horas) > 2:
            n = len(horas)
            p = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
            y = np.log(-np.log(1 - p))
            x = np.log(horas)

            fit = np.polyfit(x, y, 1)
            beta = fit[0]
            eta = np.exp(-fit[1] / beta)

            df_weibull = pd.DataFrame({"Horímetro Óleo": horas, "Confiabilidade R(t)": np.exp(-(horas / eta)**beta)})
            fig_w = px.line(df_weibull, x="Horímetro Óleo", y="Confiabilidade R(t)", markers=True)
            st.plotly_chart(fig_w, use_container_width=True)

elif opcao_menu == "🔍 Causa Raiz (RCA)":
    st.title("🔍 Análise de Causa Raiz (RCA) - Matriz de Diagnóstico")
    rca_matrix = pd.DataFrame([
        {"Sintoma / Elemento": "Alta de Silício (Si) + Alumínio (Al)", "Causa Provável": "Entrada de poeira / sujeira externa", "Ação Tática / Operacional": "Inspecionar vedação do filtro de ar, dutos de admissão e respiros."},
        {"Sintoma / Elemento": "Alta de Ferro (Fe) + Cromo (Cr)", "Causa Provável": "Desgaste de camisas, anéis ou engrenagens", "Ação Tática / Operacional": "Programar boroscopia do compartimento e verificar ruídos."}
    ])
    st.table(rca_matrix)

# ==============================================================================
# IMPORTAÇÃO / SINCRONIZAÇÃO DA PASTA DO DRIVE
# ==============================================================================
elif opcao_menu == "📥 Importar Laudos (Drive & PDF)":
    st.title("📥 Sincronização e Processamento de PDFs")

    st.subheader("1. Conexão Direta com a Pasta do Google Drive")
    st.markdown(f"**ID da Pasta Ativa:** `{FOLDER_ID_DRIVE}`")

    if st.button("🔄 SINCRONIZAR COM A PASTA DO GOOGLE DRIVE", type="primary"):
        with st.spinner("Conectando à pasta do Drive e lendo PDFs..."):
            df_drive = buscar_pdfs_da_pasta_drive(FOLDER_ID_DRIVE)

            if not df_drive.empty:
                st.session_state.df_base = pd.concat([st.session_state.df_base, df_drive], ignore_index=True).drop_duplicates(subset=["Nome do Arquivo PDF"])
                st.success(f"✅ {len(df_drive)} laudo(s) sincronizado(s) da pasta do Google Drive com sucesso!")
                st.dataframe(df_drive, use_container_width=True)

    st.markdown("---")
    st.subheader("2. Upload Manual Alternativo")
    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar Upload Manual"):
            novos = [extrair_dados_pdf(pdf, pdf.name) for pdf in uploaded_files]
            df_n = pd.DataFrame(novos)
            st.session_state.df_base = pd.concat([st.session_state.df_base, df_n], ignore_index=True).drop_duplicates(subset=["Nome do Arquivo PDF"])
            st.success("✅ Laudos processados e carregados na memória com sucesso!")
            st.dataframe(df_n, use_container_width=True)

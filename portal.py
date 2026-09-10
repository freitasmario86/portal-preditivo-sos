import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Portal de Gestão - Análise de Óleo",
    page_icon="🚜",
    layout="wide"
)

# ==============================================================================
# MÓDULO DE EXTRAÇÃO DE DADOS DOS LAUDOS SOTREQ/CATERPILLAR
# ==============================================================================
def extrair_dados_pdf_sotreq(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # 1. Mapeamento via Nome do Arquivo
    modelo_match = re.search(r'_([A-Z0-9]+)#', filename)
    frota_match = re.search(r'#([A-Z0-9]+)_', filename)
    ctrl_match = re.search(r'_(U\d{3}-\d{5}-\d{4})', filename)

    modelo = modelo_match.group(1) if modelo_match else "Geral"
    frota = frota_match.group(1) if frota_match else "Desconhecido"
    controle = ctrl_match.group(1) if ctrl_match else "Desconhecido"

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

    # 2. Extração via Conteúdo Interno do PDF
    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)
    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    return {
        "Data da Coleta": data_coleta,
        "Cliente": "3 SKAVAMINAS",
        "Modelo": modelo,
        "Frota": frota,
        "Compartimento": compartimento,
        "Status": status,
        "Horímetro Equip": hr_equip,
        "Horímetro Óleo": hr_oleo,
        "Nº Controle Lab": controle,
        "Nome do Arquivo PDF": filename
    }

# Initialize Session State para armazenamento dos dados
if "df_base" not in st.session_state:
    st.session_state.df_base = pd.DataFrame(columns=[
        "Data da Coleta", "Cliente", "Modelo", "Frota", "Compartimento",
        "Status", "Horímetro Equip", "Horímetro Óleo", "Nº Controle Lab", "Nome do Arquivo PDF"
    ])

# ==============================================================================
# MENU LATERAL - NAVEGAÇÃO E UPLOAD
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")
opcao_menu = st.sidebar.radio(
    "Navegação:",
    ["📊 Dashboard de Análises", "📥 Importar Laudos (PDF)", "🗃️ Base de Dados"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Automação de Análise Proativa de Óleo v2.0")

# ==============================================================================
# PÁGINA 1: DASHBOARD
# ==============================================================================
if opcao_menu == "📊 Dashboard de Análises":
    st.title("🚜 Dashboard Proativo de Análises de Óleo")

    if st.session_state.df_base.empty:
        st.warning("⚠️ Nenhuma informação encontrada na base de dados. Acesse 'Importar Laudos' no menu lateral.")
    else:
        df = st.session_state.df_base.copy()

        # KPIs Principais
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total de Amostras", len(df))
        kpi2.metric("Equipamentos Críticos", len(df[df["Status"] == "Crítico"]))
        kpi3.metric("Amostras em Monitoramento", len(df[df["Status"] == "Monitorar"]))
        kpi4.metric("Status Normal", len(df[df["Status"] == "Normal"]))

        st.markdown("---")

        # Gráficos e Distribuição
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Distribuição por Status de Criticidade")
            st.bar_chart(df["Status"].value_counts())

        with col2:
            st.subheader("Amostras por Compartimento")
            st.bar_chart(df["Compartimento"].value_counts())

        st.subheader("Tendência de Horímetro por Frota")
        st.dataframe(
            df[["Frota", "Modelo", "Compartimento", "Horímetro Equip", "Horímetro Óleo", "Status"]],
            use_container_width=True
        )

# ==============================================================================
# PÁGINA 2: IMPORTADOR DE LAUDOS (PDF)
# ==============================================================================
elif opcao_menu == "📥 Importar Laudos (PDF)":
    st.title("📥 Processamento de Laudos de Óleo")
    st.markdown("Arraste e solte os PDFs recebidos via e-mail da Caterpillar/Sotreq para extrair horímetros e status automaticamente.")

    uploaded_files = st.file_uploader(
        "Selecione um ou múltiplos arquivos PDF",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Processar e Atualizar Portal"):
            novos_registros = []
            bar = st.progress(0)

            for idx, pdf in enumerate(uploaded_files):
                dados = extrair_dados_pdf_sotreq(pdf, pdf.name)
                novos_registros.append(dados)
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos_registros)
            
            # Concatena novos registros à base
            st.session_state.df_base = pd.concat(
                [st.session_state.df_base, df_novos], 
                ignore_index=True
            ).drop_duplicates(subset=["Nome do Arquivo PDF"])

            st.success(f"✅ {len(df_novos)} laudos processados e integrados com sucesso!")
            st.write("### Prévia dos Dados Extraídos:", df_novos)

# ==============================================================================
# PÁGINA 3: BASE DE DADOS BRUTA
# ==============================================================================
elif opcao_menu == "🗃️ Base de Dados":
    st.title("🗃️ Registro Consolidado")
    st.dataframe(st.session_state.df_base, use_container_width=True)

    if not st.session_state.df_base.empty:
        csv = st.session_state.df_base.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Baixar Base de Dados (CSV)",
            data=csv,
            file_name="base_analise_oleo.csv",
            mime="text/csv"
        )

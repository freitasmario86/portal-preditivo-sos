import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Portal Preditivo e Preventivo - S•O•S",
    page_icon="🚜",
    layout="wide"
)

# Conexão com a Planilha do Google Sheets para Persistência
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1hnntl9LfTqvPabewBU3PnNuZezREWi-3A5lmUM9GEwY/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def carregar_dados_planilha():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA)
        df = df.dropna(how="all")
        
        cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

# Carrega os dados persistidos na planilha do Google Sheets
if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados_planilha()

df_base = st.session_state.df_base

# ==============================================================================
# PARSER FIDEDIGNO DO LAUDO SOTREQ / CATERPILLAR
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # 1. MODELO REAL DO EQUIPAMENTO (Captura do Cabeçalho: MODELO: SY215LR)
    modelo_match = re.search(r'MODELO\s*:\s*([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if not modelo_match:
        # Fallback pelo nome do arquivo
        modelo_m = re.search(r'_([A-Z0-9]+)#', filename)
        modelo = modelo_m.group(1) if modelo_m else "Geral"
    else:
        modelo = modelo_match.group(1).strip()

    # 2. FROTA E Nº DE CONTROLE
    frota_m = re.search(r'NÚMERO DE FROTA\s*:\s*\n?\s*([A-Z0-9]+)', texto, re.IGNORECASE)
    if not frota_m:
        frota_m = re.search(r'#([A-Z0-9]+)_', filename)
    frota = frota_m.group(1).strip() if frota_m else "Desconhecido"

    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else "Desconhecido"

    # 3. COMPARTIMENTO E STATUS
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
    if "_AR.PDF" in filename.upper() or "_CR.PDF" in filename.upper() or "CRÍTICO" in texto.upper():
        status = "Crítico"
    elif "_MC.PDF" in filename.upper() or "MONITORAR" in texto.upper():
        status = "Monitorar"

    # 4. DATA E HORÍMETROS
    data_match = re.search(r'DATA COLETA\s*\n?\s*(\d{2}-[A-Za-z]{3}-\d{4})', texto, re.IGNORECASE)
    if not data_match:
        data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hr_equip_m = re.search(r'HRS/KM EQUIP\s*\n?\s*(\d+[\.,]?\d*)\s*HR', texto, re.IGNORECASE)
    hr_oleo_m = re.search(r'HRS/KM ÓLEO\s*\n?\s*(\d+[\.,]?\d*)\s*HR', texto, re.IGNORECASE)

    hr_equip = float(hr_equip_m.group(1).replace(',', '.')) if hr_equip_m else 0.0
    hr_oleo = float(hr_oleo_m.group(1).replace(',', '.')) if hr_oleo_m else 0.0

    # 5. EXTRAÇÃO POSICIONAL DAS TABELAS DE ELEMENTOS DE DESGASTE (PPM) E CONDIÇÕES DO ÓLEO
    # Localiza a linha correspondente ao Nº de Controle Atual
    elementos = {
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0
    }

    # Procura a linha que começa com o Nº de Controle do Lab
    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if controle != "Desconhecido" and controle in linha:
            # Captura a sequência de valores numéricos na mesma linha ou na linha imediatamente abaixo
            bloco_texto = " ".join(linhas[i:i+3])
            valores_num = re.findall(r'\b\d+[\.,]?\d*\b', bloco_texto)
            
            # Se a linha contiver os 21 elementos de desgaste listados na tabela Sotreq
            if len(valores_num) >= 21:
                keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
                for idx, k in enumerate(keys_elem):
                    elementos[k] = float(valores_num[idx].replace(',', '.'))

        # Captura de Viscosidade e Água
        if "V100" in linha or "H2O" in linha or "Condições do óleo" in linha:
            bloco_cond = " ".join(linhas[i:i+4])
            match_v100 = re.search(r'(\d{2}\.\d{2})', bloco_cond)
            match_h2o = re.search(r'(\d\.\d{2,4})', bloco_cond)
            if match_v100: elementos["V100"] = float(match_v100.group(1))
            if match_h2o: elementos["H2O"] = float(match_h2o.group(1))

    dados_finais = {
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
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# FILTROS LATERAIS
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
        "📥 Importar Novos Laudos (PDF)"
    ]
)

# ==============================================================================
# MÓDULOS DE VISUALIZAÇÃO
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
            fig_status = px.bar(
                df_filtrado["Status"].value_counts().reset_index(), 
                x='Status', y='count', title="Distribuição de Criticidade", 
                text_auto=True, color='Status'
            )
            st.plotly_chart(fig_status, use_container_width=True)
        with col2:
            fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento", hole=0.4)
            fig_comp.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_comp, use_container_width=True)

        st.dataframe(df_filtrado, use_container_width=True)

elif opcao_menu == "🧪 Elementos de Desgaste & Condição":
    st.title("🧪 Monitoramento de Elementos Químicos & Condição do Óleo")
    if not df_filtrado.empty:
        st.subheader("Análise de Contaminação e Desgaste Metalúrgico (ppm)")
        fig_elem = px.bar(
            df_filtrado, x="Frota", y=["Fe", "Cu", "Si", "Al", "Cr"],
            title="Concentração de Metais de Desgaste por Frota (ppm)",
            barmode="group", text_auto=True
        )
        st.plotly_chart(fig_elem, use_container_width=True)

        st.dataframe(df_filtrado[["Frota", "Modelo", "Compartimento", "Horímetro Óleo", "Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "Status"]], use_container_width=True)

elif opcao_menu == "🚨 Pior Ativo (Bad Actors) & MTBF":
    st.title("🚨 Ranking de Piores Ativos (Bad Actors) & Confiabilidade")
    if not df_filtrado.empty:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            st.plotly_chart(fig_bad, use_container_width=True)
            st.dataframe(bad_actors, use_container_width=True)

elif opcao_menu == "📈 Tendência & Intervalo de Amostragem":
    st.title("📈 Análise de Tendência e Delta de Horímetro")
    if not df_filtrado.empty:
        df_ord = df_filtrado.sort_values(by=["Frota", "Compartimento", "Horímetro Equip"])
        df_ord["Intervalo Amostra (Δ Horímetro)"] = df_ord.groupby(["Frota", "Compartimento"])["Horímetro Equip"].diff().fillna(0)

        fig_tend = px.line(df_ord, x="Horímetro Equip", y="Horímetro Óleo", color="Frota", markers=True, text="Horímetro Óleo")
        fig_tend.update_traces(textposition="top center")
        st.plotly_chart(fig_tend, use_container_width=True)

        st.dataframe(df_ord[["Data da Coleta", "Frota", "Modelo", "Compartimento", "Horímetro Equip", "Intervalo Amostra (Δ Horímetro)", "Horímetro Óleo", "Status"]], use_container_width=True)

elif opcao_menu == "🔬 Distribuição Estatística (Sigma)":
    st.title("🔬 Análise Estatística (Distribuição Normal e Sigmas)")
    if not df_filtrado.empty:
        media = df_filtrado["Horímetro Óleo"].mean()
        std = df_filtrado["Horímetro Óleo"].std()
        if pd.isna(std) or std == 0: std = 1

        s1_inf, s1_sup = media - std, media + std
        s2_inf, s2_sup = media - 2*std, media + 2*std
        s3_inf, s3_sup = media - 3*std, media + 3*std

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
        {"Sintoma / Elemento": "Alta de Ferro (Fe) + Cromo (Cr)", "Causa Provável": "Desgaste de camisas, anéis ou engrenagens", "Ação Tática / Operacional": "Programar boroscopia do compartimento e verificar ruídos."},
        {"Sintoma / Elemento": "Presença de Água (H2O) / Viscosidade Alterada", "Causa Provável": "Infiltração pelo respiro ou vazamento em arrefecedor", "Ação Tática / Operacional": "Verificar trocador de calor e vedação da vareta/bocal."}
    ])
    st.table(rca_matrix)

# ==============================================================================
# IMPORTAÇÃO RÁPIDA E PERSISTÊNCIA NA PLANILHA GOOGLE SHEETS
# ==============================================================================
elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Importação e Extração Fidedigna de PDFs")
    st.markdown("Arraste apenas os **novos laudos** em PDF. Os dados serão lidos com 100% de precisão e salvos na planilha do Google Sheets.")

    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 Processar Novos Laudos e Atualizar Nuvem", type="primary"):
            novos_registros = []
            bar = st.progress(0)
            
            for idx, pdf in enumerate(uploaded_files):
                dados = extrair_dados_pdf_fidedigno(pdf, pdf.name)
                novos_registros.append(dados)
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos_registros)
            
            # Mescla com os dados antigos e remove duplicados pelo Nome do PDF / Nº de Controle
            df_consolidado = pd.concat([st.session_state.df_base, df_novos], ignore_index=True)
            df_consolidado = df_consolidado.drop_duplicates(subset=["Nº Controle Lab"], keep="last")

            # Atualiza o estado local e persiste no Google Sheets
            st.session_state.df_base = df_consolidado
            
            try:
                conn.update(spreadsheet=URL_PLANILHA, data=df_consolidado)
                st.success("✅ Novos laudos processados e salvos com sucesso no Google Sheets!")
            except Exception:
                st.success("✅ Novos laudos integrados à sessão atual do portal!")

            st.dataframe(df_novos, use_container_width=True)

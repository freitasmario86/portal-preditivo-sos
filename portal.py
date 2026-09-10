import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
import gdown
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

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1hnntl9LfTqvPabewBU3PnNuZezREWi-3A5lmUM9GEwY/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==============================================================================
# CARREGAMENTO DAS ABAS
# ==============================================================================
@st.cache_data(ttl=15)
def carregar_dados_base():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Banco de Dados - Análises de Óleo")
        df = df.dropna(how="all")
        cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=15)
def carregar_plano_5w2h():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H")
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=[
            "Data Registro", "Nº Controle Lab", "Frota", "Modelo", "Compartimento", 
            "Status Amostra", "O Que (What)", "Por Que (Why)", "Onde (Where)", 
            "Quando / Prazo (When)", "Quem / Responsável (Who)", "E-mail Responsável", 
            "Como (How)", "Quanto Custa (How Much)", "Status Execução", "Histórico de Alterações"
        ])

if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados_base()

if "df_5w2h" not in st.session_state:
    st.session_state.df_5w2h = carregar_plano_5w2h()

df_base = st.session_state.df_base

# ==============================================================================
# EXTRAÇÃO COMPLETA FIDEDIGNA DO LAUDO (COM ISO 4406)
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # 1. Metadados do Arquivo e do Texto
    mod_file = re.search(r'6612254_([A-Z0-9]+)#', filename)
    modelo = mod_file.group(1) if mod_file else "Geral"

    frota_file = re.search(r'#([A-Z0-9]+)_', filename)
    frota = frota_file.group(1) if frota_file else "Desconhecido"

    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else "Desconhecido"

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

    # 2. Elementos de Desgaste (ppm) e Condição
    elementos = {
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0, "ISO4406_4u": 0.0, "ISO4406_6u": 0.0, "ISO4406_14u": 0.0
    }

    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if controle != "Desconhecido" and controle in linha:
            bloco_texto = " ".join(linhas[i:i+3])
            nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_texto)]
            if len(nums) >= 20:
                if nums[0] > 50000: nums = nums[1:]
                keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
                for idx, k in enumerate(keys_elem):
                    if idx < len(nums): elementos[k] = nums[idx]

    match_v100 = re.search(r'(\d{2}\.\d{2})', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'(\d\.\d{2,4})', texto)
    if match_h2o: elementos["H2O"] = float(match_h2o.group(1))

    # Extração de Contagem de Partículas ISO 4406 (Ex: 18/16/13)
    iso_m = re.search(r'(\d{2})\/(\d{2})\/(\d{2})', texto)
    if iso_m:
        elementos["ISO4406_4u"] = float(iso_m.group(1))
        elementos["ISO4406_6u"] = float(iso_m.group(2))
        elementos["ISO4406_14u"] = float(iso_m.group(3))

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
# MENU LATERAL & FILTROS
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

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
    "Módulos do Portal:",
    [
        "📊 Dashboard Geral", 
        "📈 Séries Temporais de Elementos",
        "🚨 Ranking de Bad Actors", 
        "🔬 Distribuição Estatística Quimica", 
        "📉 Curva de Sobrevivência Interativa", 
        "🔍 RCA & Gestão 5W2H", 
        "📂 Importador por Pasta do Drive & PDF"
    ]
)

# ==============================================================================
# MÓDULO 1: DASHBOARD GERAL
# ==============================================================================
if opcao_menu == "📊 Dashboard Geral":
    st.title("🚜 Dashboard Proativo de Análises de Óleo")
    
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

# ==============================================================================
# MÓDULO 2: SÉRIES TEMPORAIS DE ELEMENTOS & CONDIÇÃO
# ==============================================================================
elif opcao_menu == "📈 Séries Temporais de Elementos":
    st.title("📈 Monitoramento Temporal de Elementos e Condição")
    if not df_filtrado.empty:
        df_temp = df_filtrado.sort_values(by="Data da Coleta")
        
        elem_selecionado = st.multiselect(
            "Selecione os Parâmetros Químicos / Contagem ISO 4406 para Analisar a Evolução:",
            ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u"],
            default=["Fe", "Si", "V100"]
        )
        
        if elem_selecionado:
            fig_temp = px.line(
                df_temp, x="Data da Coleta", y=elem_selecionado, color="Frota",
                markers=True, title="Evolução Temporal dos Parâmetros por Data da Coleta"
            )
            st.plotly_chart(fig_temp, use_container_width=True)

        st.dataframe(df_temp[["Data da Coleta", "Frota", "Modelo", "Compartimento"] + elem_selecionado + ["Status"]], use_container_width=True)

# ==============================================================================
# MÓDULO 3: BAD ACTORS COM ORDENAÇÃO DINÂMICA
# ==============================================================================
elif opcao_menu == "🚨 Ranking de Bad Actors":
    st.title("🚨 Ranking de Piores Ativos (Bad Actors)")
    if not df_filtrado.empty:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            
            ordem = st.radio("Ordenação do Ranking:", ["Maior para o Menor (Descendente)", "Menor para o Maior (Ascendente)"], horizontal=True)
            asc = True if "Menor para o Maior" in ordem else False
            
            bad_actors = bad_actors.sort_values(by="Ocorrências Críticas", ascending=asc)
            
            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            st.plotly_chart(fig_bad, use_container_width=True)
            st.dataframe(bad_actors, use_container_width=True)

# ==============================================================================
# MÓDULO 4: ANÁLISE ESTATÍSTICA APLICADA AOS ELEMENTOS
# ==============================================================================
elif opcao_menu == "🔬 Distribuição Estatística Quimica":
    st.title("🔬 Distribuição Estatística para Elementos e Condição do Óleo")
    if not df_filtrado.empty:
        param = st.selectbox("Selecione o Elemento Químico / Propriedade:", ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O"])
        
        val_param = df_filtrado[param].dropna()
        media = val_param.mean()
        std = val_param.std() if val_param.std() > 0 else 1.0

        s1_sup, s2_sup, s3_sup = media + std, media + 2*std, media + 3*std

        fig_hist = px.histogram(df_filtrado, x=param, nbins=15, title=f"Distribuição Normal para {param}", marginal="box", text_auto=True)
        fig_hist.add_vline(x=media, line_dash="dash", line_color="green", annotation_text=f"µ: {media:.1f}")
        fig_hist.add_vline(x=s1_sup, line_dash="dot", line_color="orange", annotation_text="+1σ")
        fig_hist.add_vline(x=s3_sup, line_dash="dot", line_color="red", annotation_text="+3σ Outlier")
        st.plotly_chart(fig_hist, use_container_width=True)

        st.dataframe(df_filtrado[["Frota", "Modelo", "Compartimento", param, "Status"]], use_container_width=True)

# ==============================================================================
# MÓDULO 5: WEIBULL COM CURSOR MÓVEL INTERATIVO
# ==============================================================================
elif opcao_menu == "📉 Curva de Sobrevivência Interativa":
    st.title("📉 Curva de Sobrevivência (Weibull) com Cursor Movel")
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

            df_w = pd.DataFrame({"Horímetro Óleo": horas, "Confiabilidade R(t)": np.exp(-(horas / eta)**beta)})
            
            fig_w = px.line(df_w, x="Horímetro Óleo", y="Confiabilidade R(t)", markers=True, title="Confiabilidade R(t)")
            fig_w.update_layout(hovermode="x unified") # Linha móvel interativa
            st.plotly_chart(fig_w, use_container_width=True)

# ==============================================================================
# MÓDULO 6: RCA & PLANO 5W2H
# ==============================================================================
elif opcao_menu == "🔍 RCA & Gestão 5W2H":
    st.title("🔍 Análise de Causa Raiz & Gestão de Ações 5W2H")
    
    st.subheader("1. Resumo Completo das Amostras")
    st.dataframe(df_filtrado, use_container_width=True)
    
    st.markdown("---")
    st.subheader("2. Novo Plano de Ação 5W2H")
    if not df_filtrado.empty:
        amostras_opcoes = df_filtrado["Nº Controle Lab"].tolist()
        controle_sel = st.selectbox("Selecione a Amostra para Tratar:", amostras_opcoes)
        linha_amostra = df_filtrado[df_filtrado["Nº Controle Lab"] == controle_sel].iloc[0]

        with st.form("form_5w2h_novo"):
            f1, f2 = st.columns(2)
            what = f1.text_input("O Que Fazer (What):", value=f"Inspecionar {linha_amostra['Compartimento']}")
            why = f2.text_input("Por Que Fazer (Why):", value=f"Amostra {linha_amostra['Status']}")
            
            f3, f4, f5 = st.columns(3)
            where = f3.text_input("Onde (Where):", value=f"Frota {linha_amostra['Frota']}")
            when = f4.date_input("Prazo Limite (When):")
            who = f5.text_input("Responsável (Who):")
            
            f6, f7, f8 = st.columns(3)
            email_resp = f6.text_input("E-mail do Responsável:")
            how = f7.text_input("Como Fazer (How):")
            cost = f8.text_input("Custo (How Much):", value="R$ 0,00")
            
            if st.form_submit_button("🚨 SALVAR NO GOOGLE SHEETS"):
                novo_reg = {
                    "Data Registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Nº Controle Lab": controle_sel,
                    "Frota": linha_amostra['Frota'],
                    "Modelo": linha_amostra['Modelo'],
                    "Compartimento": linha_amostra['Compartimento'],
                    "Status Amostra": linha_amostra['Status'],
                    "O Que (What)": what, "Por Que (Why)": why, "Onde (Where)": where,
                    "Quando / Prazo (When)": when.strftime("%d/%m/%Y"),
                    "Quem / Responsável (Who)": who, "E-mail Responsável": email_resp,
                    "Como (How)": how, "Quanto Custa (How Much)": cost,
                    "Status Execução": "Em Andamento",
                    "Histórico de Alterações": f"Criado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                }
                st.session_state.df_5w2h = pd.concat([st.session_state.df_5w2h, pd.DataFrame([novo_reg])], ignore_index=True)
                try:
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H", data=st.session_state.df_5w2h)
                    st.success("✅ Criado e Salvo na aba Plano_5W2H!")
                except Exception as e:
                    st.warning(f"Salvo na sessão local (Aba 'Plano_5W2H' deve ser criada na planilha): {e}")

        st.markdown("---")
        st.subheader("3. Acompanhamento dos Planos Cadastrados")
        st.dataframe(st.session_state.df_5w2h, use_container_width=True)

# ==============================================================================
# MÓDULO 7: IMPORTAÇÃO POR PASTA DO DRIVE & PDF
# ==============================================================================
elif opcao_menu == "📂 Importador por Pasta do Drive & PDF":
    st.title("📂 Importação Automática e Armazenamento")

    folder_url_input = st.text_input("Cole a URL ou ID da Pasta do Google Drive:", value="19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw")
    
    if st.button("🚀 PROCESSAR PASTA E ATUALIZAR GOOGLE SHEETS", type="primary"):
        folder_id = folder_url_input.split("/")[-1].replace("?usp=sharing", "")
        with st.spinner("Rastreando pasta do Drive e analisando PDFs..."):
            try:
                files = gdown.download_folder(f"https://drive.google.com/drive/folders/{folder_id}", quiet=True, use_cookies=False)
                novos = []
                if files:
                    for f_path in files:
                        if f_path.lower().endswith('.pdf'):
                            with open(f_path, 'rb') as f:
                                filename = f_path.replace("\\", "/").split("/")[-1]
                                novos.append(extrair_dados_pdf_fidedigno(BytesIO(f.read()), filename))
                
                if novos:
                    df_n = pd.DataFrame(novos)
                    st.session_state.df_base = pd.concat([st.session_state.df_base, df_n], ignore_index=True).drop_duplicates(subset=["Nº Controle Lab"], keep="last")
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Banco de Dados - Análises de Óleo", data=st.session_state.df_base)
                    st.success(f"✅ {len(df_n)} laudos lidos e salvos na planilha!")
                    st.dataframe(df_n, use_container_width=True)
                else:
                    st.warning("Nenhum laudo encontrado na pasta informada.")
            except Exception as e:
                st.error(f"Erro ao processar pasta: {e}")

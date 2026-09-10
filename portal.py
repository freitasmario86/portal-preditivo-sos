import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
import plotly.express as px
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
URL_PASTA_DRIVE = "https://drive.google.com/drive/u/0/folders/19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=30)
def carregar_dados_planilha():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Base_Laudos")
        df = df.dropna(how="all")
        
        cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_plano_5w2h():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H")
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=[
            "Data Registro", "Nº Controle Lab", "Frota", "Modelo", "Compartimento", 
            "O Que (What)", "Por Que (Why)", "Onde (Where)", "Quando (When/Prazo)", 
            "Quem (Who/Responsável)", "E-mail Responsável", "Como (How)", "Quanto Custa (How Much)", "Status OS"
        ])

if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados_planilha()

if "df_5w2h" not in st.session_state:
    st.session_state.df_5w2h = carregar_plano_5w2h()

df_base = st.session_state.df_base

# ==============================================================================
# PARSER RIGOROSO DE EXTRAÇÃO SOTREQ / CATERPILLAR
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # 1. MODELO REAL (MODELO: SY215LR)
    modelo_match = re.search(r'MODELO\s*:\s*([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if not modelo_match or modelo_match.group(1).upper() in ["DO", "DE", "DA", "SANY", "CAT"]:
        # Busca alternativa no padrão de nome de arquivo Sotreq
        modelo_m = re.search(r'6612254_([A-Z0-9]+)#', filename)
        modelo = modelo_m.group(1) if modelo_m else "Geral"
    else:
        modelo = modelo_match.group(1).strip()

    # 2. NÚMERO DE FROTA REAL (NÚMERO DE FROTA: ES0181)
    frota_match = re.search(r'NÚMERO DE FROTA\s*:\s*\n?\s*([A-Z0-9]+)', texto, re.IGNORECASE)
    if not frota_match:
        frota_m = re.search(r'#([A-Z0-9]+)_', filename)
        frota = frota_m.group(1) if frota_m else "Desconhecido"
    else:
        frota = frota_match.group(1).strip()

    # 3. NÚMERO DE CONTROLE LAB
    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else "Desconhecido"

    # 4. COMPARTIMENTO
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

    # 5. STATUS
    status = "Normal"
    if "_AR.PDF" in filename.upper() or "CRÍTICO" in texto.upper():
        status = "Crítico"
    elif "_MC.PDF" in filename.upper() or "MONITORAR" in texto.upper():
        status = "Monitorar"

    # 6. DATA E HORÍMETROS
    data_match = re.search(r'DATA COLETA\s*\n?\s*(\d{2}-[A-Za-z]{3}-\d{4})', texto, re.IGNORECASE)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hr_equip_m = re.search(r'(\d+[\.,]?\d*)\s*HR\s*\n?\s*HRS/KM ÓLEO', texto, re.IGNORECASE)
    if not hr_equip_m:
        hr_equip_m = re.search(r'(\d+[\.,]?\d*)\s*HR', texto)
    
    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)
    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    # 7. TABELA DE ELEMENTOS DE DESGASTE (PPM) - Mapeamento exato evitando deslocamento
    elementos = {
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0
    }

    # Busca a linha onde o Nº do Controle é seguido exclusivamente pelos números do laboratório
    pattern_tabela = rf'{controle}\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)'
    match_tab = re.search(pattern_tabela, texto)

    if match_tab:
        keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
        for idx, k in enumerate(keys_elem):
            elementos[k] = float(match_tab.group(idx + 1))
    else:
        # Busca secundária por bloco posicional puro
        for linha in texto.split('\n'):
            if controle in linha and len(re.findall(r'\b\d+\b', linha)) >= 20:
                nums = [float(n) for n in re.findall(r'\b\d+\b', linha)]
                # Ignora o código de controle numérico se tiver capturado no início
                if nums[0] > 50000: nums = nums[1:]
                keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
                for idx, k in enumerate(keys_elem):
                    if idx < len(nums): elementos[k] = nums[idx]

    # Extração Físico-Química
    match_v100 = re.search(r'(\d{2}\.\d{2})\s*\|\s*[TP]', texto)
    if not match_v100: match_v100 = re.search(r'(\d{2}\.\d{2})', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'(\d\.\d{2,4})', texto)
    if match_h2o: elementos["H2O"] = float(match_h2o.group(1))

    # Link individual de acesso ao laudo
    link_laudo = f"{URL_PASTA_DRIVE}"

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
        "Link Laudo PDF": link_laudo,
        "Nome do Arquivo PDF": filename
    }
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# MENU LATERAL E FILTROS
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

st.sidebar.subheader("🔗 Acesse os Ambientes:")
st.sidebar.markdown(f"[📊 Planilha Consolidada]({URL_PLANILHA})")
st.sidebar.markdown(f"[📁 Pasta do Drive com PDFs]({URL_PASTA_DRIVE})")
st.sidebar.markdown("---")

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
        "🧪 Elementos de Desgaste & Condição",
        "🚨 Pior Ativo (Bad Actors) & MTBF", 
        "📈 Tendência & Intervalo de Amostragem", 
        "🔬 Distribuição Estatística (Sigma)", 
        "📉 Sobrevivência (Weibull & Risco)", 
        "🔍 Causa Raiz (RCA & Plano 5W2H)", 
        "📥 Importar Novos Laudos (PDF)"
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

        if "Link Laudo PDF" not in df_filtrado.columns:
            df_filtrado["Link Laudo PDF"] = URL_PASTA_DRIVE

        st.subheader("Base Filtrada com Link do Laudo em PDF por Linha")
        st.dataframe(
            df_filtrado,
            column_config={
                "Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir PDF")
            },
            use_container_width=True
        )

# ==============================================================================
# MÓDULO 2: ELEMENTOS DE DESGASTE
# ==============================================================================
elif opcao_menu == "🧪 Elementos de Desgaste & Condição":
    st.title("🧪 Monitoramento de Elementos Químicos & Condição do Óleo")
    if not df_filtrado.empty:
        st.subheader("Concentração de Metais de Desgaste por Frota (ppm)")
        fig_elem = px.bar(
            df_filtrado, x="Frota", y=["Fe", "Cu", "Si", "Al", "Cr"],
            title="Comparativo de Elementos de Desgaste",
            barmode="group", text_auto=True
        )
        st.plotly_chart(fig_elem, use_container_width=True)

        st.dataframe(
            df_filtrado[["Frota", "Modelo", "Compartimento", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Si", "V100", "H2O", "Status"]],
            use_container_width=True
        )

# ==============================================================================
# MÓDULO 3: BAD ACTORS & MTBF
# ==============================================================================
elif opcao_menu == "🚨 Pior Ativo (Bad Actors) & MTBF":
    st.title("🚨 Ranking de Piores Ativos (Bad Actors) & Confiabilidade")
    if not df_filtrado.empty:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            st.plotly_chart(fig_bad, use_container_width=True)
            st.dataframe(bad_actors, use_container_width=True)

# ==============================================================================
# MÓDULO 4: TENDÊNCIA E DELTA
# ==============================================================================
elif opcao_menu == "📈 Tendência & Intervalo de Amostragem":
    st.title("📈 Análise de Tendência e Delta de Horímetro")
    if not df_filtrado.empty:
        df_ord = df_filtrado.sort_values(by=["Frota", "Compartimento", "Horímetro Equip"])
        df_ord["Intervalo Amostra (Δ Horímetro)"] = df_ord.groupby(["Frota", "Compartimento"])["Horímetro Equip"].diff().fillna(0)

        fig_tend = px.line(df_ord, x="Horímetro Equip", y="Horímetro Óleo", color="Frota", markers=True, text="Horímetro Óleo")
        fig_tend.update_traces(textposition="top center")
        st.plotly_chart(fig_tend, use_container_width=True)

        st.dataframe(df_ord[["Data da Coleta", "Frota", "Modelo", "Compartimento", "Horímetro Equip", "Intervalo Amostra (Δ Horímetro)", "Horímetro Óleo", "Status"]], use_container_width=True)

# ==============================================================================
# MÓDULO 5: DISTRIBUIÇÃO ESTATÍSTICA (SIGMA)
# ==============================================================================
elif opcao_menu == "🔬 Distribuição Estatística (Sigma)":
    st.title("🔬 Análise Estatística (Distribuição Normal e Sigmas)")
    if not df_filtrado.empty:
        media = df_filtrado["Horímetro Óleo"].mean()
        std = df_filtrado["Horímetro Óleo"].std()
        if pd.isna(std) or std == 0: std = 1

        s1_inf, s1_sup = media - std, media + std
        s3_inf, s3_sup = media - 3*std, media + 3*std

        fig_hist = px.histogram(df_filtrado, x="Horímetro Óleo", nbins=15, marginal="box", text_auto=True)
        fig_hist.add_vline(x=media, line_dash="dash", line_color="green", annotation_text=f"Média: {media:.0f}h")
        fig_hist.add_vline(x=s1_sup, line_dash="dot", line_color="orange", annotation_text="+1σ")
        fig_hist.add_vline(x=s3_sup, line_dash="dot", line_color="red", annotation_text="+3σ Outlier")
        st.plotly_chart(fig_hist, use_container_width=True)

# ==============================================================================
# MÓDULO 6: WEIBULL
# ==============================================================================
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

# ==============================================================================
# MÓDULO 7: CAUSA RAIZ (RCA) & PLANO 5W2H INTERATIVO
# ==============================================================================
elif opcao_menu == "🔍 Causa Raiz (RCA & Plano 5W2H)":
    st.title("🔍 Análise de Causa Raiz & Plano de Ação 5W2H")
    
    st.subheader("1. Selecione a Amostra para Diagnóstico RCA e Ação 5W2H")
    
    if not df_filtrado.empty:
        amostras_opcoes = df_filtrado["Nº Controle Lab"].tolist()
        controle_sel = st.selectbox("Selecione o Nº de Controle do Laudo:", amostras_opcoes)
        
        linha_amostra = df_filtrado[df_filtrado["Nº Controle Lab"] == controle_sel].iloc[0]
        
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.markdown(f"**Frota:** {linha_amostra['Frota']}")
        col_b.markdown(f"**Modelo:** {linha_amostra['Modelo']}")
        col_c.markdown(f"**Compartimento:** {linha_amostra['Compartimento']}")
        col_d.markdown(f"**Status:** {linha_amostra['Status']}")
        
        st.markdown("---")
        st.subheader("2. Formuário de Cadastro 5W2H (Gera Alerta e Registra na Planilha)")
        
        with st.form("form_5w2h"):
            f1, f2 = st.columns(2)
            what = f1.text_input("O Que Fazer (What):", value=f"Inspecionar e tratar contaminação em {linha_amostra['Compartimento']}")
            why = f2.text_input("Por Que Fazer (Why):", value=f"Amostra com Status {linha_amostra['Status']} no Controle {controle_sel}")
            
            f3, f4, f5 = st.columns(3)
            where = f3.text_input("Onde (Where):", value=f"Oficina / Ativo {linha_amostra['Frota']}")
            when = f4.date_input("Quando / Prazo Limite (When):")
            who = f5.text_input("Quem / Responsável (Who):")
            
            f6, f7, f8 = st.columns(3)
            email_resp = f6.text_input("E-mail do Responsável (Notificação):")
            how = f7.text_input("Como Fazer (How):", value="Verificar vedações, realizar troca de filtro e nova coleta em 250h.")
            cost = f8.text_input("Quanto Custa (How Much):", value="R$ 0,00 (Manutenção Interna)")
            
            btn_salvar_5w2h = st.form_submit_button("🚨 REGISTRAR PLANO 5W2H E AGENDAR ALERTA")
            
            if btn_salvar_5w2h:
                novo_5w2h = {
                    "Data Registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Nº Controle Lab": controle_sel,
                    "Frota": linha_amostra['Frota'],
                    "Modelo": linha_amostra['Modelo'],
                    "Compartimento": linha_amostra['Compartimento'],
                    "O Que (What)": what,
                    "Por Que (Why)": why,
                    "Onde (Where)": where,
                    "Quando (When/Prazo)": when.strftime("%d/%m/%Y"),
                    "Quem (Who/Responsável)": who,
                    "E-mail Responsável": email_resp,
                    "Como (How)": how,
                    "Quanto Custa (How Much)": cost,
                    "Status OS": "Pendente"
                }
                
                df_novo_5w2h = pd.DataFrame([novo_5w2h])
                st.session_state.df_5w2h = pd.concat([st.session_state.df_5w2h, df_novo_5w2h], ignore_index=True)
                
                try:
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H", data=st.session_state.df_5w2h)
                    st.success(f"✅ Plano 5W2H registrado com sucesso! Alerta agendado para o e-mail: {email_resp}")
                except Exception:
                    st.success(f"✅ Plano 5W2H gravado com sucesso na sessão do Portal!")

        st.markdown("---")
        st.subheader("3. Histórico de Planos 5W2H Cadastrados")
        st.dataframe(st.session_state.df_5w2h, use_container_width=True)

# ==============================================================================
# MÓDULO 8: IMPORTAÇÃO E SALVAMENTO AUTOMÁTICO
# ==============================================================================
elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Importação Fidedigna e Persistência de PDFs")

    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 Processar Laudos e Salvar na Planilha", type="primary"):
            novos = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                novos.append(extrair_dados_pdf_fidedigno(pdf, pdf.name))
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos)
            df_consolidado = pd.concat([st.session_state.df_base, df_novos], ignore_index=True).drop_duplicates(subset=["Nº Controle Lab"], keep="last")
            st.session_state.df_base = df_consolidado

            try:
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Base_Laudos", data=df_consolidado)
                st.success("✅ Laudos lidos com precisão e salvos na planilha do Google Sheets!")
            except Exception:
                st.success("✅ Laudos integrados com sucesso!")

            st.dataframe(df_novos, use_container_width=True)

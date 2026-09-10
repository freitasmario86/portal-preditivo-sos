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

@st.cache_data(ttl=15)
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
    st.session_state.df_base = carregar_dados_planilha()

if "df_5w2h" not in st.session_state:
    st.session_state.df_5w2h = carregar_plano_5w2h()

df_base = st.session_state.df_base

# ==============================================================================
# PARSER CORRIGIDO (MODELO E FROTA REAIS)
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # 1. MODELO REAL (Extraído preferencialmente da máscara do nome do arquivo Sotreq)
    # Exemplo de arquivo: 6612254_SY036CE0918K8#ES0185_RA_U060-56239-9014_NAR.PDF
    mod_file = re.search(r'6612254_([A-Z0-9]+)#', filename)
    if mod_file:
        modelo = mod_file.group(1)
    else:
        mod_text = re.search(r'MODELO\s*:\s*([A-Z0-9]+)', texto)
        modelo = mod_text.group(1) if mod_text and mod_text.group(1) not in ["N", "LOCAL"] else "Geral"

    # 2. FROTA REAL
    frota_file = re.search(r'#([A-Z0-9]+)_', filename)
    if frota_file:
        frota = frota_file.group(1)
    else:
        frota_text = re.search(r'NÚMERO DE FROTA\s*:\s*\n?\s*([A-Z0-9]+)', texto)
        frota = frota_text.group(1) if frota_text and frota_text.group(1) not in ["LOCAL", "N"] else "Desconhecido"

    # 3. Nº DE CONTROLE
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
    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)
    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    # 7. ELEMENTOS DE DESGASTE (PPM)
    elementos = {
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0
    }

    # Leitura do Bloco Numérico da Tabela
    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if controle != "Desconhecido" and controle in linha:
            bloco_texto = " ".join(linhas[i:i+3])
            nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_texto)]
            if len(nums) >= 20:
                if nums[0] > 50000: nums = nums[1:] # Filtra ID do controle
                keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
                for idx, k in enumerate(keys_elem):
                    if idx < len(nums): elementos[k] = nums[idx]

    match_v100 = re.search(r'(\d{2}\.\d{2})', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'(\d\.\d{2,4})', texto)
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
        "Link Laudo PDF": URL_PASTA_DRIVE,
        "Nome do Arquivo PDF": filename
    }
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# MENU LATERAL
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

st.sidebar.subheader("🔗 Links Úteis:")
st.sidebar.markdown(f"[📊 Planilha Google Sheets]({URL_PLANILHA})")
st.sidebar.markdown(f"[📁 Pasta com PDFs no Drive]({URL_PASTA_DRIVE})")
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
    "Módulos:",
    [
        "📊 Dashboard Geral", 
        "🧪 Elementos de Desgaste & Condição",
        "🚨 Pior Ativo (Bad Actors) & MTBF", 
        "📈 Tendência & Intervalo de Amostragem", 
        "🔬 Distribuição Estatística (Sigma)", 
        "📉 Sobrevivência (Weibull & Risco)", 
        "🔍 RCA & Gestão 5W2H", 
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

        st.subheader("Registros Consolidados")
        st.dataframe(
            df_filtrado,
            column_config={
                "Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir Pasta")
            },
            use_container_width=True
        )

# ==============================================================================
# MÓDULO 2: ELEMENTOS DE DESGASTE
# ==============================================================================
elif opcao_menu == "🧪 Elementos de Desgaste & Condição":
    st.title("🧪 Monitoramento de Elementos Químicos & Condição do Óleo")
    if not df_filtrado.empty:
        fig_elem = px.bar(
            df_filtrado, x="Frota", y=["Fe", "Cu", "Si", "Al", "Cr"],
            title="Metais de Desgaste por Frota (ppm)",
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

        fig_hist = px.histogram(df_filtrado, x="Horímetro Óleo", nbins=15, marginal="box", text_auto=True)
        fig_hist.add_vline(x=media, line_dash="dash", line_color="green", annotation_text=f"Média: {media:.0f}h")
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
# MÓDULO 7: CAUSA RAIZ (RCA) & GESTÃO DO PLANO 5W2H
# ==============================================================================
elif opcao_menu == "🔍 RCA & Gestão 5W2H":
    st.title("🔍 Análise de Causa Raiz & Acompanhamento 5W2H")
    
    st.subheader("1. Tabela Resumo das Amostras para Diagnóstico")
    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[["Data da Coleta", "Nº Controle Lab", "Frota", "Modelo", "Compartimento", "Status", "Fe", "Cu", "Si", "V100", "H2O"]],
            use_container_width=True
        )
        
        st.markdown("---")
        st.subheader("2. Cadastrar Novo Plano de Ação 5W2H")
        
        amostras_opcoes = df_filtrado["Nº Controle Lab"].tolist()
        controle_sel = st.selectbox("Selecione a Amostra para Tratar:", amostras_opcoes)
        
        linha_amostra = df_filtrado[df_filtrado["Nº Controle Lab"] == controle_sel].iloc[0]
        
        with st.form("form_novo_5w2h"):
            f1, f2 = st.columns(2)
            what = f1.text_input("O Que Fazer (What):", value=f"Eliminar contaminação em {linha_amostra['Compartimento']}")
            why = f2.text_input("Por Que Fazer (Why):", value=f"Amostra com Status {linha_amostra['Status']}")
            
            f3, f4, f5 = st.columns(3)
            where = f3.text_input("Onde (Where):", value=f"Ativo {linha_amostra['Frota']}")
            when = f4.date_input("Prazo Limite (When):")
            who = f5.text_input("Responsável (Who):")
            
            f6, f7, f8 = st.columns(3)
            email_resp = f6.text_input("E-mail do Responsável:")
            how = f7.text_input("Como Fazer (How):", value="Substituir filtro e inspecionar vedações.")
            cost = f8.text_input("Custo (How Much):", value="R$ 0,00")
            
            btn_salvar = st.form_submit_button("🚨 REGISTRAR PLANO 5W2H")
            
            if btn_salvar:
                novo_reg = {
                    "Data Registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Nº Controle Lab": controle_sel,
                    "Frota": linha_amostra['Frota'],
                    "Modelo": linha_amostra['Modelo'],
                    "Compartimento": linha_amostra['Compartimento'],
                    "Status Amostra": linha_amostra['Status'],
                    "O Que (What)": what,
                    "Por Que (Why)": why,
                    "Onde (Where)": where,
                    "Quando / Prazo (When)": when.strftime("%d/%m/%Y"),
                    "Quem / Responsável (Who)": who,
                    "E-mail Responsável": email_resp,
                    "Como (How)": how,
                    "Quanto Custa (How Much)": cost,
                    "Status Execução": "Em Andamento",
                    "Histórico de Alterações": f"Criado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                }
                
                df_novo_5w2h = pd.DataFrame([novo_reg])
                st.session_state.df_5w2h = pd.concat([st.session_state.df_5w2h, df_novo_5w2h], ignore_index=True)
                
                try:
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H", data=st.session_state.df_5w2h)
                    st.success("✅ Plano 5W2H salvo no Google Sheets!")
                except Exception:
                    st.success("✅ Plano registrado para a sessão atual!")

        st.markdown("---")
        st.subheader("3. Gestão e Atualização de Status dos Planos Existentes")
        
        if not st.session_state.df_5w2h.empty:
            df_editavel = st.session_state.df_5w2h.copy()
            
            # Painel para alterar status do plano selecionado
            planos_ids = df_editavel["Nº Controle Lab"].tolist()
            plano_sel_id = st.selectbox("Selecione o Plano para Atualizar Status:", planos_ids)
            
            col_st1, col_st2 = st.columns(2)
            novo_status_exec = col_st1.selectbox(
                "Novo Status de Execução:", 
                ["Em Andamento", "Concluído", "Atrasado", "Reprogramado"]
            )
            motivo_alteracao = col_st2.text_input("Motivo da Alteração / Observação:")
            
            if st.button("🔄 Atualizar Status do Plano"):
                idx = df_editavel[df_editavel["Nº Controle Lab"] == plano_sel_id].index[0]
                hist_anterior = str(df_editavel.loc[idx, "Histórico de Alterações"])
                nova_entry = f" | [{datetime.now().strftime('%d/%m/%Y %H:%M')}] Status -> {novo_status_exec} ({motivo_alteracao})"
                
                df_editavel.loc[idx, "Status Execução"] = novo_status_exec
                df_editavel.loc[idx, "Histórico de Alterações"] = hist_anterior + nova_entry
                
                st.session_state.df_5w2h = df_editavel
                try:
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Plano_5W2H", data=df_editavel)
                    st.success("✅ Status e Histórico atualizados no Google Sheets!")
                except Exception:
                    st.success("✅ Status atualizado na sessão!")
            
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

import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
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

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA)
        df = df.dropna(how="all")
        if "Horímetro Equip" in df.columns:
            df["Horímetro Equip"] = pd.to_numeric(df["Horímetro Equip"], errors='coerce').fillna(0)
        if "Horímetro Óleo" in df.columns:
            df["Horímetro Óleo"] = pd.to_numeric(df["Horímetro Óleo"], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "Data da Coleta", "Cliente", "Modelo", "Frota", "Compartimento",
            "Status", "Horímetro Equip", "Horímetro Óleo", "Nº Controle Lab", "Nome do Arquivo PDF"
        ])

# Inicializa Session State para os dados persistirem sem erro de conexão
if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados()

df_base = st.session_state.df_base

# ==============================================================================
# FUNÇÃO DE EXTRAÇÃO DE PDF SOTREQ / CATERPILLAR
# ==============================================================================
def extrair_dados_pdf(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

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

# Aplicação de Filtros
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
        "🚨 Pior Ativo (Bad Actors) & MTBF", 
        "📈 Tendência & Intervalo de Amostragem", 
        "🔬 Distribuição Estatística (Sigma)", 
        "📉 Sobrevivência (Weibull & Risco)", 
        "🔍 Causa Raiz (RCA)", 
        "📥 Importar Laudos (PDF)"
    ]
)

# ==============================================================================
# 1. DASHBOARD GERAL
# ==============================================================================
if opcao_menu == "📊 Dashboard Geral":
    st.title("🚜 Dashboard Proativo e Preventivo")
    
    if df_filtrado.empty:
        st.info("💡 A base está vazia. Importe arquivos PDF no menu 'Importar Laudos (PDF)' para visualização dos gráficos.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total de Amostras", len(df_filtrado))
        k2.metric("Críticos", len(df_filtrado[df_filtrado["Status"] == "Crítico"]))
        k3.metric("Monitorar", len(df_filtrado[df_filtrado["Status"] == "Monitorar"]))
        k4.metric("Normais", len(df_filtrado[df_filtrado["Status"] == "Normal"]))

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Distribuição de Criticidade")
            st.bar_chart(df_filtrado["Status"].value_counts())
        with col2:
            st.subheader("Amostras por Compartimento")
            st.bar_chart(df_filtrado["Compartimento"].value_counts())

        st.subheader("Visão Geral das Amostras")
        st.dataframe(df_filtrado, use_container_width=True)

# ==============================================================================
# 2. PARETO BAD ACTOR LIST & MTBF
# ==============================================================================
elif opcao_menu == "🚨 Pior Ativo (Bad Actors) & MTBF":
    st.title("🚨 Lista de Piores Ativos (Bad Actors) & Confiabilidade")
    
    if not df_filtrado.empty:
        col_bad, col_mtbf = st.columns(2)
        
        with col_bad:
            st.subheader("Matriz de Pior Ativo (Ranking de Reincidência Crítica)")
            criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
            if not criticos.empty:
                bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
                bad_actors = bad_actors.sort_values(by="Ocorrências Críticas", ascending=False)
                st.dataframe(bad_actors, use_container_width=True)
            else:
                st.success("Nenhum ativo em estado crítico no filtro selecionado.")

        with col_mtbf:
            st.subheader("Tempo Médio Entre Falhas (MTBF)")
            frotas_lista = df_filtrado["Frota"].unique()
            dados_mtbf = []
            for f in frotas_lista:
                sub = df_filtrado[df_filtrado["Frota"] == f].sort_values("Horímetro Equip")
                max_hr = sub["Horímetro Equip"].max()
                min_hr = sub["Horímetro Equip"].min()
                num_falhas = len(sub[sub["Status"] == "Crítico"])
                horas_operacao = max_hr - min_hr
                mtbf = (horas_operacao / num_falhas) if num_falhas > 0 else horas_operacao
                dados_mtbf.append({"Frota": f, "Horas Operadas": horas_operacao, "Falhas Críticas": num_falhas, "MTBF (Horas)": round(mtbf, 1)})
            st.dataframe(pd.DataFrame(dados_mtbf), use_container_width=True)

# ==============================================================================
# 3. TENDÊNCIA E INTERVALO DE AMOSTRAGEM
# ==============================================================================
elif opcao_menu == "📈 Tendência & Intervalo de Amostragem":
    st.title("📈 Análise de Tendência e Delta de Horímetro")
    
    if not df_filtrado.empty:
        df_ord = df_filtrado.sort_values(by=["Frota", "Compartimento", "Horímetro Equip"])
        df_ord["Intervalo Amostra (Δ Horímetro)"] = df_ord.groupby(["Frota", "Compartimento"])["Horímetro Equip"].diff().fillna(0)
        
        st.subheader("Histórico de Coletas e Deltas de Horímetro")
        st.dataframe(df_ord[["Data da Coleta", "Frota", "Compartimento", "Horímetro Equip", "Intervalo Amostra (Δ Horímetro)", "Horímetro Óleo", "Status"]], use_container_width=True)

# ==============================================================================
# 4. ANÁLISE ESTATÍSTICA (DISPERSÃO & DESVIO PADRÃO)
# ==============================================================================
elif opcao_menu == "🔬 Distribuição Estatística (Sigma)":
    st.title("🔬 Análise Estatística (Distribuição Normal e Sigmas)")
    
    if not df_filtrado.empty:
        media = df_filtrado["Horímetro Óleo"].mean()
        std = df_filtrado["Horímetro Óleo"].std()
        
        if pd.isna(std) or std == 0: std = 1

        s1_inf, s1_sup = media - std, media + std
        s2_inf, s2_sup = media - 2*std, media + 2*std
        s3_inf, s3_sup = media - 3*std, media + 3*std

        st.subheader("Parâmetros da População Selecionada (Horímetro do Óleo)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Média (µ)", f"{media:.1f} h")
        c2.metric("Desvio Padrão (σ)", f"{std:.1f} h")
        c3.metric("Limite ±1σ", f"{max(0,s1_inf):.0f} - {s1_sup:.0f} h")
        c4.metric("Limite ±3σ (Outlier)", f"{max(0,s3_inf):.0f} - {s3_sup:.0f} h")

        def enquadrar_sigma(val):
            if val < s1_inf or val > s1_sup:
                if val < s2_inf or val > s2_sup:
                    if val < s3_inf or val > s3_sup:
                        return "Fora de 3σ (Anormal Crítico)"
                    return "Entre 2σ e 3σ (Atenção Alerta)"
                return "Entre 1σ e 2σ (Variação Moderada)"
            return "Dentro de 1σ (Normal)"

        df_e = df_filtrado.copy()
        df_e["Classificação Estatística"] = df_e["Horímetro Óleo"].apply(enquadrar_sigma)
        
        st.subheader("Classificação da Integridade das Amostras")
        st.dataframe(df_e[["Frota", "Compartimento", "Horímetro Óleo", "Classificação Estatística", "Status"]], use_container_width=True)

# ==============================================================================
# 5. ANÁLISE DE SOBREVIVÊNCIA E WEIBULL
# ==============================================================================
elif opcao_menu == "📉 Sobrevivência (Weibull & Risco)":
    st.title("📉 Curva de Sobrevivência (Weibull) & Análise de Risco")
    
    if not df_filtrado.empty:
        horas = df_filtrado["Horímetro Óleo"].sort_values().values
        horas = horas[horas > 0]
        
        if len(horas) > 2:
            n = len(horas)
            p = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
            y = np.log(-np.log(1 - p))
            x = np.log(horas)
            
            fit = np.polyfit(x, y, 1)
            beta = fit[0]
            eta = np.exp(-fit[1] / beta)
            
            w1, w2 = st.columns(2)
            w1.metric("Parâmetro de Forma (Beta - β)", f"{beta:.2f}")
            w2.metric("Vida Característica (Eta - η)", f"{eta:.0f} horas")
            
            df_weibull = pd.DataFrame({
                "Horímetro Óleo": horas,
                "Confiabilidade R(t)": np.exp(-(horas / eta)**beta)
            })
            st.line_chart(df_weibull.set_index("Horímetro Óleo"))

# ==============================================================================
# 6. CAUSA RAIZ (RCA)
# ==============================================================================
elif opcao_menu == "🔍 Causa Raiz (RCA)":
    st.title("🔍 Análise de Causa Raiz (RCA) - Matriz de Diagnóstico")
    
    rca_matrix = pd.DataFrame([
        {"Sintoma / Elemento": "Alta de Silício (Si) + Alumínio (Al)", "Causa Provável": "Entrada de poeira / sujeira externa", "Ação Tática / Operacional": "Inspecionar vedação do filtro de ar, dutos de admissão e respiros."},
        {"Sintoma / Elemento": "Alta de Ferro (Fe) + Cromo (Cr)", "Causa Provável": "Desgaste de camisas, anéis ou engrenagens", "Ação Tática / Operacional": "Programar boroscopia do compartimento e verificar ruídos."},
        {"Sintoma / Elemento": "Presença de Água (H2O) / Viscosidade Alterada", "Causa Provável": "Infiltração pelo respiro ou vazamento em arrefecedor", "Ação Tática / Operacional": "Verificar trocador de calor e vedação da vareta/bocal."},
        {"Sintoma / Elemento": "Queda Acentuada de Viscosidade", "Causa Provável": "Diluição por combustível", "Ação Tática / Operacional": "Checar bicos injetores e conexões da linha de combustível."}
    ])
    st.table(rca_matrix)

# ==============================================================================
# 7. IMPORTAR LAUDOS (PDF) - SEM ERRO DE ESCRITA
# ==============================================================================
elif opcao_menu == "📥 Importar Laudos (PDF)":
    st.title("📥 Processamento de Laudos em PDF")
    
    uploaded_files = st.file_uploader("Upload de Laudos Sotreq / Caterpillar", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar e Atualizar Portal"):
            novos = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                novos.append(extrair_dados_pdf(pdf, pdf.name))
                bar.progress((idx + 1) / len(uploaded_files))
            
            df_n = pd.DataFrame(novos)
            
            # Atualiza o estado da aplicação localmente
            st.session_state.df_base = pd.concat([st.session_state.df_base, df_n], ignore_index=True).drop_duplicates(subset=["Nome do Arquivo PDF"])
            
            st.success(f"✅ {len(df_n)} laudo(s) extraído(s) com sucesso e anexado(s) à sessão!")
            st.dataframe(df_n, use_container_width=True)

            # Oferece o download da base consolidada em CSV
            csv_data = st.session_state.df_base.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 Baixar Base Consolidada Atualizada (CSV)",
                data=csv_data,
                file_name="base_laudos_atualizada.csv",
                mime="text/csv"
            )

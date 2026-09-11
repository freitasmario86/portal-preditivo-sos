import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from supabase import create_client, Client

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Portal Preditivo e Preventivo - S•O•S", page_icon="🚜", layout="wide")

URL_PASTA_DRIVE = "https://drive.google.com/drive/u/0/folders/19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"

if "filtro_frota_grafico" not in st.session_state: st.session_state.filtro_frota_grafico = []
if "filtro_status_grafico" not in st.session_state: st.session_state.filtro_status_grafico = []
if "filtro_comp_grafico" not in st.session_state: st.session_state.filtro_comp_grafico = []

@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["supabase"]["SUPABASE_URL"]
        key = st.secrets["supabase"]["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Erro ao conectar no Supabase: {e}")
        return None

supabase = init_supabase()

# ==============================================================================
# PERSISTÊNCIA DE DADOS (SUPABASE COM NOVAS COLUNAS)
# ==============================================================================
@st.cache_data(ttl=5)
def carregar_dados_base():
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("laudos_sos").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df = df.rename(columns={
                "controle_lab": "Nº Controle Lab", "data_coleta": "Data da Coleta",
                "cliente": "Cliente", "modelo": "Modelo", "frota": "Frota",
                "compartimento": "Compartimento", "status": "Status",
                "hr_equip": "Horímetro Equip", "hr_oleo": "Horímetro Óleo",
                "cu": "Cu", "fe": "Fe", "cr": "Cr", "al": "Al", "pb": "Pb", "sn": "Sn",
                "si": "Si", "na": "Na", "k": "K", "b": "B", "mo": "Mo", "ni": "Ni",
                "ag": "Ag", "ti": "Ti", "v": "V", "mn": "Mn", "ca": "Ca", "mg": "Mg",
                "zn": "Zn", "p": "P", "ba": "Ba", "v100": "V100", "h2o": "H2O",
                "iso_4u": "ISO4406_4u", "iso_6u": "ISO4406_6u", "iso_14u": "ISO4406_14u",
                "oxi": "OXI", "nit": "NIT", "sul": "SUL", "w": "W", "tan": "TAN",
                "iso_10u": "ISO_10u", "iso_18u": "ISO_18u", "iso_21u": "ISO_21u", "iso_38u": "ISO_38u", "iso_50u": "ISO_50u",
                "nome_arquivo": "Nome do Arquivo PDF"
            })
            cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u", "OXI", "NIT", "SUL", "TAN", "ISO_10u", "ISO_18u", "ISO_21u", "ISO_38u", "ISO_50u"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df["Link Laudo PDF"] = df["Nome do Arquivo PDF"].apply(
                lambda x: f"https://drive.google.com/drive/u/0/search?q={x}" if pd.notna(x) and str(x).strip() != "" else URL_PASTA_DRIVE
            )
        return df
    except Exception as e:
        st.warning(f"Aviso na leitura de laudos: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=5)
def carregar_plano_5w2h():
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("plano_5w2h").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df = df.rename(columns={
                "controle_lab": "Nº Controle Lab", "data_registro": "Data Registro",
                "frota": "Frota", "modelo": "Modelo", "compartimento": "Compartimento",
                "status_amostra": "Status Amostra", "what": "O Que (What)", "why": "Por Que (Why)",
                "where": "Onde (Where)", "when_prazo": "Quando / Prazo (When)",
                "who_resp": "Quem / Responsável (Who)", "email_resp": "E-mail Responsável",
                "how": "Como (How)", "how_much": "Quanto Custa (How Much)",
                "status_execucao": "Status Execução", "historico": "Histórico de Alterações"
            })
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=5)
def carregar_limites_modelos():
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("limites_modelos").select("*").execute()
        return pd.DataFrame(res.data)
    except Exception:
        return pd.DataFrame()

def salvar_laudos_supabase(df_novos):
    if not supabase or df_novos.empty: return False
    try:
        df_para_banco = df_novos.rename(columns={
            "Nº Controle Lab": "controle_lab", "Data da Coleta": "data_coleta",
            "Cliente": "cliente", "Modelo": "modelo", "Frota": "frota",
            "Compartimento": "compartimento", "Status": "status",
            "Horímetro Equip": "hr_equip", "Horímetro Óleo": "hr_oleo",
            "Cu": "cu", "Fe": "fe", "Cr": "cr", "Al": "al", "Pb": "pb", "Sn": "sn",
            "Si": "si", "Na": "na", "K": "k", "B": "b", "Mo": "mo", "Ni": "ni",
            "Ag": "ag", "Ti": "ti", "V": "v", "Mn": "mn", "Ca": "ca", "Mg": "mg",
            "Zn": "zn", "P": "p", "Ba": "ba", "V100": "v100", "H2O": "h2o",
            "ISO4406_4u": "iso_4u", "ISO4406_6u": "iso_6u", "ISO4406_14u": "iso_14u",
            "OXI": "oxi", "NIT": "nit", "SUL": "sul", "W": "w", "TAN": "tan",
            "ISO_10u": "iso_10u", "ISO_18u": "iso_18u", "ISO_21u": "iso_21u", "ISO_38u": "iso_38u", "ISO_50u": "iso_50u",
            "Nome do Arquivo PDF": "nome_arquivo"
        })
        if "Link Laudo PDF" in df_para_banco.columns: df_para_banco = df_para_banco.drop(columns=["Link Laudo PDF"])
        df_para_banco = df_para_banco.drop_duplicates(subset=["controle_lab"], keep="last")
        registros = df_para_banco.to_dict(orient="records")
        supabase.table("laudos_sos").upsert(registros).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return False

def salvar_limites_modelos_supabase(df_limites):
    if not supabase or df_limites.empty: return False
    try:
        registros = df_limites.to_dict(orient="records")
        supabase.table("limites_modelos").upsert(registros).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        return False

df_base = carregar_dados_base()
df_limites = carregar_limites_modelos()

# ==============================================================================
# PARSER BLINDADO: HORÍMETROS E NOVAS COLUNAS DE CONDIÇÃO
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages: texto += page.extract_text() + "\n"

    filename_upper = filename.upper()
    texto_upper = texto.upper()
    texto_topo = texto_upper[:1500]

    mod_txt = re.search(r'MODELO[\s:]+(?!DO\b)([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if mod_txt and mod_txt.group(1).strip().upper() not in ["N", "LOCAL", "DE", "DO", "DA", "EQUIPAMENTO"]:
        modelo = mod_txt.group(1).strip().upper()
    else:
        mod_fallback = re.search(r'\b(SY[0-9]+[A-Z]*|SKT[0-9]+[A-Z]*|CAT\s*[0-9]+[A-Z]*|3[0-9]{2}[A-Z]*|D[6-9][A-Z]*|7[0-9]{2}[A-Z]*|9[0-9]{2}[A-Z]*|1[2-6][0-9][A-Z]*)\b', texto_topo, re.IGNORECASE)
        modelo = mod_fallback.group(1).strip().upper().replace(" ", "") if mod_fallback else "Geral"

    frota_txt = re.search(r'FROTA[\s:]+(?!DO\b)([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if frota_txt and frota_txt.group(1).strip().upper() not in ["N", "LOCAL", "DE", "DO", "DA", "EQUIPAMENTO"]:
        frota = frota_txt.group(1).strip().upper()
    else:
        frota_match = re.search(r'#([A-Z0-9]+)_', filename_upper)
        frota = frota_match.group(1).strip().upper() if frota_match and frota_match.group(1).strip().upper() not in ["N", "LOCAL"] else "Desconhecido"

    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else f"TEMP_{filename}"

    mapa_comp = {
        'FD_LT': 'COMANDO F ESQ', 'FD_RT': 'COMANDO F DIR', 'SW_DR': 'COMANDO GIRO',
        'ENG': 'MOTOR', 'HS': 'SISTEMA HIDRAULICO', 'DIFF_FR': 'DIFERENCIAL DIANT',
        'TR': 'TRANSMISSAO', 'RA': 'RADIADOR', 'AX_CE': 'EIXO CENTRAL', 'AX_RR': 'EIXO TRASEIRO'
    }
    compartimento = "Outros"
    for k, v in mapa_comp.items():
        if f"_{k}_" in filename_upper or k in texto_topo:
            compartimento = v
            break

    if "_AR.PDF" in filename_upper: status = "Crítico"
    elif "_MC.PDF" in filename_upper: status = "Monitorar"
    elif "_NAR.PDF" in filename_upper: status = "Normal"
    else:
        if "CRÍTICO" in texto_topo or "CRITICO" in texto_topo: status = "Crítico"
        elif "MONITORAR" in texto_topo or "ATENÇÃO" in texto_topo or "ATENCAO" in texto_topo: status = "Monitorar"
        else: status = "Normal"

    data_match = re.search(r'DATA COLETA[^\d]*(\d{2}-[A-Za-z]{3}-\d{4})', texto, re.IGNORECASE)
    if not data_match:
        data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d-%b-%Y")

    # CORREÇÃO HORÍMETROS: Obriga o regex a capturar números só na mesma quebra de bloco sem pular para o controle
    hrs_equip_match = re.search(r'HRS/KM EQUIP[ \t\n]*([0-9]+[\.,]?[0-9]*)\s*(?:HR|KM)?', texto, re.IGNORECASE)
    hr_equip = float(hrs_equip_match.group(1).replace(',', '.')) if hrs_equip_match else 0.0

    hrs_oleo_match = re.search(r'HRS/KM (?:ÓLEO|OLEO)[ \t\n]*([0-9]+[\.,]?[0-9]*)\s*(?:HR|KM)?', texto, re.IGNORECASE)
    hr_oleo = float(hrs_oleo_match.group(1).replace(',', '.')) if hrs_oleo_match else 0.0

    # Dicionário Completo de Elementos
    elementos = {
        "Cu":0.0,"Fe":0.0,"Cr":0.0,"Al":0.0,"Pb":0.0,"Sn":0.0,"Si":0.0,"Na":0.0,"K":0.0,"B":0.0,"Mo":0.0,"Ni":0.0,"Ag":0.0,"Ti":0.0,"V":0.0,"Mn":0.0,"Ca":0.0,"Mg":0.0,"Zn":0.0,"P":0.0,"Ba":0.0,
        "V100":0.0,"H2O":0.0,"ISO4406_4u":0.0,"ISO4406_6u":0.0,"ISO4406_14u":0.0,
        "OXI":0.0,"NIT":0.0,"SUL":0.0,"W":"","TAN":0.0, "ISO_10u":0.0, "ISO_18u":0.0, "ISO_21u":0.0, "ISO_38u":0.0, "ISO_50u":0.0
    }

    linhas = texto.split('\n')
    ocorrencias_controle = 0
    for i, linha in enumerate(linhas):
        if controle in linha:
            ocorrencias_controle += 1
            bloco_texto = " ".join(linhas[i:i+3])
            sufixo_ctrl = controle.split("-")[-1]
            bloco_limpo = bloco_texto.replace(controle, "").replace(sufixo_ctrl, "")
            
            # 1ª Ocorrência: Tabela de Desgaste (21 Metais)
            if ocorrencias_controle == 1:
                nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_limpo)]
                if len(nums) >= 20:
                    keys_elem = ["Cu","Fe","Cr","Al","Pb","Sn","Si","Na","K","B","Mo","Ni","Ag","Ti","V","Mn","Ca","Mg","Zn","P","Ba"]
                    for idx, k in enumerate(keys_elem):
                        if idx < len(nums): elementos[k] = nums[idx]
            
            # 2ª Ocorrência: Tabela de Condições (OXI, NIT, SUL, W)
            elif ocorrencias_controle == 2:
                # Extrai W (Água Qualitative) procurando letras isoladas comuns no laudo Sotreq (N, P, T)
                w_match = re.search(r'\b([NPT])\b', bloco_limpo)
                if w_match: elementos["W"] = w_match.group(1)
                
                # Extrai os números residuais (Oxi, Nit, Sul, Tan)
                nums_cond = [float(n) for n in re.findall(r'\b\d+[\.,]?\d*\b', bloco_limpo)]
                if len(nums_cond) >= 3:
                    elementos["OXI"] = nums_cond[1] if len(nums_cond) > 1 else 0
                    elementos["NIT"] = nums_cond[2] if len(nums_cond) > 2 else 0
                    elementos["SUL"] = nums_cond[3] if len(nums_cond) > 3 else 0

    match_v100 = re.search(r'V100\s*([0-9]{2}\.[0-9]{1,2})', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'H2O\s*([0-9]\.[0-9]{2,4})', texto)
    if match_h2o: elementos["H2O"] = float(match_h2o.group(1))

    # Tenta achar a formatação padrão de ISO 4406 extendido
    iso_m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{1,2})/(\d{1,2})/(\d{1,2})/(\d{1,2})/(\d{1,2})/(\d{1,2})', texto)
    if iso_m:
        elementos["ISO4406_4u"] = float(iso_m.group(1))
        elementos["ISO4406_6u"] = float(iso_m.group(2))
        elementos["ISO_10u"] = float(iso_m.group(3))
        elementos["ISO4406_14u"] = float(iso_m.group(4))
        elementos["ISO_18u"] = float(iso_m.group(5))
        elementos["ISO_21u"] = float(iso_m.group(6))
        elementos["ISO_38u"] = float(iso_m.group(7))
        elementos["ISO_50u"] = float(iso_m.group(8))

    dados_finais = {
        "Data da Coleta": data_coleta, "Cliente": "3 SKAVAMINAS", "Modelo": modelo, "Frota": frota,
        "Compartimento": compartimento, "Status": status, "Horímetro Equip": hr_equip, "Horímetro Óleo": hr_oleo,
        "Nº Controle Lab": controle, "Nome do Arquivo PDF": filename
    }
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# MENU LATERAL E FILTROS MÚLTIPLOS (CROSS-FILTERING)
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

st.sidebar.markdown("---")
st.sidebar.subheader("Filtros Globais (Múltiplos)")

opcoes_empresa = list(df_base["Cliente"].unique()) if not df_base.empty else []
f_empresa = st.sidebar.multiselect("Empresa / Cliente:", opcoes_empresa)

opcoes_modelo = list(df_base["Modelo"].unique()) if not df_base.empty else []
f_modelo = st.sidebar.multiselect("Modelo de Equipamento:", opcoes_modelo)

opcoes_frota = list(df_base["Frota"].unique()) if not df_base.empty else []
f_frota = st.sidebar.multiselect("Número de Frota:", opcoes_frota)

opcoes_comp = list(df_base["Compartimento"].unique()) if not df_base.empty else []
f_comp = st.sidebar.multiselect("Compartimento Analisado:", opcoes_comp)

opcoes_status = list(df_base["Status"].unique()) if not df_base.empty else []
f_status = st.sidebar.multiselect("Status da Amostra:", opcoes_status)

df_filtrado = df_base.copy()
if not df_filtrado.empty:
    if f_empresa: df_filtrado = df_filtrado[df_filtrado["Cliente"].isin(f_empresa)]
    if f_modelo: df_filtrado = df_filtrado[df_filtrado["Modelo"].isin(f_modelo)]
    if f_frota: df_filtrado = df_filtrado[df_filtrado["Frota"].isin(f_frota)]
    if f_comp: df_filtrado = df_filtrado[df_filtrado["Compartimento"].isin(f_comp)]
    if f_status: df_filtrado = df_filtrado[df_filtrado["Status"].isin(f_status)]

filtros_dinamicos = []
if st.session_state.filtro_frota_grafico:
    df_filtrado = df_filtrado[df_filtrado["Frota"].isin(st.session_state.filtro_frota_grafico)]
    filtros_dinamicos.append(f"Frotas: {', '.join(st.session_state.filtro_frota_grafico)}")
if st.session_state.filtro_status_grafico:
    df_filtrado = df_filtrado[df_filtrado["Status"].isin(st.session_state.filtro_status_grafico)]
    filtros_dinamicos.append(f"Status: {', '.join(st.session_state.filtro_status_grafico)}")
if st.session_state.filtro_comp_grafico:
    df_filtrado = df_filtrado[df_filtrado["Compartimento"].isin(st.session_state.filtro_comp_grafico)]
    filtros_dinamicos.append(f"Comps: {', '.join(st.session_state.filtro_comp_grafico)}")

if filtros_dinamicos:
    st.sidebar.info("🔍 **Filtros Ativos via Gráfico:**\n- " + "\n- ".join(filtros_dinamicos))
    if st.sidebar.button("❌ Limpar Seleção Gráfica"):
        st.session_state.filtro_frota_grafico = []
        st.session_state.filtro_status_grafico = []
        st.session_state.filtro_comp_grafico = []
        st.rerun()

st.sidebar.markdown("---")
opcao_menu = st.sidebar.radio(
    "Módulos do Portal:",
    [
        "📊 Dashboard Geral Interativo", 
        "📈 Séries Temporais & Variação",
        "🚨 Ranking de Bad Actors", 
        "🔬 Distribuição Estatística e Alarmes", 
        "🔥 Análise de Correlação (Spearman)",
        "📉 Curva de Sobrevivência (Weibull)", 
        "⚙️ Parametrização de Limites",
        "📥 Importar Novos Laudos (PDF)"
    ]
)

# ==============================================================================
# MÓDULOS DE VISUALIZAÇÃO
# ==============================================================================
if opcao_menu == "📊 Dashboard Geral Interativo":
    st.title("🚜 Dashboard Proativo de Análises de Óleo (Interativo)")
    
    if df_filtrado.empty:
        st.info("💡 Nenhuma análise encontrada com os filtros atuais.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total de Amostras", len(df_filtrado))
        k2.metric("Críticos", len(df_filtrado[df_filtrado["Status"] == "Crítico"]) if "Status" in df_filtrado.columns else 0)
        k3.metric("Monitorar", len(df_filtrado[df_filtrado["Status"] == "Monitorar"]) if "Status" in df_filtrado.columns else 0)
        k4.metric("Normais", len(df_filtrado[df_filtrado["Status"] == "Normal"]) if "Status" in df_filtrado.columns else 0)

        col1, col2 = st.columns(2)
        with col1:
            if "Status" in df_filtrado.columns:
                fig_status = px.bar(
                    df_filtrado["Status"].value_counts().reset_index(), 
                    x='Status', y='count', title="Distribuição de Criticidade (Selecione a barra)", 
                    text_auto=True, color='Status',
                    color_discrete_map={"Normal": "#10B981", "Monitorar": "#F59E0B", "Crítico": "#EF4444"}
                )
                evento_status = st.plotly_chart(fig_status, use_container_width=True, on_select="rerun")
                if evento_status and "selection" in evento_status and evento_status["selection"]["points"]:
                    pontos = [p["x"] for p in evento_status["selection"]["points"]]
                    st.session_state.filtro_status_grafico = pontos
                    st.rerun()
                    
        with col2:
            if "Compartimento" in df_filtrado.columns:
                fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento (Selecione a fatia)", hole=0.4)
                fig_comp.update_traces(textinfo='percent+label')
                evento_comp = st.plotly_chart(fig_comp, use_container_width=True, on_select="rerun")
                if evento_comp and "selection" in evento_comp and evento_comp["selection"]["points"]:
                    pontos = [p["label"] for p in evento_comp["selection"]["points"]]
                    st.session_state.filtro_comp_grafico = pontos
                    st.rerun()

        st.subheader("Base de Dados Completa")
        st.dataframe(
            df_filtrado,
            column_config={"Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir Documento PDF")},
            use_container_width=True
        )

elif opcao_menu == "📈 Séries Temporais & Variação":
    st.title("📈 Monitoramento Temporal: Comparativo Frota vs. Média do Modelo")
    if not df_filtrado.empty and "Data da Coleta" in df_filtrado.columns:
        
        df_temp = df_filtrado.copy()
        # Tratamento cronológico correto de datas
        df_temp['Data_Convertida'] = pd.to_datetime(df_temp['Data da Coleta'], format='%d-%b-%Y', errors='coerce')
        df_temp = df_temp.sort_values(by=["Modelo", "Frota", "Data_Convertida"]).dropna(subset=['Data_Convertida'])
        
        if not df_temp.empty:
            cols_numericas = ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "Horímetro Óleo", "Horímetro Equip", "OXI", "NIT", "SUL"]
            param_var = st.selectbox("Selecione o Parâmetro:", cols_numericas)
            
            df_media_modelo = df_temp.groupby(["Modelo", "Data_Convertida"])[param_var].mean().reset_index()

            fig_temp = px.line(df_temp, x="Data_Convertida", y=param_var, color="Frota", markers=True)
            fig_temp.update_xaxes(title="Data da Coleta", tickformat="%d/%m/%Y")
            
            for mod in df_temp["Modelo"].unique():
                df_m = df_media_modelo[df_media_modelo["Modelo"] == mod]
                fig_temp.add_trace(go.Scatter(
                    x=df_m["Data_Convertida"], y=df_m[param_var],
                    mode='lines', name=f'Média Modelo {mod}',
                    line=dict(dash='dash', width=3, color='black')
                ))
            
            st.plotly_chart(fig_temp, use_container_width=True)
            st.dataframe(df_temp.drop(columns=['Data_Convertida']), use_container_width=True)
        else:
            st.warning("⚠️ Não foi possível alinhar cronologicamente as datas.")

elif opcao_menu == "🔬 Distribuição Estatística e Alarmes":
    st.title("🔬 Distribuição Estatística e Identificação de Alarmes")
    
    df_normais = df_filtrado[df_filtrado["Status"] == "Normal"].copy()
    
    if df_normais.empty:
        st.warning("⚠️ Selecione filtros que contenham amostras 'Normal' para calcular a linha base populacional.")
    else:
        c1, c2 = st.columns(2)
        comp_sel = c1.selectbox("Selecione o Compartimento Base:", list(df_normais["Compartimento"].unique()))
        
        cols_opcoes = ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "OXI", "NIT", "SUL"]
        param = c2.selectbox("Selecione o Parâmetro de Desgaste:", cols_opcoes)
        
        df_comp_total = df_normais[df_normais["Compartimento"] == comp_sel]
        
        if not df_comp_total.empty and param in df_comp_total.columns:
            m_global = df_comp_total[param].mean()
            std_global = df_comp_total[param].std()

            st.markdown("---")
            k1, k2 = st.columns(2)
            k1.metric(f"Média Populacional $\mu$ ({comp_sel})", f"{m_global:.1f}")
            k2.metric(f"Desvio Padrão $\sigma$", f"{std_global:.1f}")

            # Gráfico do Histograma
            fig_limpo = px.histogram(
                df_comp_total, x=param, title=f"Limites Estatísticos de {param} ({comp_sel})", text_auto=True, opacity=0.8
            )
            fig_limpo.add_vline(x=m_global, line_dash="dash", line_color="black", annotation_text=f"$\mu$: {m_global:.1f}")
            fig_limpo.add_vline(x=m_global + std_global, line_dash="dot", line_color="#F59E0B", annotation_text="Alerta ($> \mu+1\sigma$)")
            fig_limpo.add_vline(x=m_global + 2*std_global, line_dash="dot", line_color="#EF4444", annotation_text="Crítico ($> \mu+2\sigma$)")
            st.plotly_chart(fig_limpo, use_container_width=True)

            # TABELA OBRIGATÓRIA DE AMOSTRAS ACIMA DOS LIMITES
            st.markdown("### ⚠️ Tabela de Amostras Que Romperam os Limites de Alarme")
            st.write("Identificação detalhada dos laudos que ultrapassaram a média + 1 desvio padrão:")
            
            limite_alerta = m_global + std_global
            df_alarmes = df_filtrado[(df_filtrado["Compartimento"] == comp_sel) & (df_filtrado[param] > limite_alerta)].copy()
            df_alarmes["Severidade"] = np.where(df_alarmes[param] > (m_global + 2*std_global), "🚨 Crítico (> 2σ)", "⚠️ Alerta (> 1σ)")
            
            df_alarmes = df_alarmes.sort_values(by=param, ascending=False)
            
            st.dataframe(
                df_alarmes[["Severidade", "Nº Controle Lab", "Frota", "Data da Coleta", param, "Status", "Link Laudo PDF"]],
                column_config={"Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir PDF")},
                use_container_width=True
            )

elif opcao_menu == "📉 Curva de Sobrevivência (Weibull)":
    st.title("📉 Curva de Sobrevivência (Weibull) com Cursor Móvel")
    if not df_filtrado.empty and "Horímetro Óleo" in df_filtrado.columns:
        s_horas = pd.to_numeric(df_filtrado["Horímetro Óleo"], errors='coerce').dropna()
        horas = np.unique(np.sort(s_horas[s_horas > 0].values))
        
        if len(horas) >= 3:
            n = len(horas)
            p = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
            y = np.log(-np.log(1 - p))
            x = np.log(horas)
            
            try:
                fit = np.polyfit(x, y, 1)
                beta = fit[0]
                eta = np.exp(-fit[1] / beta)
                df_w = pd.DataFrame({"Horímetro Óleo": horas, "Confiabilidade R(t)": np.exp(-(horas / eta)**beta)})
                fig_w = px.line(df_w, x="Horímetro Óleo", y="Confiabilidade R(t)", markers=True)
                fig_w.update_layout(hovermode="x unified")
                st.plotly_chart(fig_w, use_container_width=True)
            except Exception as e:
                st.warning("⚠️ Os valores de horímetro extraídos formam uma reta inválida matematicamente para Weibull.")
        else:
            st.warning("⚠️ Selecione equipamentos com pelo menos 3 amostras contendo horímetros de óleo ÚNICOS e maiores que zero.")

elif opcao_menu == "🔥 Análise de Correlação (Spearman)":
    st.title("🔥 Análise de Extensão da Vida do Óleo (Correlação de Spearman)")
    if not df_filtrado.empty:
        col_corr = ["Horímetro Óleo", "V100", "Fe", "Cu", "Si", "Al", "Cr", "H2O", "OXI", "NIT", "SUL"]
        col_existentes = [c for c in col_corr if c in df_filtrado.columns]
        df_corr = df_filtrado[col_existentes].dropna(subset=["Horímetro Óleo"])
        df_corr = df_corr[df_corr["Horímetro Óleo"] > 0]
        
        if not df_corr.empty and len(df_corr) > 3:
            matriz = df_corr.corr(method="spearman")
            fig_corr = px.imshow(matriz, text_auto=".2f", color_continuous_scale="RdBu_r")
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.warning("⚠️ É necessário histórico com Horímetro de Óleo preenchido (> 0) e variável para gerar a matriz.")

elif opcao_menu == "⚙️ Parametrização de Limites":
    st.title("⚙️ Parametrização de Limites Máximos em Massa por Modelo")
    
    tab1, tab2 = st.tabs(["✍️ Tabela Interativa Editável", "📥 Upload via Excel/CSV"])
    
    with tab1:
        df_para_edicao = df_limites.copy() if not df_limites.empty else pd.DataFrame(columns=["modelo", "fe_max", "cu_max", "si_max", "al_max", "cr_max", "v100_min", "v100_max"])
        df_editado = st.data_editor(df_para_edicao, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Salvar Alterações na Base", type="primary"):
            if salvar_limites_modelos_supabase(df_editado):
                st.success("✅ Limites atualizados no banco de dados!")
                st.rerun()

    with tab2:
        df_template = pd.DataFrame(columns=["modelo", "fe_max", "cu_max", "si_max", "al_max", "cr_max", "v100_min", "v100_max"])
        csv_template = df_template.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Tabela Modelo (CSV)", data=csv_template, file_name='template_limites_modelos.csv', mime='text/csv')
        
        uploaded_limites = st.file_uploader("Faça o Upload do Arquivo de Limites Preenchido", type=["csv", "xlsx"])
        if uploaded_limites:
            try:
                df_up_lim = pd.read_csv(uploaded_limites) if uploaded_limites.name.endswith('.csv') else pd.read_excel(uploaded_limites)
                if st.button("🚀 Gravar Planilha no Supabase", type="primary"):
                    if salvar_limites_modelos_supabase(df_up_lim):
                        st.success("✅ Planilha salva com sucesso no Supabase!")
                        st.rerun()
            except Exception as e:
                st.error(f"Erro na planilha: {e}")

elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Ingestão de Laudos e Correção Definitiva da Base")
    
    st.subheader("⚠️ LIMPEZA E REPROCESSAMENTO DO BANCO DE DADOS")
    if st.button("🚨 ZERAR BANCO DE DADOS ANTIGO PARA RE-UPLOAD", type="secondary"):
        if supabase:
            supabase.table("laudos_sos").delete().neq("controle_lab", "X_INVALIDO").execute()
            st.cache_data.clear()
            st.success("✅ O BANCO FOI ZERADO! Faça o upload dos PDFs abaixo.")
            st.rerun()

    st.markdown("---")
    st.subheader("Upload dos Arquivos PDF em Lote")
    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar e Gravar no Supabase", type="primary"):
            novos = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                novos.append(extrair_dados_pdf_fidedigno(BytesIO(pdf.read()), pdf.name))
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos)
            df_novos = df_novos.drop_duplicates(subset=["Nº Controle Lab"], keep="last")
            
            sucesso = salvar_laudos_supabase(df_novos)
            if sucesso:
                st.success(f"✅ {len(df_novos)} laudos extraídos e salvos!")
                st.dataframe(df_novos, use_container_width=True)

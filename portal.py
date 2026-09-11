import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
import inspect
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

def renderizar_grafico_seguro(fig, **kwargs):
    if "on_select" in inspect.signature(st.plotly_chart).parameters:
        return st.plotly_chart(fig, **kwargs)
    else:
        kwargs.pop("on_select", None)
        st.plotly_chart(fig, **kwargs)
        return None

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
# PERSISTÊNCIA DE DADOS
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
            
            df['Data_Convertida'] = pd.to_datetime(df['Data da Coleta'], format='%d-%b-%Y', errors='coerce')
            
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
        # Remove colunas auxiliares geradas pelo portal
        colunas_remover = ["Link Laudo PDF", "Data_Convertida"]
        for col in colunas_remover:
            if col in df_para_banco.columns:
                df_para_banco = df_para_banco.drop(columns=[col])
                
        df_para_banco = df_para_banco.drop_duplicates(subset=["controle_lab"], keep="last")
        registros = df_para_banco.to_dict(orient="records")
        supabase.table("laudos_sos").upsert(registros).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return False

# ==============================================================================
# LENTE OCR DE ALTA PRECISÃO (HORÍMETROS E METAIS)
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages: texto += page.extract_text() + "\n"

    filename_upper = filename.upper()
    texto_upper = texto.upper()
    texto_topo = texto_upper[:2000]

    # Modelo Exato
    mod_txt = re.search(r'MODELO[\s:]+(?!DO\b)([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if mod_txt and mod_txt.group(1).strip().upper() not in ["N", "LOCAL", "DE", "DO", "DA", "EQUIPAMENTO", ""]:
        modelo = mod_txt.group(1).strip().upper()
    else:
        mod_fallback = re.search(r'\b(SY[0-9]+[A-Z]*|SKT[0-9]+[A-Z]*|CAT\s*[0-9]+[A-Z]*|3[0-9]{2}[A-Z]*|D[6-9][A-Z]*|7[0-9]{2}[A-Z]*|9[0-9]{2}[A-Z]*|1[2-6][0-9][A-Z]*)\b', texto_topo, re.IGNORECASE)
        modelo = mod_fallback.group(1).strip().upper().replace(" ", "") if mod_fallback else "Geral"

    # Frota
    frota_txt = re.search(r'FROTA[\s:]+(?!DO\b)([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if frota_txt and frota_txt.group(1).strip().upper() not in ["N", "LOCAL", "DE", "DO", "DA", "EQUIPAMENTO", ""]:
        frota = frota_txt.group(1).strip().upper()
    else:
        frota_match = re.search(r'#([A-Z0-9]+)_', filename_upper)
        frota = frota_match.group(1).strip().upper() if frota_match and frota_match.group(1).strip().upper() not in ["N", "LOCAL"] else "Desconhecido"

    # Controle Numérico
    ctrl_m = re.search(r'\d{3}-\d{5}-\d{4}', texto)
    core_ctrl = ctrl_m.group(0) if ctrl_m else "000-00000-0000"
    controle = f"U{core_ctrl}" if ctrl_m else f"TEMP_{filename}"
    sufixo_ctrl = core_ctrl.split("-")[-1]

    # Compartimento
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

    # Status Seguro
    if "_AR.PDF" in filename_upper: status = "Crítico"
    elif "_MC.PDF" in filename_upper: status = "Monitorar"
    elif "_NAR.PDF" in filename_upper: status = "Normal"
    else:
        if "CRÍTICO" in texto_topo or "CRITICO" in texto_topo: status = "Crítico"
        elif "MONITORAR" in texto_topo or "ATENÇÃO" in texto_topo or "ATENCAO" in texto_topo: status = "Monitorar"
        else: status = "Normal"

    # Data Coleta
    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d-%b-%Y")

    elementos = {
        "Cu":0.0,"Fe":0.0,"Cr":0.0,"Al":0.0,"Pb":0.0,"Sn":0.0,"Si":0.0,"Na":0.0,"K":0.0,"B":0.0,"Mo":0.0,"Ni":0.0,"Ag":0.0,"Ti":0.0,"V":0.0,"Mn":0.0,"Ca":0.0,"Mg":0.0,"Zn":0.0,"P":0.0,"Ba":0.0,
        "V100":0.0,"H2O":0.0,"ISO4406_4u":0.0,"ISO4406_6u":0.0,"ISO4406_14u":0.0,
        "OXI":0.0,"NIT":0.0,"SUL":0.0,"W":"","TAN":0.0, "ISO_10u":0.0, "ISO_18u":0.0, "ISO_21u":0.0, "ISO_38u":0.0, "ISO_50u":0.0
    }

    hr_equip, hr_oleo = 0.0, 0.0
    linhas = texto.split('\n')
    idx_linhas = [i for i, l in enumerate(linhas) if core_ctrl in l]
    elementos_encontrados = False

    for idx in idx_linhas:
        # A CAÇADA AOS HORÍMETROS: Busca ampliada no bloco para evitar zeramento
        bloco_horas = " ".join(linhas[idx : idx+12])
        # Padrão flexível: Pega qualquer número seguido de HR ou KM
        horas_list = re.findall(r'(\d+[\.,]?\d*)\s*(?:HR|KM)', bloco_horas, re.IGNORECASE)
        if len(horas_list) >= 1 and hr_equip == 0.0: hr_equip = float(horas_list[0].replace(',', '.'))
        if len(horas_list) >= 2 and hr_oleo == 0.0: hr_oleo = float(horas_list[1].replace(',', '.'))

        # A CAÇADA AOS METAIS
        bloco_texto = " ".join(linhas[idx : idx+5])
        bloco_limpo = re.sub(r'[A-Za-z0-9]?\d{3}-\d{5}-\d{4}', ' ', bloco_texto)
        bloco_limpo = re.sub(rf'\b{sufixo_ctrl}\b', ' ', bloco_limpo)
        bloco_limpo = re.sub(r'\b202[0-9]\b', ' ', bloco_limpo) # Filtro Anti-Data
        bloco_limpo = re.sub(r'\d{2}-[a-zA-Z]{3}-\d{4}', ' ', bloco_limpo)
        
        nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_limpo)]
        nums_filtrados = [n for n in nums if n < 50000] 
        
        if len(nums_filtrados) >= 20 and not elementos_encontrados:
            keys_elem = ["Cu","Fe","Cr","Al","Pb","Sn","Si","Na","K","B","Mo","Ni","Ag","Ti","V","Mn","Ca","Mg","Zn","P","Ba"]
            for i_elem, k in enumerate(keys_elem):
                if i_elem < len(nums_filtrados): elementos[k] = nums_filtrados[i_elem]
            elementos_encontrados = True
            
        elif 3 <= len(nums_filtrados) < 20:
            w_match = re.search(r'\b([NPT])\b', bloco_limpo)
            if w_match: elementos["W"] = w_match.group(1)
            
            if len(nums_filtrados) >= 3:
                offset = 1 if "ST " in texto_upper else 0
                if len(nums_filtrados) > offset + 2:
                    elementos["OXI"] = nums_filtrados[offset]
                    elementos["NIT"] = nums_filtrados[offset+1]
                    elementos["SUL"] = nums_filtrados[offset+2]

    match_v100 = re.search(r'(?:V100|Viscosidade)[^\d]*([0-9]{2,3}\.[0-9]{1,2})', texto, re.IGNORECASE)
    if not match_v100: match_v100 = re.search(r'\b([0-9]{2,3}\.[0-9]{1,2})\b', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'H2O[^\d]*([0-9]\.[0-9]{2,4})', texto, re.IGNORECASE)
    if match_h2o: elementos["H2O"] = float(match_h2o.group(1))

    dados_finais = {
        "Data da Coleta": data_coleta, "Cliente": "3 SKAVAMINAS", "Modelo": modelo, "Frota": frota,
        "Compartimento": compartimento, "Status": status, "Horímetro Equip": hr_equip, "Horímetro Óleo": hr_oleo,
        "Nº Controle Lab": controle, "Nome do Arquivo PDF": filename
    }
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# RELATÓRIO EXECUTIVO EM PDF (INCLUI BAD ACTORS)
# ==============================================================================
def gerar_relatorio_pdf_executivo(df_dados):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#0F172A"))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#1E3A8A"))

    story.append(Paragraph("<b>RELATÓRIO DE CONFIABILIDADE DE FLUIDOS S•O•S</b>", title_style))
    story.append(Spacer(1, 10))

    if not df_dados.empty:
        total = len(df_dados)
        criticos = len(df_dados[df_dados["Status"] == "Crítico"])
        monit = len(df_dados[df_dados["Status"] == "Monitorar"])
        
        story.append(Paragraph("<b>1. Resumo da Frota (KPIs)</b>", sub_style))
        t_kpi = Table([["Total de Amostras", "Ação Imediata (Crítico)", "Monitoramento"], [str(total), str(criticos), str(monit)]])
        t_kpi.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E40AF")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
        story.append(t_kpi)
        story.append(Spacer(1, 15))

        df_crit = df_dados[df_dados["Status"].isin(["Crítico", "Monitorar"])]
        if not df_crit.empty:
            story.append(Paragraph("<b>2. Equipamentos em Alerta (Bad Actors)</b>", sub_style))
            bad = df_crit.groupby(["Frota", "Compartimento", "Status"]).size().reset_index(name="Falhas").sort_values(by="Falhas", ascending=False).head(10)
            bad_data = [["Frota", "Compartimento", "Status", "Qtd. Alertas"]]
            for _, r in bad.iterrows(): bad_data.append([str(r["Frota"]), str(r["Compartimento"]), str(r["Status"]), str(r["Falhas"])])
            
            t_bad = Table(bad_data)
            t_bad.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#991B1B")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
            story.append(t_bad)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# MENU LATERAL E FILTROS MÚLTIPLOS (CROSS-FILTERING)
# ==============================================================================
df_base = carregar_dados_base()
df_5w2h = carregar_plano_5w2h()
df_limites = carregar_limites_modelos()

st.sidebar.title("🛠️ Painel de Controle")

st.sidebar.subheader("📄 Relatório Executivo PDF")
pdf_bytes = gerar_relatorio_pdf_executivo(df_base)
st.sidebar.download_button(label="📥 EMITIR RELATÓRIO PDF", data=pdf_bytes, file_name=f"Relatorio_SOS_{datetime.now().strftime('%d%m%Y')}.pdf", mime="application/pdf")

st.sidebar.markdown("---")
st.sidebar.subheader("Filtros Globais (Múltiplos)")

def aplicar_filtros(df, coluna, selecao):
    if not selecao or "Todas" in selecao or "Todos" in selecao: return df
    return df[df[coluna].isin(selecao)]

opcoes_empresa = ["Todas"] + list(df_base["Cliente"].unique()) if not df_base.empty else []
f_empresa = st.sidebar.multiselect("Empresa / Cliente:", opcoes_empresa, default="Todas")

opcoes_modelo = ["Todos"] + list(df_base["Modelo"].unique()) if not df_base.empty else []
f_modelo = st.sidebar.multiselect("Modelo de Equipamento:", opcoes_modelo, default="Todos")

opcoes_frota = ["Todas"] + list(df_base["Frota"].unique()) if not df_base.empty else []
f_frota = st.sidebar.multiselect("Número de Frota:", opcoes_frota, default="Todas")

opcoes_comp = ["Todos"] + list(df_base["Compartimento"].unique()) if not df_base.empty else []
f_comp = st.sidebar.multiselect("Compartimento Analisado:", opcoes_comp, default="Todos")

opcoes_status = ["Todos"] + list(df_base["Status"].unique()) if not df_base.empty else []
f_status = st.sidebar.multiselect("Status da Amostra:", opcoes_status, default="Todos")

df_filtrado = df_base.copy()
if not df_filtrado.empty:
    df_filtrado = aplicar_filtros(df_filtrado, "Cliente", f_empresa)
    df_filtrado = aplicar_filtros(df_filtrado, "Modelo", f_modelo)
    df_filtrado = aplicar_filtros(df_filtrado, "Frota", f_frota)
    df_filtrado = aplicar_filtros(df_filtrado, "Compartimento", f_comp)
    df_filtrado = aplicar_filtros(df_filtrado, "Status", f_status)

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
        "🔍 RCA & Gestão do Plano 5W2H", 
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
                evento = renderizar_grafico_seguro(fig_status, use_container_width=True, on_select="rerun")
                if evento and "selection" in evento and evento["selection"]["points"]:
                    st.session_state.filtro_status_grafico = [p["x"] for p in evento["selection"]["points"]]
                    st.rerun()
                    
        with col2:
            if "Compartimento" in df_filtrado.columns:
                fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento (Selecione a fatia)", hole=0.4)
                fig_comp.update_traces(textinfo='percent+label')
                evento = renderizar_grafico_seguro(fig_comp, use_container_width=True, on_select="rerun")
                if evento and "selection" in evento and evento["selection"]["points"]:
                    st.session_state.filtro_comp_grafico = [p["label"] for p in evento["selection"]["points"]]
                    st.rerun()

        st.markdown("---")
        st.subheader("🔥 Mapa de Calor: Saúde Atual da Frota (Última Amostra)")
        if "Data_Convertida" in df_filtrado.columns:
            df_recente = df_filtrado.sort_values("Data_Convertida").groupby(["Frota", "Compartimento"]).tail(1)
            pivot_status = df_recente.pivot(index="Frota", columns="Compartimento", values="Status").fillna("-")
            
            def color_status(val):
                if val == 'Crítico': return 'background-color: #EF4444; color: white'
                elif val == 'Monitorar': return 'background-color: #F59E0B; color: white'
                elif val == 'Normal': return 'background-color: #10B981; color: white'
                return ''
                
            st.dataframe(pivot_status.style.map(color_status), use_container_width=True)

elif opcao_menu == "📈 Séries Temporais & Variação":
    st.title("📈 Monitoramento Temporal: Comparativo Frota vs. Média do Modelo")
    if not df_filtrado.empty and "Data_Convertida" in df_filtrado.columns:
        df_temp = df_filtrado.sort_values(by=["Modelo", "Frota", "Data_Convertida"]).dropna(subset=['Data_Convertida'])
        
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
                    mode='lines', name=f'Média {mod}',
                    line=dict(dash='dash', width=3, color='black')
                ))
            
            renderizar_grafico_seguro(fig_temp, use_container_width=True)

elif opcao_menu == "🚨 Ranking de Bad Actors":
    st.title("🚨 Ranking dos Piores Ativos (Bad Actors)")
    if not df_filtrado.empty and "Status" in df_filtrado.columns:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if criticos.empty:
            st.success("✅ Excelente! Não há ativos em estado Crítico ou Monitorar.")
        else:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            ordem = st.radio("Ordenação:", ["Maior para o Menor (Descendente)", "Menor para o Maior (Ascendente)"], horizontal=True)
            asc = True if "Menor para o Maior" in ordem else False
            totais_frota = bad_actors.groupby("Frota")["Ocorrências Críticas"].sum().sort_values(ascending=asc).index.tolist()

            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            fig_bad.update_xaxes(categoryorder='array', categoryarray=totais_frota)
            
            evento = renderizar_grafico_seguro(fig_bad, use_container_width=True, on_select="rerun")
            if evento and "selection" in evento and evento["selection"]["points"]:
                st.session_state.filtro_frota_grafico = [p["x"] for p in evento["selection"]["points"]]
                st.rerun()

            st.dataframe(bad_actors, use_container_width=True)

elif opcao_menu == "🔬 Distribuição Estatística e Alarmes":
    st.title("🔬 Distribuição Estatística Limpa e Alarmes")
    
    st.info("💡 A Média ($\mu$) e Desvio Padrão ($\sigma$) são calculados EXCLUSIVAMENTE com as amostras Normais do equipamento para garantir a pureza da linha base estatística.")
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhuma amostra na base com os filtros selecionados.")
    else:
        c1, c2 = st.columns(2)
        comp_sel = c1.selectbox("Selecione o Compartimento Base:", list(df_filtrado["Compartimento"].unique()))
        cols_opcoes = ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "OXI", "NIT", "SUL"]
        param = c2.selectbox("Selecione o Parâmetro de Desgaste:", cols_opcoes)
        
        # Isola os Normais para matemática
        df_comp_normal = df_filtrado[(df_filtrado["Compartimento"] == comp_sel) & (df_filtrado["Status"] == "Normal")]
        df_comp_todos = df_filtrado[df_filtrado["Compartimento"] == comp_sel].copy()
        
        if df_comp_normal.empty:
            st.error("⚠️ Não há amostras 'Normal' suficientes para este compartimento para criar uma linha base.")
        elif not df_comp_todos.empty and param in df_comp_todos.columns:
            m_global = df_comp_normal[param].mean()
            std_global = df_comp_normal[param].std()

            st.markdown("---")
            k1, k2 = st.columns(2)
            k1.metric(f"Média Populacional $\mu$ ({comp_sel})", f"{m_global:.1f}")
            k2.metric(f"Desvio Padrão $\sigma$", f"{std_global:.1f}")

            # Gráfico de barras simples em azul (Conforme pedido)
            fig_limpo = px.histogram(df_comp_todos, x=param, title=f"Distribuição de {param} ({comp_sel})", text_auto=True, opacity=0.8, color_discrete_sequence=['#3b82f6'])
            fig_limpo.add_vline(x=m_global, line_dash="dash", line_color="black", annotation_text=f"$\mu$: {m_global:.1f}")
            fig_limpo.add_vline(x=m_global + std_global, line_dash="dot", line_color="#F59E0B", annotation_text="Alerta ($> \mu+1\sigma$)")
            fig_limpo.add_vline(x=m_global + 2*std_global, line_dash="dot", line_color="#EF4444", annotation_text="Crítico ($> \mu+2\sigma$)")
            renderizar_grafico_seguro(fig_limpo, use_container_width=True)

            st.markdown("### ⚠️ Amostras Que Romperam os Limites de Alarme")
            limite_alerta = m_global + std_global
            df_alarmes = df_comp_todos[df_comp_todos[param] > limite_alerta].copy()
            
            if df_alarmes.empty:
                st.success("✅ Nenhuma amostra rompeu o alarme superior (> $\mu + 1\sigma$) para este parâmetro.")
            else:
                df_alarmes["Severidade"] = np.where(df_alarmes[param] > (m_global + 2*std_global), "🚨 Crítico (> 2σ)", "⚠️ Alerta (> 1σ)")
                df_alarmes = df_alarmes.sort_values(by=param, ascending=False)
                st.dataframe(
                    df_alarmes[["Severidade", "Nº Controle Lab", "Frota", "Data da Coleta", param, "Status", "Link Laudo PDF"]],
                    column_config={"Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir PDF")},
                    use_container_width=True
                )

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
            renderizar_grafico_seguro(fig_corr, use_container_width=True)
        else:
            st.warning("⚠️ Os horímetros não foram detectados ou são insuficientes. Retorne à aba de Ingestão e zere o banco antes de reenviar os PDFs.")

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
                renderizar_grafico_seguro(fig_w, use_container_width=True)
            except Exception:
                st.warning("⚠️ Regressão matemática inválida. Os horímetros lidos estão zerados ou corrompidos.")
        else:
            st.warning("⚠️ Dados insuficientes. Retorne à aba de Ingestão e zere o banco antes de reenviar os PDFs com o novo OCR ativo.")

elif opcao_menu == "🔍 RCA & Gestão do Plano 5W2H":
    st.title("🔍 RCA & Gestão de Ações 5W2H")
    tab1, tab2 = st.tabs(["📌 Criar Novo Plano 5W2H", "🔄 Reprogramar / Atualizar Status"])
    
    with tab1:
        st.dataframe(df_filtrado, use_container_width=True)
        if not df_filtrado.empty and "Nº Controle Lab" in df_filtrado.columns:
            amostras_opcoes = df_filtrado["Nº Controle Lab"].tolist()
            controle_sel = st.selectbox("Selecione a Amostra para Tratar:", amostras_opcoes)
            linha_amostra = df_filtrado[df_filtrado["Nº Controle Lab"] == controle_sel].iloc[0]

            with st.form("form_5w2h_novo"):
                f1, f2 = st.columns(2)
                what = f1.text_input("O Que Fazer (What):", value=f"Inspecionar {linha_amostra.get('Compartimento', '')}")
                why = f2.text_input("Por Que Fazer (Why):", value=f"Amostra {linha_amostra.get('Status', '')}")
                f3, f4, f5 = st.columns(3)
                where = f3.text_input("Onde (Where):", value=f"Frota {linha_amostra.get('Frota', '')}")
                when = f4.date_input("Prazo Limite (When):")
                who = f5.text_input("Responsável (Who):")
                f6, f7, f8 = st.columns(3)
                email_resp = f6.text_input("E-mail do Responsável:")
                how = f7.text_input("Como Fazer (How):")
                cost = f8.text_input("Custo (How Much):", value="R$ 0,00")
                
                if st.form_submit_button("🚨 REGISTRAR PLANO NO SUPABASE"):
                    novo_reg = {
                        "Data Registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Nº Controle Lab": controle_sel, "Frota": linha_amostra.get('Frota', ''),
                        "Modelo": linha_amostra.get('Modelo', ''), "Compartimento": linha_amostra.get('Compartimento', ''),
                        "Status Amostra": linha_amostra.get('Status', ''), "O Que (What)": what, "Por Que (Why)": why,
                        "Onde (Where)": where, "Quando / Prazo (When)": when.strftime("%d/%m/%Y"), "Quem / Responsável (Who)": who,
                        "E-mail Responsável": email_resp, "Como (How)": how, "Quanto Custa (How Much)": cost,
                        "Status Execução": "Em Andamento", "Histórico de Alterações": f"Criado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    }
                    salvar_5w2h_supabase(pd.DataFrame([novo_reg]))
                    st.success("✅ Plano gravado no banco de dados!")

    with tab2:
        if not df_5w2h.empty and "Nº Controle Lab" in df_5w2h.columns:
            planos_ids = df_5w2h["Nº Controle Lab"].tolist()
            plano_sel_id = st.selectbox("Selecione o Plano 5W2H para Modificar:", planos_ids)
            linha_plano = df_5w2h[df_5w2h["Nº Controle Lab"] == plano_sel_id].iloc[0]
            
            c_s1, c_s2 = st.columns(2)
            novo_status_exec = c_s1.selectbox("Status da Ação:", ["Em Andamento", "Concluído", "Atrasado", "Reprogramado"])
            motivo_justificativa = c_s2.text_input("Motivo da Alteração / Observação:")
            
            novo_prazo_str = None
            if novo_status_exec in ["Atrasado", "Reprogramado"]:
                novo_prazo_dt = st.date_input("Nova Data / Prazo Limite (When):")
                novo_prazo_str = novo_prazo_dt.strftime("%d/%m/%Y")
            
            if st.button("🔄 SALVAR ALTERAÇÃO NO SUPABASE", type="primary"):
                hist_ant = str(linha_plano.get("Histórico de Alterações", ""))
                sub_prazo = f" -> Novo Prazo: {novo_prazo_str}" if novo_prazo_str else ""
                novo_hist = f"{hist_ant} | [{datetime.now().strftime('%d/%m/%Y %H:%M')}] Status -> {novo_status_exec}{sub_prazo} (Motivo: {motivo_justificativa})"
                if atualizar_5w2h_status_prazo(plano_sel_id, novo_status_exec, novo_prazo_str, novo_hist):
                    st.success("✅ Plano reprogramado no Supabase!")
                    st.rerun()

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
    
    st.subheader("⚠️ LIMPEZA DO BANCO DE DADOS (Zerar Erros do Passado)")
    st.write("A base do Supabase contém os laudos antigos com Horímetros Zerados e 'Anos' no lugar dos metais. **Zere a base antes do novo upload!**")
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
                st.success(f"✅ {len(df_novos)} laudos extraídos e salvos limpos!")
                st.dataframe(df_novos, use_container_width=True)

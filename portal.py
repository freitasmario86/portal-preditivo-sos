import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# Importações para a Geração do Relatório PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Portal Preditivo e Preventivo - S•O•S",
    page_icon="🚜",
    layout="wide"
)

URL_PASTA_DRIVE = "https://drive.google.com/drive/u/0/folders/19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"

# Conexão Oficial com o Supabase
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ==============================================================================
# LEITURA E ESCRITA VIA SUPABASE
# ==============================================================================
@st.cache_data(ttl=10)
def carregar_dados_base():
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
                "nome_arquivo": "Nome do Arquivo PDF"
            })
            cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=10)
def carregar_plano_5w2h():
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
            "Nome do Arquivo PDF": "nome_arquivo"
        })
        registros = df_para_banco.to_dict(orient="records")
        supabase.table("laudos_sos").upsert(registros).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return False

def salvar_5w2h_supabase(df_5w2h):
    try:
        df_p = df_5w2h.rename(columns={
            "Nº Controle Lab": "controle_lab", "Data Registro": "data_registro",
            "Frota": "frota", "Modelo": "modelo", "Compartimento": "compartimento",
            "Status Amostra": "status_amostra", "O Que (What)": "what", "Por Que (Why)": "why",
            "Onde (Where)": "where", "Quando / Prazo (When)": "when_prazo",
            "Quem / Responsável (Who)": "who_resp", "E-mail Responsável": "email_resp",
            "Como (How)": "how", "Quanto Custa (How Much)": "how_much",
            "Status Execução": "status_execucao", "Histórico de Alterações": "historico"
        })
        if "id" in df_p.columns:
            df_p = df_p.drop(columns=["id"])
        registros = df_p.to_dict(orient="records")
        supabase.table("plano_5w2h").insert(registros).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao gravar 5W2H no Supabase: {e}")
        return False

if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados_base()

if "df_5w2h" not in st.session_state:
    st.session_state.df_5w2h = carregar_plano_5w2h()

df_base = st.session_state.df_base

# ==============================================================================
# GERADOR DE RELATÓRIO PDF EXECUTIVO
# ==============================================================================
def gerar_relatorio_pdf_completo(df_dados, df_planos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#0F172A"), spaceAfter=10)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#1E3A8A"), spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=12)

    story.append(Paragraph("<b>RELATÓRIO TÉCNICO DE ENGENHARIA DE CONFIABILIDADE S•O•S</b>", title_style))
    story.append(Paragraph(f"Data da Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Cliente: 3 SKAVAMINAS", body_style))
    story.append(Spacer(1, 10))

    total = len(df_dados)
    criticos = len(df_dados[df_dados["Status"] == "Crítico"]) if not df_dados.empty else 0
    monit = len(df_dados[df_dados["Status"] == "Monitorar"]) if not df_dados.empty else 0
    normais = len(df_dados[df_dados["Status"] == "Normal"]) if not df_dados.empty else 0

    story.append(Paragraph("<b>1. Indicadores Globais da Frota (KPIs)</b>", subtitle_style))
    kpi_table = Table([
        ["Total Amostras", "Críticos (Ação Imediata)", "Em Monitoramento", "Normais"],
        [str(total), str(criticos), str(monit), str(normais)]
    ], colWidths=[130, 140, 130, 130])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E40AF")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8"))
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>2. Ranking de Piores Ativos (Bad Actors)</b>", subtitle_style))
    if not df_dados.empty:
        df_crit = df_dados[df_dados["Status"].isin(["Crítico", "Monitorar"])]
        if not df_crit.empty:
            bad = df_crit.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Falhas").sort_values(by="Falhas", ascending=False).head(8)
            bad_data = [["Frota", "Modelo", "Compartimento", "Ocorrências Críticas"]]
            for _, r in bad.iterrows():
                bad_data.append([str(r["Frota"]), str(r["Modelo"]), str(r["Compartimento"]), str(r["Falhas"])])
            t_bad = Table(bad_data, colWidths=[100, 120, 210, 100])
            t_bad.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#991B1B")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]))
            story.append(t_bad)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>3. Avaliação Estatística de Metais e Condição</b>", subtitle_style))
    if not df_dados.empty:
        fe_med, fe_max = df_dados["Fe"].mean(), df_dados["Fe"].max() if "Fe" in df_dados.columns else (0,0)
        si_med, si_max = df_dados["Si"].mean(), df_dados["Si"].max() if "Si" in df_dados.columns else (0,0)
        v100_med = df_dados["V100"].mean() if "V100" in df_dados.columns else 0
        
        stat_data = [
            ["Parâmetro Químico", "Média Geral (ppm / cSt)", "Máximo Encontrado", "Status da População"],
            ["Ferro (Fe) - Desgaste", f"{fe_med:.1f} ppm", f"{fe_max:.1f} ppm", "Crítico" if fe_max > 100 else "Normal"],
            ["Silício (Si) - Poeira", f"{si_med:.1f} ppm", f"{si_max:.1f} ppm", "Atenção" if si_max > 30 else "Normal"],
            ["Viscosidade 100ºC (V100)", f"{v100_med:.1f} cSt", "-", "Estável"]
        ]
        t_stat = Table(stat_data, colWidths=[150, 130, 120, 130])
        t_stat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER')
        ]))
        story.append(t_stat)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>4. Plano de Ação 5W2H Cadastrado</b>", subtitle_style))
    if not df_planos.empty:
        p_data = [["Frota", "O Que Fazer (What)", "Responsável", "Prazo", "Status"]]
        for _, r in df_planos.head(8).iterrows():
            p_data.append([
                str(r.get("Frota", "")), str(r.get("O Que (What)", ""))[:35],
                str(r.get("Quem / Responsável (Who)", "")), str(r.get("Quando / Prazo (When)", "")),
                str(r.get("Status Execução", ""))
            ])
        t_p = Table(p_data, colWidths=[60, 200, 110, 70, 90])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#15803D")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER')
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("Nenhum plano 5W2H cadastrado para esta seleção.", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# PARSER EXTRAÇÃO SOTREQ / CATERPILLAR
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
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0, "ISO4406_4u": 0.0, "ISO4406_6u": 0.0, "ISO4406_14u": 0.0
    }

    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if controle in linha:
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
# MENU LATERAL
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

st.sidebar.subheader("📄 Relatório Executivo PDF")
pdf_bytes = gerar_relatorio_pdf_completo(st.session_state.df_base, st.session_state.df_5w2h)
st.sidebar.download_button(
    label="📥 EMITIR RELATÓRIO PDF COMPLETO",
    data=pdf_bytes,
    file_name=f"Relatorio_Executivo_SOS_{datetime.now().strftime('%d%m%Y')}.pdf",
    mime="application/pdf"
)

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
        "📈 Séries Temporais de Elementos & ISO",
        "🚨 Ranking de Bad Actors", 
        "🔬 Distribuição Estatística Quimica", 
        "📉 Curva de Sobrevivência Interativa", 
        "🔍 RCA & Gestão 5W2H", 
        "📥 Importar Novos Laudos (PDF)"
    ]
)

# ==============================================================================
# MÓDULOS DO PORTAL
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
            fig_status = px.bar(df_filtrado["Status"].value_counts().reset_index(), x='Status', y='count', title="Distribuição de Criticidade", text_auto=True, color='Status')
            st.plotly_chart(fig_status, use_container_width=True)
        with col2:
            fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento", hole=0.4)
            fig_comp.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_comp, use_container_width=True)

        st.subheader("Base de Dados Carregada do Supabase")
        st.dataframe(df_filtrado, use_container_width=True)

elif opcao_menu == "📈 Séries Temporais de Elementos & ISO":
    st.title("📈 Monitoramento Temporal de Elementos, Condição & ISO 4406")
    if not df_filtrado.empty:
        df_temp = df_filtrado.sort_values(by="Data da Coleta")
        elem_selecionado = st.multiselect(
            "Selecione os Parâmetros Químicos / Contagem ISO 4406 para Analisar:",
            ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u"],
            default=["Fe", "Si", "V100"]
        )
        if elem_selecionado:
            fig_temp = px.line(df_temp, x="Data da Coleta", y=elem_selecionado, color="Frota", markers=True)
            st.plotly_chart(fig_temp, use_container_width=True)
        st.dataframe(df_temp, use_container_width=True)

elif opcao_menu == "🚨 Ranking de Bad Actors":
    st.title("🚨 Ranking de Piores Ativos (Bad Actors)")
    if not df_filtrado.empty:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            ordem = st.radio("Ordenação:", ["Maior para o Menor (Descendente)", "Menor para o Maior (Ascendente)"], horizontal=True)
            asc = True if "Menor para o Maior" in ordem else False
            bad_actors = bad_actors.sort_values(by="Ocorrências Críticas", ascending=asc)
            fig_bad = px.bar(bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True)
            st.plotly_chart(fig_bad, use_container_width=True)
            st.dataframe(bad_actors, use_container_width=True)

elif opcao_menu == "🔬 Distribuição Estatística Quimica":
    st.title("🔬 Distribuição Estatística: Frota Selecionada vs. Compartimento Global")
    if not df_base.empty:
        c1, c2 = st.columns(2)
        comp_sel = c1.selectbox("Selecione o Compartimento para Benchmark Global:", list(df_base["Compartimento"].unique()))
        param = c2.selectbox("Selecione o Elemento Químico / Propriedade:", ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O"])
        
        df_comp_total = df_base[df_base["Compartimento"] == comp_sel]
        frotas_comp = list(df_comp_total["Frota"].unique())
        frota_sel = st.selectbox("Selecione a Frota Específica para Comparar:", frotas_comp)
        df_frota_especifica = df_comp_total[df_comp_total["Frota"] == frota_sel]

        if not df_comp_total.empty and not df_frota_especifica.empty:
            m_global = df_comp_total[param].mean()
            m_frota = df_frota_especifica[param].mean()

            st.markdown("---")
            k1, k2 = st.columns(2)
            k1.metric(f"Média {param} (Compartimento Global: {comp_sel})", f"{m_global:.1f} ppm")
            k2.metric(f"Média {param} (Frota {frota_sel})", f"{m_frota:.1f} ppm", delta=f"{m_frota - m_global:.1f} ppm vs Global")

            fig_comp = px.histogram(
                df_comp_total, x=param, color="Frota", barmode="overlay",
                title=f"Distribuição de {param}: Frota {frota_sel} x Demais Frotas ({comp_sel})",
                marginal="box", text_auto=True
            )
            fig_comp.add_vline(x=m_global, line_dash="dash", line_color="red", annotation_text=f"Média Global: {m_global:.1f}")
            st.plotly_chart(fig_comp, use_container_width=True)

elif opcao_menu == "📉 Curva de Sobrevivência Interativa":
    st.title("📉 Curva de Sobrevivência (Weibull) com Cursor Móvel")
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
            fig_w = px.line(df_w, x="Horímetro Óleo", y="Confiabilidade R(t)", markers=True)
            fig_w.update_layout(hovermode="x unified")
            st.plotly_chart(fig_w, use_container_width=True)

elif opcao_menu == "🔍 RCA & Gestão 5W2H":
    st.title("🔍 RCA & Gestão de Ações 5W2H")
    st.dataframe(df_filtrado, use_container_width=True)
    st.markdown("---")
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
            
            if st.form_submit_button("🚨 REGISTRAR PLANO 5W2H NO SUPABASE"):
                novo_reg = {
                    "Data Registro": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Nº Controle Lab": controle_sel,
                    "Frota": linha_amostra['Frota'], "Modelo": linha_amostra['Modelo'],
                    "Compartimento": linha_amostra['Compartimento'], "Status Amostra": linha_amostra['Status'],
                    "O Que (What)": what, "Por Que (Why)": why, "Onde (Where)": where,
                    "Quando / Prazo (When)": when.strftime("%d/%m/%Y"),
                    "Quem / Responsável (Who)": who, "E-mail Responsável": email_resp,
                    "Como (How)": how, "Quanto Custa (How Much)": cost,
                    "Status Execução": "Em Andamento", "Histórico de Alterações": f"Criado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                }
                salvar_5w2h_supabase(pd.DataFrame([novo_reg]))
                st.success("✅ Plano 5W2H gravado no banco de dados Supabase!")

        st.markdown("---")
        st.subheader("3. Histórico de Planos 5W2H Cadastrados")
        st.dataframe(st.session_state.df_5w2h, use_container_width=True)

elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Ingestão de Laudos e Gravação no Supabase")
    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar e Gravar no Supabase", type="primary"):
            novos = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                novos.append(extrair_dados_pdf_fidedigno(BytesIO(pdf.read()), pdf.name))
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos)
            sucesso = salvar_laudos_supabase(df_novos)
            if sucesso:
                st.success(f"✅ {len(df_novos)} laudos salvos e persistidos com sucesso no Supabase!")
            st.dataframe(df_novos, use_container_width=True)

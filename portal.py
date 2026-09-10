import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

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

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1hnntl9LfTqvPabewBU3PnNuZezREWi-3A5lmUM9GEwY/edit"
URL_PASTA_DRIVE = "https://drive.google.com/drive/u/0/folders/19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==============================================================================
# CARREGAMENTO DA BASE
# ==============================================================================
@st.cache_data(ttl=30)
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

if "df_base" not in st.session_state:
    st.session_state.df_base = carregar_dados_base()

if "df_5w2h" not in st.session_state:
    st.session_state.df_5w2h = pd.DataFrame(columns=[
        "Data Registro", "Nº Controle Lab", "Frota", "Modelo", "Compartimento", 
        "Status Amostra", "O Que (What)", "Por Que (Why)", "Onde (Where)", 
        "Quando / Prazo (When)", "Quem / Responsável (Who)", "E-mail Responsável", 
        "Como (How)", "Quanto Custa (How Much)", "Status Execução", "Histórico de Alterações"
    ])

df_base = st.session_state.df_base

# ==============================================================================
# GERADOR DE RELATÓRIO PDF EXECUTIVO
# ==============================================================================
def gerar_relatorio_pdf_gerencial(df_dados, df_planos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#1E3A8A"), spaceAfter=12)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor("#1F2937"), spaceAfter=8)
    normal_style = styles['Normal']

    # Cabeçalho
    story.append(Paragraph("<b>PORTAL DE ENGENHARIA DE CONFIABILIDADE & ANALISE DE OLEO S•O•S</b>", title_style))
    story.append(Paragraph(f"Data de Emissao: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
    story.append(Spacer(1, 15))

    # Resumo Geral
    story.append(Paragraph("1. Resumo Executivo da Frota", subtitle_style))
    total_amostras = len(df_dados)
    criticos = len(df_dados[df_dados["Status"] == "Crítico"]) if not df_dados.empty else 0
    monitorar = len(df_dados[df_dados["Status"] == "Monitorar"]) if not df_dados.empty else 0
    normais = len(df_dados[df_dados["Status"] == "Normal"]) if not df_dados.empty else 0

    kpi_data = [
        ["Total de Amostras", "Equipamentos Criticos", "Em Monitoramento", "Status Normal"],
        [str(total_amostras), str(criticos), str(monitorar), str(normais)]
    ]
    t_kpi = Table(kpi_data, colWidths=[130, 130, 130, 130])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 15))

    # Tabela das ultimas amostras criticas
    story.append(Paragraph("2. Amostras Criticas Recentes", subtitle_style))
    if not df_dados.empty:
        df_crit = df_dados[df_dados["Status"].isin(["Crítico", "Monitorar"])].head(10)
        if not df_crit.empty:
            dados_crit = [["Data", "Frota", "Modelo", "Compartimento", "Fe", "Si", "Status"]]
            for _, r in df_crit.iterrows():
                dados_crit.append([
                    str(r.get("Data da Coleta", "")), str(r.get("Frota", "")),
                    str(r.get("Modelo", "")), str(r.get("Compartimento", "")),
                    str(r.get("Fe", 0)), str(r.get("Si", 0)), str(r.get("Status", ""))
                ])
            t_crit = Table(dados_crit, colWidths=[70, 70, 80, 120, 50, 50, 80])
            t_crit.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]))
            story.append(t_crit)
        else:
            story.append(Paragraph("Nenhuma amostra critica registrada.", normal_style))
    story.append(Spacer(1, 15))

    # Plano 5W2H
    story.append(Paragraph("3. Plano de Acao 5W2H e Acompanhamento", subtitle_style))
    if not df_planos.empty:
        dados_p = [["Frota", "O Que (What)", "Responsavel", "Prazo", "Status"]]
        for _, r in df_planos.head(10).iterrows():
            dados_p.append([
                str(r.get("Frota", "")), str(r.get("O Que (What)", ""))[:30],
                str(r.get("Quem / Responsável (Who)", "")), str(r.get("Quando / Prazo (When)", "")),
                str(r.get("Status Execução", ""))
            ])
        t_plan = Table(dados_p, colWidths=[70, 180, 100, 80, 90])
        t_plan.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#059669")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER')
        ]))
        story.append(t_plan)
    else:
        story.append(Paragraph("Nenhum plano 5W2H cadastrado.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# PARSER EXTRAÇÃO DE LAUDOS
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
        "Link Laudo PDF": URL_PASTA_DRIVE,
        "Nome do Arquivo PDF": filename
    }
    dados_finais.update(elementos)
    return dados_finais

# ==============================================================================
# MENU LATERAL
# ==============================================================================
st.sidebar.title("🛠️ Painel de Controle")

# Botão para Download do Relatório Gerencial em PDF
st.sidebar.subheader("📄 Emissão de Relatório")
pdf_bytes = gerar_relatorio_pdf_gerencial(st.session_state.df_base, st.session_state.df_5w2h)
st.sidebar.download_button(
    label="📥 EMITIR RELATÓRIO PDF COMPLETO",
    data=pdf_bytes,
    file_name=f"Relatorio_Preditiva_SOS_{datetime.now().strftime('%d%m%Y')}.pdf",
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
# MÓDULOS DE VISUALIZAÇÃO
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

        st.subheader("Registros Salvos no Banco de Dados")
        st.dataframe(df_filtrado, use_container_width=True)

        # Botão para Download dos Dados em CSV
        csv_base = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Exportar Base Consolidada (CSV)", data=csv_base, file_name="base_laudos.csv", mime="text/csv")

elif opcao_menu == "📈 Séries Temporais de Elementos & ISO":
    st.title("📈 Monitoramento Temporal de Elementos, Condição & ISO 4406")
    if not df_filtrado.empty:
        df_temp = df_filtrado.sort_values(by="Data da Coleta")
        elem_selecionado = st.multiselect(
            "Selecione os Parâmetros Químicos para Analisar:",
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
    st.title("🔬 Distribuição Estatística para Elementos e Condição do Óleo")
    if not df_filtrado.empty:
        param = st.selectbox("Selecione o Elemento Químico:", ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O"])
        val_param = df_filtrado[param].dropna()
        media = val_param.mean()
        std = val_param.std() if val_param.std() > 0 else 1.0
        fig_hist = px.histogram(df_filtrado, x=param, nbins=15, marginal="box", text_auto=True)
        fig_hist.add_vline(x=media, line_dash="dash", line_color="green", annotation_text=f"Média: {media:.1f}")
        st.plotly_chart(fig_hist, use_container_width=True)
        st.dataframe(df_filtrado[["Frota", "Modelo", "Compartimento", param, "Status"]], use_container_width=True)

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
            
            if st.form_submit_button("🚨 REGISTRAR PLANO 5W2H"):
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
                st.session_state.df_5w2h = pd.concat([st.session_state.df_5w2h, pd.DataFrame([novo_reg])], ignore_index=True)
                st.success("✅ Plano 5W2H registrado na sessão!")

        st.markdown("---")
        st.subheader("3. Gestão e Acompanhamento do 5W2H")
        st.dataframe(st.session_state.df_5w2h, use_container_width=True)

elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Processamento de Laudos em PDF")
    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar e Atualizar Base", type="primary"):
            novos = []
            bar = st.progress(0)
            for idx, pdf in enumerate(uploaded_files):
                novos.append(extrair_dados_pdf_fidedigno(BytesIO(pdf.read()), pdf.name))
                bar.progress((idx + 1) / len(uploaded_files))

            df_novos = pd.DataFrame(novos)
            st.session_state.df_base = pd.concat([st.session_state.df_base, df_novos], ignore_index=True).drop_duplicates(subset=["Nº Controle Lab"], keep="last")
            st.success("✅ Laudos processados e salvos com sucesso na memória do portal!")
            st.dataframe(df_novos, use_container_width=True)

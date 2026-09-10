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
# CONFIGURAÇÃO DA PÁGINA E ESTADOS
# ==============================================================================
st.set_page_config(
    page_title="Portal Preditivo e Preventivo - S•O•S",
    page_icon="🚜",
    layout="wide"
)

URL_PASTA_DRIVE = "https://drive.google.com/drive/u/0/folders/19neodq1Ug0MJDd4mnqyBiWWmTQGuP_sw"

if "filtro_frota_grafico" not in st.session_state:
    st.session_state.filtro_frota_grafico = None

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
# PERSISTÊNCIA DE DADOS SUPABASE
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
                "nome_arquivo": "Nome do Arquivo PDF"
            })
            cols_num = ["Horímetro Equip", "Horímetro Óleo", "Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba", "V100", "H2O", "ISO4406_4u", "ISO4406_6u", "ISO4406_14u"]
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

df_base = carregar_dados_base()
df_5w2h = carregar_plano_5w2h()
df_limites = carregar_limites_modelos()

# ==============================================================================
# PARSER CORRIGIDO - BLINDAGEM DA TABELA DE METAIS E REMOÇÃO DE HISTÓRICO
# ==============================================================================
def extrair_dados_pdf_fidedigno(file_bytes, filename):
    reader = pypdf.PdfReader(file_bytes)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    filename_upper = filename.upper()
    texto_upper = texto.upper()

    mod_comercial = re.search(r'MODELO\s*:\s*([A-Z0-9\-_]+)', texto, re.IGNORECASE)
    if mod_comercial and not re.match(r'^[0-9]{3}$', mod_comercial.group(1).strip()):
        modelo = mod_comercial.group(1).strip()
    else:
        mod_tag = re.search(r'(SY[0-9A-Z]+LR|SKT[0-9A-Z]+S?|CAT[0-9A-Z]+|777[A-Z]?|D[8-9][R-T]?)', filename_upper)
        modelo = mod_tag.group(1).strip() if mod_tag else "Geral"

    frota_txt = re.search(r'NÚMERO DE FROTA\s*:\s*([A-Z0-9]+)', texto, re.IGNORECASE)
    if frota_txt and frota_txt.group(1).strip().upper() not in ["LOCAL", "N"]:
        frota = frota_txt.group(1).strip()
    else:
        frota_match = re.search(r'#([A-Z0-9]+)_', filename)
        frota = frota_match.group(1).strip() if frota_match else "Desconhecido"

    ctrl_m = re.search(r'U\d{3}-\d{5}-\d{4}', texto)
    controle = ctrl_m.group(0) if ctrl_m else f"TEMP_{filename}"

    mapa_comp = {
        'FD_LT': 'COMANDO F ESQ', 'FD_RT': 'COMANDO F DIR', 'SW_DR': 'COMANDO GIRO',
        'ENG': 'MOTOR', 'HS': 'SISTEMA HIDRAULICO', 'DIFF_FR': 'DIFERENCIAL DIANT',
        'TR': 'TRANSMISSAO', 'RA': 'RADIADOR', 'AX_CE': 'EIXO CENTRAL', 'AX_RR': 'EIXO TRASEIRO'
    }
    compartimento = "Outros"
    for k, v in mapa_comp.items():
        if f"_{k}_" in filename_upper or k in texto_upper:
            compartimento = v
            break

    if "_AR.PDF" in filename_upper or "CRÍTICO" in texto_upper or "CRITICO" in texto_upper:
        status = "Crítico"
    elif "_MC.PDF" in filename_upper or "MONITORAR" in texto_upper or "ATENÇÃO" in texto_upper or "ATENCAO" in texto_upper:
        status = "Monitorar"
    elif "_NAR.PDF" in filename_upper or "NORMAL" in texto_upper:
        status = "Normal"
    else:
        status = "Normal"

    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    data_coleta = data_match.group(1) if data_match else datetime.now().strftime("%d/%m/%Y")

    hrs_equip_match = re.search(r'HRS/KM EQUIP\s*([0-9\.,]+)', texto)
    hr_equip = float(hrs_equip_match.group(1).replace(',', '.')) if hrs_equip_match else 0.0

    hrs_oleo_match = re.search(r'HRS/KM ÓLEO\s*([0-9\.,]+)', texto)
    hr_oleo = float(hrs_oleo_match.group(1).replace(',', '.')) if hrs_oleo_match else 0.0

    elementos = {
        "Cu": 0.0, "Fe": 0.0, "Cr": 0.0, "Al": 0.0, "Pb": 0.0, "Sn": 0.0, "Si": 0.0,
        "Na": 0.0, "K": 0.0, "B": 0.0, "Mo": 0.0, "Ni": 0.0, "Ag": 0.0, "Ti": 0.0,
        "V": 0.0, "Mn": 0.0, "Ca": 0.0, "Mg": 0.0, "Zn": 0.0, "P": 0.0, "Ba": 0.0,
        "V100": 0.0, "H2O": 0.0, "ISO4406_4u": 0.0, "ISO4406_6u": 0.0, "ISO4406_14u": 0.0
    }

    linhas = texto.split('\n')
    elementos_encontrados = False
    
    for i, linha in enumerate(linhas):
        # A trava 'not elementos_encontrados' impede que ele leia a tabela de Condições debaixo
        if controle in linha and not elementos_encontrados:
            bloco_texto = " ".join(linhas[i:i+3])
            
            # Limpeza Absoluta: Remove qualquer código de controle da linha para não ser lido como metal
            bloco_limpo = re.sub(r'[A-Za-z]?\d{3}-\d{5}-\d{4}', ' ', bloco_texto)
            
            # Extrai os números
            nums = [float(n) for n in re.findall(r'\b\d+\b', bloco_limpo)]
            
            # A tabela de metais possui 21 colunas.
            if len(nums) >= 20:
                # Filtragem de segurança: Remove números absurdos que possam ter passado
                nums_filtrados = [n for n in nums if n < 50000]
                
                keys_elem = ["Cu", "Fe", "Cr", "Al", "Pb", "Sn", "Si", "Na", "K", "B", "Mo", "Ni", "Ag", "Ti", "V", "Mn", "Ca", "Mg", "Zn", "P", "Ba"]
                for idx, k in enumerate(keys_elem):
                    if idx < len(nums_filtrados): 
                        elementos[k] = nums_filtrados[idx]
                        
                elementos_encontrados = True  # TRAVA DE SUCESSO: Trava o loop para não sobrescrever

    match_v100 = re.search(r'V100\s*([0-9]{2}\.[0-9]{1,2})', texto)
    if match_v100: elementos["V100"] = float(match_v100.group(1))

    match_h2o = re.search(r'H2O\s*([0-9]\.[0-9]{2,4})', texto)
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
# MENU LATERAL E FILTROS
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
    if f_empresa != "Todas" and "Cliente" in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado["Cliente"] == f_empresa]
    if f_modelo != "Todos" and "Modelo" in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado["Modelo"] == f_modelo]
    if f_frota != "Todas" and "Frota" in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado["Frota"] == f_frota]
    if f_comp != "Todos" and "Compartimento" in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado["Compartimento"] == f_comp]

if st.session_state.filtro_frota_grafico:
    st.info(f"🔍 Filtro Interativo Ativo via Gráfico: Frota **{st.session_state.filtro_frota_grafico}**")
    if st.button("❌ Limpar Filtro do Gráfico"):
        st.session_state.filtro_frota_grafico = None
        st.rerun()
    df_filtrado = df_filtrado[df_filtrado["Frota"] == st.session_state.filtro_frota_grafico]

st.sidebar.markdown("---")
opcao_menu = st.sidebar.radio(
    "Módulos do Portal:",
    [
        "📊 Dashboard Geral Interativo", 
        "📈 Séries Temporais & Variação Modelo",
        "🚨 Ranking de Bad Actors Ordenado", 
        "🔬 Distribuição Estatística (Apenas Normais)", 
        "📥 Importar Novos Laudos (PDF)"
    ]
)

# ==============================================================================
# MÓDULOS DE VISUALIZAÇÃO
# ==============================================================================
if opcao_menu == "📊 Dashboard Geral Interativo":
    st.title("🚜 Dashboard Proativo de Análises de Óleo")
    
    if df_filtrado.empty:
        st.info("💡 Nenhuma análise encontrada na base. Acesse **'📥 Importar Novos Laudos (PDF)'**.")
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
                    df_filtrado["Status"].value_counts().reset_index(), x='Status', y='count', 
                    title="Distribuição de Criticidade", text_auto=True, color='Status',
                    color_discrete_map={"Normal": "#10B981", "Monitorar": "#F59E0B", "Crítico": "#EF4444"}
                )
                st.plotly_chart(fig_status, use_container_width=True)
        with col2:
            if "Compartimento" in df_filtrado.columns:
                fig_comp = px.pie(df_filtrado, names="Compartimento", title="Amostras por Compartimento", hole=0.4)
                fig_comp.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_comp, use_container_width=True)

        st.subheader("Base de Dados Completa (Clique no link para abrir o Laudo PDF)")
        st.dataframe(
            df_filtrado,
            column_config={
                "Link Laudo PDF": st.column_config.LinkColumn("Laudo PDF", display_text="📄 Abrir Documento PDF")
            },
            use_container_width=True
        )

elif opcao_menu == "🔬 Distribuição Estatística (Apenas Normais)":
    st.title("🔬 Distribuição Estatística Populacional (Estritamente Amostras Normais)")
    
    df_normais = df_base[df_base["Status"] == "Normal"].copy()
    
    if df_normais.empty:
        st.warning("⚠️ Nenhuma amostra com status 'Normal' encontrada na base.")
    else:
        c1, c2 = st.columns(2)
        comp_sel = c1.selectbox("Selecione o Compartimento:", list(df_normais["Compartimento"].unique()))
        param = c2.selectbox("Selecione o Parâmetro:", ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O"])
        
        df_comp_total = df_normais[df_normais["Compartimento"] == comp_sel]
        frotas_comp = list(df_comp_total["Frota"].unique()) if "Frota" in df_comp_total.columns else []
        
        if frotas_comp:
            frota_sel = st.selectbox("Comparar com Frota:", frotas_comp)
            df_frota_especifica = df_comp_total[df_comp_total["Frota"] == frota_sel]

            if not df_comp_total.empty and param in df_comp_total.columns:
                m_global = df_comp_total[param].mean()
                std_global = df_comp_total[param].std()
                m_frota = df_frota_especifica[param].mean() if not df_frota_especifica.empty else 0

                st.markdown("---")
                k1, k2, k3 = st.columns(3)
                k1.metric(f"Média Normal ({comp_sel})", f"{m_global:.1f} ppm")
                k2.metric(f"Média Frota {frota_sel}", f"{m_frota:.1f} ppm", delta=f"{m_frota - m_global:.1f} ppm")
                k3.metric("Desvio Padrão Global (σ)", f"{std_global:.1f}")

                df_comp_total["Grupo_Comparacao"] = np.where(df_comp_total["Frota"] == frota_sel, f"Frota {frota_sel}", "Outras Frotas")

                fig_limpo = px.histogram(
                    df_comp_total, x=param, color="Grupo_Comparacao", barmode="overlay",
                    title=f"Distribuição Normal de {param}", text_auto=True, opacity=0.75
                )
                fig_limpo.add_vline(x=m_global, line_dash="dash", line_color="black")
                st.plotly_chart(fig_limpo, use_container_width=True)

elif opcao_menu == "🚨 Ranking de Bad Actors Ordenado":
    st.title("🚨 Ranking dos Piores Ativos (Bad Actors)")
    if not df_filtrado.empty and "Status" in df_filtrado.columns:
        criticos = df_filtrado[df_filtrado["Status"].isin(["Crítico", "Monitorar"])]
        if not criticos.empty:
            bad_actors = criticos.groupby(["Frota", "Modelo", "Compartimento"]).size().reset_index(name="Ocorrências Críticas")
            ordem = st.radio("Ordenação:", ["Maior para o Menor (Descendente)", "Menor para o Maior (Ascendente)"], horizontal=True)
            asc = True if "Menor para o Maior" in ordem else False
            totais_frota = bad_actors.groupby("Frota")["Ocorrências Críticas"].sum().sort_values(ascending=asc).index.tolist()

            fig_bad = px.bar(
                bad_actors, x="Frota", y="Ocorrências Críticas", color="Compartimento", text_auto=True
            )
            fig_bad.update_xaxes(categoryorder='array', categoryarray=totais_frota)
            
            evento_clique = st.plotly_chart(fig_bad, use_container_width=True, on_select="rerun")
            if evento_clique and "selection" in evento_clique and evento_clique["selection"]["points"]:
                st.session_state.filtro_frota_grafico = evento_clique["selection"]["points"][0]["x"]
                st.rerun()

            st.dataframe(bad_actors, use_container_width=True)

elif opcao_menu == "📈 Séries Temporais & Variação Modelo":
    st.title("📈 Monitoramento Temporal: Comparativo Frota vs. Média do Modelo")
    if not df_filtrado.empty and "Data da Coleta" in df_filtrado.columns:
        df_temp = df_filtrado.sort_values(by=["Modelo", "Frota", "Data da Coleta"]).copy()
        param_var = st.selectbox("Selecione o Parâmetro:", ["Fe", "Cu", "Si", "Al", "Cr", "V100", "H2O"])
        
        df_media_modelo = df_temp.groupby(["Modelo", "Data da Coleta"])[param_var].mean().reset_index()

        fig_temp = px.line(df_temp, x="Data da Coleta", y=param_var, color="Frota", markers=True)
        for mod in df_temp["Modelo"].unique():
            df_m = df_media_modelo[df_media_modelo["Modelo"] == mod]
            fig_temp.add_trace(go.Scatter(
                x=df_m["Data da Coleta"], y=df_m[param_var], mode='lines', name=f'Média {mod}', line=dict(dash='dash', width=3, color='black')
            ))
        
        st.plotly_chart(fig_temp, use_container_width=True)
        st.dataframe(df_temp, use_container_width=True)

elif opcao_menu == "📥 Importar Novos Laudos (PDF)":
    st.title("📥 Ingestão de Laudos e Correção Definitiva da Base")
    
    st.subheader("⚠️ PASSO 1 OBRIGATÓRIO: Apagar os laudos com erros")
    st.write("A base do Supabase está com os laudos antigos salvos de forma errada. Clique no botão vermelho abaixo ANTES de fazer o upload.")
    
    if st.button("🚨 ZERAR BANCO DE DADOS ANTIGO PARA RE-UPLOAD", type="secondary"):
        if supabase:
            supabase.table("laudos_sos").delete().neq("controle_lab", "X_INVALIDO").execute()
            st.cache_data.clear()
            st.success("✅ O BANCO FOI ZERADO! Agora faça o upload dos PDFs abaixo para inserir os dados perfeitos.")
            st.rerun()

    st.markdown("---")
    st.subheader("PASSO 2: Upload dos Arquivos PDF")
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
                st.success(f"✅ {len(df_novos)} laudos processados sem erros e salvos no Supabase!")
                st.dataframe(df_novos, use_container_width=True)

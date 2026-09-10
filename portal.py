import gdown
from io import BytesIO

# ==============================================================================
# CONEXÃO DIRETA E PÚBLICA COM A PASTA DO GOOGLE DRIVE (SEM SECRETS)
# ==============================================================================
def buscar_pdfs_da_pasta_drive_publica(folder_id):
    try:
        url_folder = f"https://drive.google.com/drive/folders/{folder_id}"
        
        # Lista e baixa os arquivos em lote na memória temporária
        files = gdown.download_folder(url_folder, quiet=True, use_cookies=False)
        
        dados_extraidos = []
        if files:
            for file_path in files:
                if file_path.lower().endswith('.pdf'):
                    with open(file_path, 'rb') as f:
                        file_bytes = BytesIO(f.read())
                        filename = file_path.split('/')[-1].split('\\')[-1]
                        dados = extrair_dados_pdf(file_bytes, filename)
                        dados_extraidos.append(dados)
        
        return pd.DataFrame(dados_extraidos)
    except Exception as e:
        st.error(f"Erro ao acessar pasta pública do Drive: {e}")
        return pd.DataFrame()

# ==============================================================================
# NO MÓDULO: "📥 Importar Laudos (Drive & PDF)"
# ==============================================================================
elif opcao_menu == "📥 Importar Laudos (Drive & PDF)":
    st.title("📥 Sincronização e Processamento de PDFs")

    st.subheader("1. Conexão Direta com a Pasta do Google Drive")
    st.markdown(f"**Pasta Ativa:** `https://drive.google.com/drive/u/0/folders/{FOLDER_ID_DRIVE}`")

    if st.button("🔄 SINCRONIZAR COM A PASTA DO GOOGLE DRIVE", type="primary"):
        with st.spinner("Lendo arquivos PDF diretamente da pasta do Google Drive..."):
            df_drive = buscar_pdfs_da_pasta_drive_publica(FOLDER_ID_DRIVE)

            if not df_drive.empty:
                st.session_state.df_base = pd.concat(
                    [st.session_state.df_base, df_drive], 
                    ignore_index=True
                ).drop_duplicates(subset=["Nome do Arquivo PDF"])
                
                st.success(f"✅ {len(df_drive)} laudo(s) lido(s) e integrados com sucesso!")
                st.dataframe(df_drive, use_container_width=True)
            else:
                st.warning("Nenhum arquivo PDF encontrado na pasta do Drive.")

    st.markdown("---")
    st.subheader("2. Upload Manual Alternativo")
    uploaded_files = st.file_uploader("Upload de Laudos em PDF", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 Processar Upload Manual"):
            novos = [extrair_dados_pdf(pdf, pdf.name) for pdf in uploaded_files]
            df_n = pd.DataFrame(novos)
            st.session_state.df_base = pd.concat([st.session_state.df_base, df_n], ignore_index=True).drop_duplicates(subset=["Nome do Arquivo PDF"])
            st.success("✅ Laudos processados e carregados com sucesso!")
            st.dataframe(df_n, use_container_width=True)

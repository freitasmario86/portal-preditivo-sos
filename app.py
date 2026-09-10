import pypdf
import re
import pandas as pd
from googleapiclient.discovery import build

def extrair_dados_pdf(stream_pdf, nome_arquivo):
    reader = pypdf.PdfReader(stream_pdf)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"

    # Extrações via Nome do Arquivo
    modelo = re.search(r'_([A-Z0-9]+)#', nome_arquivo)
    frota = re.search(r'#([A-Z0-9]+)_', nome_arquivo)
    ctrl = re.search(r'_(U\d{3}-\d{5}-\d{4})', nome_arquivo)

    # Extrações via Conteúdo Interno (Lê os horímetros reais sem zerar)
    data_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', texto)
    hrs_encontrados = re.findall(r'(\d+[\.,]?\d*)\s*HR', texto)

    hr_equip = float(hrs_encontrados[0].replace(',', '.')) if len(hrs_encontrados) >= 1 else 0.0
    hr_oleo = float(hrs_encontrados[1].replace(',', '.')) if len(hrs_encontrados) >= 2 else 0.0

    return {
        "Data": data_match.group(1) if data_match else "N/A",
        "Modelo": modelo.group(1) if modelo else "Geral",
        "Frota": frota.group(1) if frota else "Desconhecido",
        "Horímetro Equip": hr_equip,
        "Horímetro Óleo": hr_oleo,
        "Controle": ctrl.group(1) if ctrl else "Desconhecido",
        "Arquivo": nome_arquivo
    }

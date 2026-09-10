import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import weibull_min
from sklearn.linear_model import LinearRegression

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Portal Preditivo S.O.S", layout="wide")
st.title("⚙️ Portal Avançado de Manutenção Preditiva e Confiabilidade")

# ==========================================
# 1. CARREGAMENTO DE DADOS (Simulação baseada no seu cenário)
# ==========================================
@st.cache_data
def carregar_dados():
    # Simulando um banco de dados maior para permitir todas as análises
    dados = {
        'Frota': ['ES0181', 'ES0181', 'ES0181', 'ES0181', 'RC0004', 'RC0004', 'ES0201', 'ES0201'],
        'Compartimento': ['Com. Giro', 'Com. Giro', 'Com. Giro', 'Com. Giro', 'Com. Esq', 'Com. Esq', 'Motor', 'Motor'],
        'Data': pd.to_datetime(['2025-11-03', '2026-02-21', '2026-05-25', '2026-08-25', '2026-01-28', '2026-08-21', '2026-03-25', '2026-08-19']),
        'Horimetro_Equip': [4403, 4910, 5379, 5919, 2468, 3466, 2774, 3744],
        'Horimetro_Oleo': [250, 507, 469, 1009, 422, 998, 371, 462],
        'Fe_ppm': [912, 571, 370, 257, 58, 49, 1101, 78],
        'Si_ppm': [13, 19, 20, 21, 22, 22, 227, 22],
        'V100': [27.9, 27.3, 28.4, 29.4, 28.1, 26.7, 0.64, 18.2], # Viscosidade
        'Status': ['Crítico', 'Crítico', 'Crítico', 'Monitorar', 'Monitorar', 'Normal', 'Crítico', 'Normal']
    }
    return pd.DataFrame(dados).sort_values(by=['Frota', 'Compartimento', 'Data'])

df = carregar_dados()

# ==========================================
# 2. FILTROS LATERAIS
# ==========================================
st.sidebar.header("Filtros de Ativo")
filtro_frota = st.sidebar.selectbox("Número de Frota", df['Frota'].unique())
df_frota = df[df['Frota'] == filtro_frota]
filtro_comp = st.sidebar.selectbox("Compartimento", df_frota['Compartimento'].unique())
df_filtrado = df_frota[df_frota['Compartimento'] == filtro_comp].copy()

# ==========================================
# 3. ANÁLISES TÁTICAS (Nível Gerencial)
# ==========================================
st.header("📊 1. Visão Tática e Confiabilidade (Geral)")
colT1, colT2 = st.columns(2)

with colT1:
    st.subheader("Matriz de Pior Ativo (Bad Actor List)")
    # Conta quantos status "Crítico" cada Frota/Compartimento tem
    bad_actors = df[df['Status'] == 'Crítico'].groupby(['Frota', 'Compartimento']).size().reset_index(name='Alertas Críticos')
    bad_actors = bad_actors.sort_values(by='Alertas Críticos', ascending=False)
    fig_pareto, ax_pareto = plt.subplots(figsize=(6, 4))
    sns.barplot(x='Alertas Críticos', y='Frota', hue='Compartimento', data=bad_actors, ax=ax_pareto, palette='Reds_r')
    ax_pareto.set_title("Equipamentos com mais falhas crônicas")
    st.pyplot(fig_pareto)

with colT2:
    st.subheader("Análise de Sobrevivência (Weibull) & MTBF")
    # Simulação de tempo até a falha crítica (MTBF em horas do óleo)
    tempos_falha = df[df['Status'] == 'Crítico']['Horimetro_Oleo'].values
    if len(tempos_falha) > 1:
        mtbf = tempos_falha.mean()
        forma, loc, escala = weibull_min.fit(tempos_falha, floc=0)
        x = np.linspace(0, max(tempos_falha)*1.5, 100)
        confiabilidade = weibull_min.sf(x, forma, loc=loc, scale=escala) # Survival Function (R(t))
        
        fig_w, ax_w = plt.subplots(figsize=(6, 4))
        ax_w.plot(x, confiabilidade * 100, color='purple', lw=2)
        ax_w.axvline(mtbf, color='red', linestyle='--', label=f'MTBF: {mtbf:.0f}h')
        ax_w.set_title("Curva de Confiabilidade R(t)")
        ax_w.set_ylabel("Probabilidade de Sobrevivência (%)")
        ax_w.set_xlabel("Horas do Óleo")
        ax_w.legend()
        st.pyplot(fig_w)
    else:
        st.info("Dados insuficientes para calcular Weibull nesta amostra.")

st.divider()

# ==========================================
# 4. ANÁLISES OPERACIONAIS (Componente Específico)
# ==========================================
st.header(f"🔧 2. Visão Operacional: {filtro_frota} - {filtro_comp}")

# 4.1 Taxa de Geração de Desgaste (ppm/hora)
df_filtrado['Delta_Fe'] = df_filtrado['Fe_ppm'].diff()
df_filtrado['Delta_Horas'] = df_filtrado['Horimetro_Equip'].diff()
df_filtrado['Taxa_Desgaste (ppm/h)'] = (df_filtrado['Delta_Fe'] / df_filtrado['Delta_Horas']).fillna(0)

st.subheader("A. Taxa de Geração de Desgaste (Velocidade de Degradação)")
st.dataframe(df_filtrado[['Data', 'Horimetro_Equip', 'Fe_ppm', 'Taxa_Desgaste (ppm/h)', 'Status']].style.highlight_max(subset=['Taxa_Desgaste (ppm/h)'], color='lightcoral'))

colO1, colO2 = st.columns(2)

with colO1:
    # 4.2 Previsão de Troca (Regressão Linear)
    st.subheader("B. Previsão de Troca (Oil Drain Extension)")
    if len(df_filtrado) >= 2:
        X = df_filtrado['Horimetro_Oleo'].values.reshape(-1, 1)
        y = df_filtrado['Fe_ppm'].values
        modelo = LinearRegression()
        modelo.fit(X, y)
        
        # Prever o Ferro para 1000 horas, 1500 horas, etc
        x_futuro = np.array([[500], [1000], [1500], [2000]])
        y_futuro = modelo.predict(x_futuro)
        
        fig_pred, ax_pred = plt.subplots(figsize=(6, 4))
        ax_pred.scatter(X, y, color='black', label='Amostras Reais')
        ax_pred.plot(x_futuro, y_futuro, color='green', linestyle='--', label='Projeção Linear')
        ax_pred.axhline(800, color='red', linestyle='-', alpha=0.5, label='Limite Crítico (800 ppm)')
        ax_pred.set_xlabel("Horímetro do Óleo")
        ax_pred.set_ylabel("Ferro (ppm)")
        ax_pred.legend()
        st.pyplot(fig_pred)
    else:
        st.warning("Necessário pelo menos 2 coletas para projeção.")

with colO2:
    # 4.3 Correlação Contaminação vs Viscosidade
    st.subheader("C. Índice de Contaminação vs. Viscosidade")
    fig_corr, ax_corr = plt.subplots(figsize=(6, 4))
    sns.regplot(x='Si_ppm', y='V100', data=df_filtrado, ax=ax_corr, scatter_kws={'s':100, 'color':'orange'}, line_kws={'color':'red'})
    ax_corr.set_title("Impacto da Poeira (Silício) na Viscosidade")
    ax_corr.set_xlabel("Silício / Poeira (ppm)")
    ax_corr.set_ylabel("Viscosidade (V100)")
    st.pyplot(fig_corr)

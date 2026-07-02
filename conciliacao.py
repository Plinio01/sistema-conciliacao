import streamlit as st
import pandas as pd
from io import BytesIO
from difflib import SequenceMatcher
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Sistema de Conciliação Bancária",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

class SistemaConciliacao:
    def __init__(self, tolerancia_valor=0.01, tolerancia_dias=3):
        self.tolerancia_valor = tolerancia_valor
        self.tolerancia_dias = tolerancia_dias
    
    def similaridade_texto(self, texto1, texto2):
        """Calcula similaridade entre textos"""
        if pd.isna(texto1) or pd.isna(texto2):
            return 0
        return SequenceMatcher(None, str(texto1).lower(), str(texto2).lower()).ratio()
    
    def normalizar_data(self, data):
        """Normaliza diferentes formatos de data"""
        if pd.isna(data):
            return None
        
        if isinstance(data, pd.Timestamp):
            return data.date()
        
        try:
            # Tenta vários formatos
            for formato in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                try:
                    return datetime.strptime(str(data), formato).date()
                except:
                    continue
            return pd.to_datetime(data).date()
        except:
            return None
    
    def preparar_extrato(self, df):
        """Prepara e valida extrato"""
        # Padronizar nomes de colunas
        df.columns = df.columns.str.lower().str.strip()
        
        # Verificar colunas obrigatórias
        colunas_necessarias = ['data', 'valor', 'descricao']
        faltando = [col for col in colunas_necessarias if col not in df.columns]
        
        if faltando:
            raise ValueError(f"Colunas faltando: {', '.join(faltando)}")
        
        # Limpar e converter dados
        df['data'] = df['data'].apply(self.normalizar_data)
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
        df['descricao'] = df['descricao'].astype(str).str.strip()
        
        # Remover linhas com dados inválidos
        df = df.dropna(subset=['data', 'valor'])
        
        return df
    
    def comparar_extratos(self, extrato_banco, extrato_contabil):
        """Compara extratos e retorna diferenças"""
        
        # Preparar dados
        banco = self.preparar_extrato(extrato_banco.copy())
        contabil = self.preparar_extrato(extrato_contabil.copy())
        
        # Adicionar flags de conciliação
        banco['conciliado'] = False
        banco['id_original'] = banco.index
        contabil['conciliado'] = False
        contabil['id_original'] = contabil.index
        
        # Listas de resultados
        conciliados = []
        divergencias = []
        
        # FASE 1: Correspondência EXATA (data + valor + descrição similar)
        for idx_b, row_b in banco.iterrows():
            if row_b['conciliado']:
                continue
            
            for idx_c, row_c in contabil.iterrows():
                if row_c['conciliado']:
                    continue
                
                if (row_b['data'] == row_c['data'] and 
                    abs(row_b['valor'] - row_c['valor']) <= self.tolerancia_valor and
                    self.similaridade_texto(row_b['descricao'], row_c['descricao']) > 0.8):
                    
                    conciliados.append({
                        'Data': row_b['data'],
                        'Valor': f"R$ {row_b['valor']:,.2f}",
                        'Descrição Banco': row_b['descricao'],
                        'Descrição Contábil': row_c['descricao'],
                        'Tipo': '✅ Match Exato',
                        'Similaridade': f"{self.similaridade_texto(row_b['descricao'], row_c['descricao'])*100:.0f}%"
                    })
                    
                    banco.at[idx_b, 'conciliado'] = True
                    contabil.at[idx_c, 'conciliado'] = True
                    break
        
        # FASE 2: Correspondência por VALOR e DATA (descrição diferente)
        for idx_b, row_b in banco.iterrows():
            if row_b['conciliado']:
                continue
            
            for idx_c, row_c in contabil.iterrows():
                if row_c['conciliado']:
                    continue
                
                if (row_b['data'] == row_c['data'] and 
                    abs(row_b['valor'] - row_c['valor']) <= self.tolerancia_valor):
                    
                    divergencias.append({
                        'Data': row_b['data'],
                        'Valor': f"R$ {row_b['valor']:,.2f}",
                        'Descrição Banco': row_b['descricao'],
                        'Descrição Contábil': row_c['descricao'],
                        'Tipo': '⚠️ Descrição Divergente',
                        'Observação': 'Valores iguais, descrições diferentes'
                    })
                    
                    banco.at[idx_b, 'conciliado'] = True
                    contabil.at[idx_c, 'conciliado'] = True
                    break
        
        # FASE 3: Correspondência por VALOR (datas próximas)
        for idx_b, row_b in banco.iterrows():
            if row_b['conciliado']:
                continue
            
            for idx_c, row_c in contabil.iterrows():
                if row_c['conciliado']:
                    continue
                
                diff_dias = abs((row_b['data'] - row_c['data']).days)
                
                if (diff_dias <= self.tolerancia_dias and 
                    abs(row_b['valor'] - row_c['valor']) <= self.tolerancia_valor):
                    
                    divergencias.append({
                        'Data Banco': row_b['data'],
                        'Data Contábil': row_c['data'],
                        'Valor': f"R$ {row_b['valor']:,.2f}",
                        'Descrição Banco': row_b['descricao'],
                        'Descrição Contábil': row_c['descricao'],
                        'Tipo': '⚠️ Data Divergente',
                        'Observação': f'Diferença de {diff_dias} dia(s)'
                    })
                    
                    banco.at[idx_b, 'conciliado'] = True
                    contabil.at[idx_c, 'conciliado'] = True
                    break
        
        # Itens não conciliados
        apenas_banco = banco[~banco['conciliado']][['data', 'valor', 'descricao']].copy()
        apenas_banco.columns = ['Data', 'Valor', 'Descrição']
        apenas_banco['Valor'] = apenas_banco['Valor'].apply(lambda x: f"R$ {x:,.2f}")
        
        apenas_contabil = contabil[~contabil['conciliado']][['data', 'valor', 'descricao']].copy()
        apenas_contabil.columns = ['Data', 'Valor', 'Descrição']
        apenas_contabil['Valor'] = apenas_contabil['Valor'].apply(lambda x: f"R$ {x:,.2f}")
        
        # Calcular totais
        total_banco = banco[~banco['conciliado']]['valor'].sum()
        total_contabil = contabil[~contabil['conciliado']]['valor'].sum()
        
        return {
            'conciliados': pd.DataFrame(conciliados),
            'divergencias': pd.DataFrame(divergencias),
            'apenas_banco': apenas_banco,
            'apenas_contabil': apenas_contabil,
            'total_banco': total_banco,
            'total_contabil': total_contabil,
            'diferenca': total_banco - total_contabil
        }

def criar_modelo_excel():
    """Cria arquivo modelo para download"""
    modelo = pd.DataFrame({
        'data': ['2024-01-10', '2024-01-15', '2024-01-20'],
        'valor': [1000.00, 500.50, 250.75],
        'descricao': ['Recebimento Cliente A', 'Pagamento Fornecedor X', 'Taxa Bancária']
    })
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        modelo.to_excel(writer, index=False, sheet_name='Extrato')
        
        # Adicionar instruções
        instrucoes = pd.DataFrame({
            'Instruções': [
                '1. Mantenha os nomes das colunas: data, valor, descricao',
                '2. Formato de data: AAAA-MM-DD ou DD/MM/AAAA',
                '3. Valores numéricos sem símbolos (ex: 1000.50)',
                '4. Descrições devem ser texto',
                '5. Apague esta aba antes de fazer upload'
            ]
        })
        instrucoes.to_excel(writer, index=False, sheet_name='Instruções')
    
    return buffer.getvalue()

def main():
    # Cabeçalho
    st.title("🏦 Sistema de Conciliação Bancária")
    st.markdown("**Identifique diferenças entre extratos bancários e contábeis automaticamente**")
    st.markdown("---")
    
    # Sidebar - Upload de arquivos
    with st.sidebar:
        st.header("📤 Upload dos Extratos")
        
        arquivo_banco = st.file_uploader(
            "**1️⃣ Extrato Bancário**",
            type=['csv', 'xlsx', 'xls'],
            help="Arquivo CSV ou Excel com colunas: data, valor, descricao"
        )
        
        arquivo_contabil = st.file_uploader(
            "**2️⃣ Extrato Contábil**",
            type=['csv', 'xlsx', 'xls'],
            help="Arquivo CSV ou Excel com colunas: data, valor, descricao"
        )
        
        st.markdown("---")
        
        # Configurações
        st.subheader("⚙️ Configurações")
        
        tolerancia_valor = st.number_input(
            "Tolerância de Valor (R$)",
            min_value=0.00,
            max_value=100.00,
            value=0.01,
            step=0.01,
            help="Diferença máxima aceita entre valores"
        )
        
        tolerancia_dias = st.slider(
            "Tolerância de Dias",
            min_value=0,
            max_value=10,
            value=3,
            help="Diferença máxima de dias para considerar match"
        )
        
        st.markdown("---")
        
        # Download modelo
        st.subheader("📥 Modelo de Arquivo")
        st.download_button(
            label="⬇️ Baixar Modelo Excel",
            data=criar_modelo_excel(),
            file_name="modelo_extrato_bancario.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Baixe um modelo para preencher seus extratos"
        )
        
        # Formato esperado
        with st.expander("ℹ️ Formato dos Arquivos"):
            st.code("""
data,valor,descricao
2024-01-10,1000.00,Pagamento Cliente A
2024-01-15,500.50,Fornecedor XYZ
2024-01-20,250.00,Taxa Bancária
            """)
    
    # Área principal
    if not arquivo_banco or not arquivo_contabil:
        # Mensagem inicial
        st.info("👈 **Comece fazendo upload dos dois extratos na barra lateral**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### ✅ Conciliação Automática")
            st.write("Identifica transações idênticas automaticamente")
        
        with col2:
            st.markdown("### ⚠️ Detecta Divergências")
            st.write("Aponta diferenças de descrição e datas")
        
        with col3:
            st.markdown("### 📊 Relatório Completo")
            st.write("Exporta resultados em Excel")
        
        # Exemplo visual
        st.markdown("---")
        st.subheader("📝 Exemplo de Resultado")
        
        exemplo_df = pd.DataFrame({
            'Data': ['2024-01-10', '2024-01-15'],
            'Valor': ['R$ 1.000,00', 'R$ 500,00'],
            'Descrição Banco': ['Pagamento Cliente A', 'Fornecedor XYZ'],
            'Descrição Contábil': ['Cliente A - Recebimento', 'Pgto Fornecedor XYZ'],
            'Status': ['✅ Conciliado', '⚠️ Descrição Divergente']
        })
        
        st.dataframe(exemplo_df, use_container_width=True)
        
    else:
        try:
            # Carregar arquivos
            with st.spinner("Carregando extratos..."):
                # Extrato Bancário
                if arquivo_banco.name.endswith('.csv'):
                    df_banco = pd.read_csv(arquivo_banco)
                else:
                    df_banco = pd.read_excel(arquivo_banco)
                
                # Extrato Contábil
                if arquivo_contabil.name.endswith('.csv'):
                    df_contabil = pd.read_csv(arquivo_contabil)
                else:
                    df_contabil = pd.read_excel(arquivo_contabil)
            
            # Preview dos dados
            st.subheader("👀 Preview dos Extratos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🏦 Extrato Bancário**")
                st.caption(f"Total de {len(df_banco)} registros")
                st.dataframe(df_banco.head(5), use_container_width=True)
            
            with col2:
                st.markdown("**📒 Extrato Contábil**")
                st.caption(f"Total de {len(df_contabil)} registros")
                st.dataframe(df_contabil.head(5), use_container_width=True)
            
            st.markdown("---")
            
            # Botão processar
            if st.button("🔄 **PROCESSAR CONCILIAÇÃO**", type="primary", use_container_width=True):
                
                with st.spinner("🔍 Analisando e comparando extratos..."):
                    # Processar conciliação
                    sistema = SistemaConciliacao(
                        tolerancia_valor=tolerancia_valor,
                        tolerancia_dias=tolerancia_dias
                    )
                    
                    resultado = sistema.comparar_extratos(df_banco, df_contabil)
                
                st.success("✅ Conciliação processada com sucesso!")
                
                # Cards de resumo
                st.subheader("📊 Resumo Executivo")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        label="✅ Conciliados",
                        value=len(resultado['conciliados']),
                        delta=None,
                        help="Lançamentos que conferem"
                    )
                
                with col2:
                    st.metric(
                        label="⚠️ Divergências",
                        value=len(resultado['divergencias']),
                        delta=None,
                        help="Lançamentos com pequenas diferenças"
                    )
                
                with col3:
                    st.metric(
                        label="🏦 Apenas Banco",
                        value=len(resultado['apenas_banco']),
                        delta=f"R$ {resultado['total_banco']:,.2f}",
                        delta_color="off",
                        help="Lançamentos só no extrato bancário"
                    )
                
                with col4:
                    st.metric(
                        label="📒 Apenas Contábil",
                        value=len(resultado['apenas_contabil']),
                        delta=f"R$ {resultado['total_contabil']:,.2f}",
                        delta_color="off",
                        help="Lançamentos só no extrato contábil"
                    )
                
                # Alerta de diferença
                if abs(resultado['diferenca']) > 0.01:
                    st.markdown(f"""
                    <div class="error-box">
                        <strong>⚠️ ATENÇÃO: Diferença de saldo detectada!</strong><br>
                        Diferença total: <strong>R$ {resultado['diferenca']:,.2f}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="success-box">
                        <strong>✅ Saldos conferem!</strong><br>
                        Não há diferença nos valores não conciliados.
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Tabs com detalhes
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "✅ Conciliados",
                    "⚠️ Divergências",
                    "🏦 Apenas Banco",
                    "📒 Apenas Contábil",
                    "📊 Estatísticas"
                ])
                
                with tab1:
                    if not resultado['conciliados'].empty:
                        st.dataframe(
                            resultado['conciliados'],
                            use_container_width=True,
                            hide_index=True
                        )
                        st.success(f"✅ {len(resultado['conciliados'])} lançamentos conciliados com sucesso!")
                    else:
                        st.warning("Nenhum lançamento foi conciliado automaticamente.")
                
                with tab2:
                    if not resultado['divergencias'].empty:
                        st.dataframe(
                            resultado['divergencias'],
                            use_container_width=True,
                            hide_index=True
                        )
                        st.info(f"ℹ️ {len(resultado['divergencias'])} lançamentos com divergências detectadas.")
                    else:
                        st.success("✅ Nenhuma divergência encontrada!")
                
                with tab3:
                    if not resultado['apenas_banco'].empty:
                        st.dataframe(
                            resultado['apenas_banco'],
                            use_container_width=True,
                            hide_index=True
                        )
                        st.error(f"❌ {len(resultado['apenas_banco'])} lançamentos encontrados apenas no banco (Total: R$ {resultado['total_banco']:,.2f})")
                    else:
                        st.success("✅ Todos os lançamentos do banco foram encontrados na contabilidade!")
                
                with tab4:
                    if not resultado['apenas_contabil'].empty:
                        st.dataframe(
                            resultado['apenas_contabil'],
                            use_container_width=True,
                            hide_index=True
                        )
                        st.error(f"❌ {len(resultado['apenas_contabil'])} lançamentos encontrados apenas na contabilidade (Total: R$ {resultado['total_contabil']:,.2f})")
                    else:
                        st.success("✅ Todos os lançamentos contábeis foram encontrados no banco!")
                
                with tab5:
                    # Estatísticas gerais
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 📈 Distribuição")
                        total_itens = len(resultado['conciliados']) + len(resultado['divergencias']) + len(resultado['apenas_banco']) + len(resultado['apenas_contabil'])
                        
                        if total_itens > 0:
                            taxa_conciliacao = (len(resultado['conciliados']) / total_itens) * 100
                            st.metric("Taxa de Conciliação", f"{taxa_conciliacao:.1f}%")
                        
                        st.metric("Total de Lançamentos Analisados", total_itens)
                    
                    with col2:
                        st.markdown("### 💰 Valores")
                        st.metric("Valor Total Banco (não conciliado)", f"R$ {resultado['total_banco']:,.2f}")
                        st.metric("Valor Total Contábil (não conciliado)", f"R$ {resultado['total_contabil']:,.2f}")
                        st.metric("Diferença", f"R$ {resultado['diferenca']:,.2f}")
                
                # Exportar resultados
                st.markdown("---")
                st.subheader("💾 Exportar Resultados")
                
                # Criar Excel com múltiplas abas
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    # Resumo
                    resumo_df = pd.DataFrame({
                        'Métrica': [
                            'Total Conciliados',
                            'Total Divergências',
                            'Total Apenas Banco',
                            'Total Apenas Contábil',
                            'Valor Apenas Banco',
                            'Valor Apenas Contábil',
                            'Diferença'
                        ],
                        'Valor': [
                            len(resultado['conciliados']),
                            len(resultado['divergencias']),
                            len(resultado['apenas_banco']),
                            len(resultado['apenas_contabil']),
                            f"R$ {resultado['total_banco']:,.2f}",
                            f"R$ {resultado['total_contabil']:,.2f}",
                            f"R$ {resultado['diferenca']:,.2f}"
                        ]
                    })
                    resumo_df.to_excel(writer, sheet_name='Resumo', index=False)
                    
                    # Conciliados
                    if not resultado['conciliados'].empty:
                        resultado['conciliados'].to_excel(writer, sheet_name='Conciliados', index=False)
                    
                    # Divergências
                    if not resultado['divergencias'].empty:
                        resultado['divergencias'].to_excel(writer, sheet_name='Divergências', index=False)
                    
                    # Apenas Banco
                    if not resultado['apenas_banco'].empty:
                        resultado['apenas_banco'].to_excel(writer, sheet_name='Apenas Banco', index=False)
                    
                    # Apenas Contábil
                    if not resultado['apenas_contabil'].empty:
                        resultado['apenas_contabil'].to_excel(writer, sheet_name='Apenas Contábil', index=False)
                
                # Botão de download
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col2:
                    st.download_button(
                        label="📥 **BAIXAR RELATÓRIO COMPLETO (EXCEL)**",
                        data=buffer.getvalue(),
                        file_name=f"conciliacao_bancaria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
        
        except Exception as e:
            st.error(f"❌ **Erro ao processar arquivos:**")
            st.exception(e)
            
            st.info("""
            **Verifique se:**
            - Os arquivos contêm as colunas: `data`, `valor`, `descricao`
            - Os formatos de data estão corretos
            - Os valores são numéricos
            - Não há linhas vazias
            """)

if __name__ == "__main__":
    main()

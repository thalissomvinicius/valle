import streamlit as st
import pyodbc
import pandas as pd
from datetime import datetime
import os

# Configuração da página
st.set_page_config(
    page_title="Consulta de Vendas",
    page_icon="💰",
    layout="wide"
)

# Configuração da conexão usando variáveis de ambiente
connection_string = (
    "Driver={SQL Server};"
    "Server=" + os.getenv('DB_SERVER', 'DCWBD11\\VALLEPRIME_PRD') + ";"
    "Database=" + os.getenv('DB_DATABASE', 'UAU-VALLEPRIME') + ";"
    "UID=" + os.getenv('DB_UID', 'consultasBD') + ";"
    "PWD=" + os.getenv('DB_PWD', 'V@lle#2021') + ";"
)

# Mapeamento de tipos de parcelas
tipo_parcela_map = {
    "0": "Seguro",
    "1": "Custas",
    "2": "Acerto final",
    "A": "Resíduo Agrup.",
    "B": "Balão",
    "C": "Chave",
    "E": "Entrada",
    "ER": "Entrada Renegoc",
    "I": "Intermediação",
    "IN": "Intermediárias",
    "P": "Parcela",
    "R": "Resíduo",
    "S": "C. CORRETAGEM"
}

# Tipos de parcelas a serem considerados
tipos_filtrados = {"E", "P", "S"}

# Função para escolher a empresa com base na seleção
def escolher_empresa(empresa_selecionada):
    if empresa_selecionada == 'ML - 999 - 70100 - 604':
        return 999, '70100', 604  # Retorna empresa, obra, código da empresa
    elif empresa_selecionada == 'VALLE - 6 - 70400 - 605':
        return 6, '70400', 605  # Retorna empresa, obra, código da empresa
    else:
        return None, None, None

# Função para obter detalhes da venda (com cache)
@st.cache_data
def get_detalhes_venda(num_venda, empresa, obra):
    query = """
    SELECT 
        Recebidas.NumParc_Rec AS Parc,
        (Recebidas.Valor_Rec + Recebidas.VlJurosParc_Rec + Recebidas.VlCorrecao_Rec + Recebidas.VlAcres_Rec + Recebidas.VlTaxaBol_Rec + Recebidas.VlMulta_Rec + Recebidas.VlJuros_Rec + Recebidas.VlCorrecaoAtr_Rec
         - (Recebidas.VlDesconto_Rec + Recebidas.ValDescontoCusta_Rec + Recebidas.ValDescontoImposto_Rec + Recebidas.ValDescontoCondicional_rec)
         + Recebidas.ValorConf_Rec + Recebidas.VlJurosParcConf_Rec + Recebidas.VlCorrecaoConf_Rec + Recebidas.VlAcresConf_Rec + Recebidas.VlTaxaBolConf_Rec + Recebidas.VlMultaConf_Rec + Recebidas.VlJurosConf_Rec + Recebidas.VlCorrecaoAtrConf_Rec
         - (Recebidas.VlDescontoConf_Rec + Recebidas.ValDescontoCustaConf_Rec + Recebidas.ValDescontoImpostoConf_Rec + Recebidas.ValDescontoCondicionalConf_rec)) AS Val_Parc_Paga,
        Recebidas.Tipo_Rec AS Tipo,
        (Recebidas.ValDescontoCusta_Rec + Recebidas.ValDescontoCustaConf_Rec) AS TotDescCusta,  -- Soma os valores de desconto de custas
        CONVERT(varchar, Recebidas.Data_Rec, 23) AS Dt_Recebe,
        (Recebidas.VlCorrecao_Rec + Recebidas.VlCorrecaoConf_Rec 
        + CASE 
            WHEN Recebidas.Tipo_Rec IN ('R', 'A') 
            THEN 0 
            ELSE  
                CASE VendasRecebidas.AniversarioContr_VRec 
                    WHEN 0  
                    THEN (Recebidas.Valor_Rec + Recebidas.ValorConf_Rec)  
                    ELSE (Recebidas.Valor_Rec + Recebidas.ValorConf_Rec + Recebidas.VlJurosParcEmb_Rec + Recebidas.VlJurosParcEmbConf_Rec + Recebidas.VlCorrecaoEmb_Rec + Recebidas.VlCorrecaoEmbConf_Rec)
                END
        END) AS Vl_Confirm
    FROM 
        VendasRecebidas WITH(NOLOCK)
    INNER JOIN 
        Recebidas WITH(NOLOCK) 
        ON VendasRecebidas.Empresa_VRec = Recebidas.Empresa_Rec 
        AND VendasRecebidas.Obra_VRec = Recebidas.Obra_Rec 
        AND VendasRecebidas.Num_VRec = Recebidas.NumVend_Rec
    WHERE 
        Recebidas.Obra_Rec = ?
        AND Recebidas.NumVend_Rec = ?
        AND Recebidas.Empresa_Rec = ?
    ORDER BY 
        Recebidas.Data_Rec
    """
    try:
        with pyodbc.connect(connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (obra, num_venda, empresa))
                columns = [column[0] for column in cursor.description]
                results = cursor.fetchall()
                return columns, results
    except pyodbc.Error as e:
        st.error(f"Erro no banco de dados: {e}")
        return None, None
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        return None, None

def formatar_para_real(valor):
    try:
        return f"R${float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return valor

def traduzir_tipo_parcela(tipo):
    return tipo_parcela_map.get(tipo, tipo)

def get_status_description(status_code):
    status_dict = {
        0: "0 - Normal",
        1: "1 - Cancelada",
        2: "2 - Alterada",
        3: "3 - Quitado",
        4: "4 - Em acerto",
        5: "5 - Aluguel quitado adiantado"
    }
    return status_dict.get(status_code, "Status desconhecido")

def format_cpf_cnpj(document):
    if len(document) == 11:
        return f"{document[:3]}.{document[3:6]}.{document[6:9]}-{document[9:]}"  # Formato CPF
    elif len(document) == 14:
        return f"{document[:2]}.{document[2:5]}.{document[5:8]}/{document[8:12]}-{document[12:]}"  # Formato CNPJ
    return document

def format_date(date_obj):
    if isinstance(date_obj, datetime):
        return date_obj.strftime('%d/%m/%Y')
    return date_obj

def get_identifier(cursor, empresa, obra, num_venda):
    sql_query = f"""
    SELECT UnidadePer.Identificador_unid AS IdentificadorQuadraLote
    FROM (
       SELECT * FROM ItensVenda WITH(NOLOCK) 
       UNION
       SELECT * FROM ItensRecebidas WITH(NOLOCK) 
    ) AS ItensVenda 
    INNER JOIN PrdSrv WITH(NOLOCK) 
       ON ItensVenda.Produto_Itv = PrdSrv.NumProd_psc 
    INNER JOIN (
       SELECT Empresa_ven, Obra_ven, Num_ven, Data_Ven, ValorTot_ven, Cliente_ven, TipoVenda_Ven, Status_Ven, DataCancel_Ven
       FROM Vendas WITH(NOLOCK) 
       UNION
       SELECT Empresa_vrec, Obra_vrec, Num_vrec, Data_vrec, ValorTot_vrec, Cliente_vrec, TipoVenda_vrec, Status_VRec, DataCancel_VRec
       FROM VendasRecebidas WITH(NOLOCK) 
    ) AS Vendas
       ON ItensVenda.Empresa_itv = Vendas.Empresa_ven
       AND ItensVenda.Obra_Itv = Vendas.Obra_Ven
       AND ItensVenda.NumVend_Itv = Vendas.Num_Ven 
    LEFT JOIN UnidadePer WITH(NOLOCK) 
       ON ItensVenda.Empresa_itv = UnidadePer.Empresa_unid
       AND ItensVenda.Produto_Itv = UnidadePer.Prod_unid
       AND ItensVenda.CodPerson_Itv = UnidadePer.NumPer_unid  
    WHERE Vendas.Empresa_ven = {empresa}
       AND Vendas.Num_Ven = {num_venda}
       AND Vendas.Obra_Ven = '{obra}'
    """
    cursor.execute(sql_query)
    result = cursor.fetchone()
    return result.IdentificadorQuadraLote if result else 'N/A'

def consultar_detalhes_venda(num_venda, empresa, obra):
    query = f"""
    SELECT 
        Pessoas.nome_pes AS NomeCliente_Ven,
        Vendas.Status_Ven,
        Vendas.Empresa_Ven,
        Vendas.Obra_Ven,
        Vendas.Num_Ven,
        Vendas.Cliente_Ven,
        Vendas.DataIniContrato_Ven,
        Empresas.Desc_emp,
        Obras.Descr_obr,
        Pessoas.cpf_pes
    FROM (
        SELECT  
            Empresa_Ven, 
            Obra_Ven, 
            Num_Ven, 
            Cliente_Ven,
            Status_Ven,
            DataIniContrato_Ven
        FROM 
            Vendas WITH(NOLOCK) 
        UNION 
        SELECT  
            Empresa_VRec, 
            Obra_VRec, 
            Num_VRec, 
            Cliente_VRec,
            Status_VRec AS Status_Ven,
            DataIniContrato_VRec AS DataIniContrato_Ven
        FROM 
            VendasRecebidas WITH(NOLOCK) 
    ) AS Vendas
    INNER JOIN 
        Pessoas WITH(NOLOCK) ON Vendas.Cliente_Ven = Pessoas.cod_pes
    INNER JOIN 
        Obras WITH(NOLOCK) ON Cod_Obr = Vendas.Obra_Ven AND empresa_obr = Vendas.Empresa_Ven
    INNER JOIN 
        Empresas WITH(NOLOCK) ON Codigo_emp = Vendas.Empresa_Ven
    WHERE 
        Vendas.Num_Ven = {num_venda}
        AND Vendas.Empresa_Ven = {empresa}
        AND Vendas.Obra_Ven = '{obra}'
    """

    try:
        with pyodbc.connect(connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                colunas_venda = [column[0] for column in cursor.description]
                resultados_venda = cursor.fetchall()

                if resultados_venda:
                    resultado = resultados_venda[0]
                    identificador = get_identifier(cursor, empresa, obra, num_venda)

                    # Exibição mais compacta usando colunas
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Cliente:** {resultado[colunas_venda.index('NomeCliente_Ven')]}")
                        st.write(f"**CPF/CNPJ:** {format_cpf_cnpj(resultado[colunas_venda.index('cpf_pes')])}")
                        st.write(f"**Venda:** {resultado[colunas_venda.index('Num_Ven')]}")
                        st.write(f"**Status:** {get_status_description(resultado[colunas_venda.index('Status_Ven')])}")
                    with col2:
                        st.write(f"**Empresa:** {resultado[colunas_venda.index('Desc_emp')]}")
                        st.write(f"**Obra:** {resultado[colunas_venda.index('Descr_obr')]}")
                        st.write(f"**Data do Contrato:** {format_date(resultado[colunas_venda.index('DataIniContrato_Ven')])}")
                        st.write(f"**Identificador:** {identificador}")
                else:
                    st.warning("Nenhum detalhe de venda encontrado.")
    except pyodbc.Error as e:
        st.error(f"Erro no banco de dados: {e}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")

def mostrar_valores_pagos(num_venda, empresa, obra):
    columns, results = get_detalhes_venda(num_venda, empresa, obra)
    if results:
        # Criar um DataFrame para exibir os resultados
        data = []
        total_val_parc_paga = 0
        total_vl_confirm = 0
        total_vl_menor = 0
        
        for row in results:
            row_dict = dict(zip(columns, row))
            tipo = row_dict['Tipo']
            if tipo in tipos_filtrados:  # Filtrando os tipos desejados
                tipo_traduzido = traduzir_tipo_parcela(tipo)
                val_parc_paga = float(row_dict['Val_Parc_Paga'])
                vl_confirm = float(row_dict['Vl_Confirm'])
                dt_recebe = row_dict['Dt_Recebe']
                vl_menor = min(val_parc_paga, vl_confirm)
                diferenca = val_parc_paga - vl_confirm  # Calculando a diferença
                
                data.append([ 
                    tipo_traduzido,
                    row_dict['Parc'],
                    dt_recebe,
                    formatar_para_real(val_parc_paga),
                    formatar_para_real(vl_confirm),
                    formatar_para_real(vl_menor),
                    formatar_para_real(diferenca)  # Adicionando a diferença
                ])
                
                total_val_parc_paga += val_parc_paga
                total_vl_confirm += vl_confirm
                total_vl_menor += vl_menor
        
        # Criar o DataFrame
        df = pd.DataFrame(data, columns=["Tipo", "Parc.", "Dt. Recebe", "Val. Parc. Paga", "Vl. Confirm.", "Vl. Menor", "Diferença"])
        
        # Exibir a tabela no Streamlit
        st.write("### Valores Pagos:")
        st.dataframe(df)  # Exibe a tabela de forma interativa
        
        # Exibir os totais
        st.success(f"**Total Valor Pago:** {formatar_para_real(total_val_parc_paga)}")
        st.success(f"**Total Valor Confirmado:** {formatar_para_real(total_vl_confirm)}")
        st.success(f"**Valor para Usar na Quitação:** {formatar_para_real(total_vl_menor)}")
    else:
        st.warning("Nenhuma parcela paga encontrada para este lote, ou número da venda de outra Obra")
        st.write("**Total Valor Pago:** R$0,00")
        st.write("**Total Valor Confirmado:** R$0,00")
        st.write("**Valor para Usar na Quitação:** R$0,00")

# Interface Streamlit
st.title("Valor para Termo de Quitação")

# Menu lateral
with st.sidebar:
    st.header("Configurações")
    empresa_selecionada = st.selectbox("Selecione a Empresa:", ['ML - 999 - 70100 - 604', 'VALLE - 6 - 70400 - 605'])
    num_venda = st.text_input("Número da Venda:")

    # Seção de ajuda
    with st.expander("Instruções de Uso"):
        st.write("""
        1. Selecione a empresa no menu lateral.
        2. Insira o número da venda.
        3. Clique em 'Consultar' para visualizar os detalhes.
        """)

# Consulta e exibição dos dados
if st.button("Consultar"):
    if not num_venda.isdigit() or int(num_venda) <= 0:
        st.error("Número da Venda deve ser um número positivo.")
    else:
        empresa, obra, _ = escolher_empresa(empresa_selecionada)
        if empresa is None or obra is None:
            st.error("Empresa selecionada inválida.")
        else:
            with st.spinner("Consultando banco de dados..."):
                consultar_detalhes_venda(num_venda, empresa, obra)
                mostrar_valores_pagos(num_venda, empresa, obra)
import os
import re
import pandas as pd
import rasterio
from skimage.transform import resize
import numpy as np
from glob import glob
import natsort
from datetime import datetime
import traceback # <-- ADICIONADO: Importação necessária

class CFG:
    eps = 1e-6
    selected_bands = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06',
                      'B07', 'B08', 'B8A', 'B09', 'B11', 'B12']

def verificar_arquivos_existentes(diretorio_raiz):
    """Verifica se os arquivos CSV já existem"""
    # =========================================================================
    # MODIFICAÇÃO 1: Adicionado o novo arquivo de normalização [0, 1]
    # =========================================================================
    arquivos_esperados = [
        'serie_temporal_normalizada_neg_pos.csv',
        'serie_temporal_normalizada_zero_um.csv',
    ]
    
    arquivos_existentes = [f for f in arquivos_esperados
                           if os.path.exists(os.path.join(diretorio_raiz, f))]
    
    return arquivos_existentes

def verificar_dados_atualizados(diretorio_raiz, arquivos_existentes):
    """Verifica se há novas imagens após a última atualização dos CSVs"""
    if not arquivos_existentes:
        return False
        
    # Obtém a data de modificação mais recente dos CSVs
    ultima_atualizacao = max(
        os.path.getmtime(os.path.join(diretorio_raiz, f))
        for f in arquivos_existentes
    )
    
    # Verifica se há arquivos .tif mais recentes que os CSVs
    for root, _, files in os.walk(diretorio_raiz):
        for file in files:
            if file.endswith('.tif'):
                if os.path.getmtime(os.path.join(root, file)) > ultima_atualizacao:
                    return False
    
    return True

def renomear_bandas_sentinel(diretorio_raiz):
    """Padroniza os nomes dos arquivos de bandas para sentinel_BXX.tif"""
    padrao_antigo = re.compile(r'sentinel_\d+_B(\d{1,2}[A]?)\.tif$', re.IGNORECASE)
    
    for pasta_atual, _, arquivos in os.walk(diretorio_raiz):
        for arquivo in arquivos:
            if padrao_antigo.match(arquivo):
                banda_match = padrao_antigo.search(arquivo)
                if banda_match:
                    banda = banda_match.group(1)
                    # Lógica para formatar B8A corretamente e outros com zero à esquerda
                    if 'A' in banda.upper():
                        banda_formatada = banda.upper()
                    else:
                        banda_formatada = f"{int(re.sub(r'[^0-9]', '', banda)):02d}"
                    
                    novo_nome = f"sentinel_B{banda_formatada}.tif"
                    
                    os.rename(
                        os.path.join(pasta_atual, arquivo),
                        os.path.join(pasta_atual, novo_nome)
                    )

def carregar_bandas(diretorio):
    """Carrega bandas Sentinel-2 e redimensiona para tamanho comum"""
    max_shape = (0, 0)
    bandas_info = {}
    
    for arquivo in glob(os.path.join(diretorio, 'sentinel_*B*.tif')):
        with rasterio.open(arquivo) as src:
            nome_banda_match = re.search(r'B(\d{1,2}[A]?)', arquivo)
            if nome_banda_match:
                nome_banda = f"B{nome_banda_match.group(1).upper()}"
                bandas_info[nome_banda] = {
                    'path': arquivo,
                    'shape': src.shape
                }
                if src.shape[0] * src.shape[1] > max_shape[0] * max_shape[1]:
                    max_shape = src.shape
    
    bandas = {}
    for nome_banda, info in bandas_info.items():
        with rasterio.open(info['path']) as src:
            dados = src.read(1)
            if dados.shape != max_shape:
                dados = resize(dados, max_shape, preserve_range=True, anti_aliasing=True)
            bandas[nome_banda] = dados.flatten()
            
    return bandas

def calcular_indices(df_bandas):
    """Calcula todos os índices de vegetação mantendo os valores originais"""
    
    def NDVI(df): return (df['B08'] - df['B04']) / (df['B08'] + df['B04'] + CFG.eps)
    def GNDVI(df): return (df['B08'] - df['B03']) / (df['B08'] + df['B03'] + CFG.eps)
    def VARI(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] - df['B02'] + CFG.eps)
    def ARVI(df): return (df['B08'] - (2 * df['B04']) + df['B02']) / (df['B08'] + (2 * df['B04']) + df['B02'] + CFG.eps)
    def NDWI(df): return (df['B03'] - df['B08']) / (df['B08'] + df['B03'] + CFG.eps)
    def NDMI(df): return (df['B08'] - df['B11']) / (df['B08'] + df['B11'] + CFG.eps)
    def SAVI(df): return (df['B08'] - df['B11']) / ((df['B08'] + df['B11'] + 0.55) * (1 + 0.55))
    def MSI(df): return df['B11'] / (df['B8A'] + CFG.eps)
    #def EVI(df): return 2.5 * ((df['B8A'] - df['B04']) / (df['B8A'] + 6 * df['B04'] - 7.5 * df['B02'] + 1))
    def SIPI(df): return (df['B08'] - df['B02']) / (df['B08'] - df['B04'] + CFG.eps)
    def FIDET(df): return df['B12'] / (df['B8A'] * df['B09'] + CFG.eps)
    def NDRE(df): return (df['B09'] - df['B05']) / (df['B09'] + df['B05'] + CFG.eps)
    def brightness(df): return (df[CFG.selected_bands].apply(abs, axis=1).sum(axis=1)) / 11

    # Índices RGB
    def NGRDI(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] + CFG.eps)
    def RI(df): return (df['B04'] / (df['B03'] + CFG.eps)) - 1
    def ExR(df): return 2.5 * df['B04'] - 1.5 * df['B03']
    def GLI(df): return df['B03'] / (df['B04'] + df['B03'] + df['B02'] + CFG.eps)
    def VARIgreen(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] - df['B02'] + CFG.eps)
    def CIVE(df): return (0.441 * df['B04']) - (0.811 * df['B03']) + (0.385 * df['B02']) + 18.78745
    def VEG(df): return ((df['B04'] - df['B02']) * (df['B04'] - df['B03'])).pow(0.5) / (df['B04'] + df['B02'] + df['B03'] + CFG.eps)
    def VDVI(df): return (df['B03'] - df['B02']) / (df['B03'] + df['B02'] + CFG.eps)
    def IAF(df): return df['B08'] / (df['B04'] + CFG.eps)
    def ExG(df): return 2 * df['B03'] - df['B04'] - df['B02']
    def ExGR(df): return (3 * df['B03'] - 2.4 * df['B04'] - 1.5 * df['B08']) / (df['B03'] + 2.4 * df['B04'] + 1.5 * df['B08'] + CFG.eps)
    def COM(df): return df['B08'] / (df['B03'] + CFG.eps)

    df_resultado = df_bandas.copy()

    # Índices padrão
    df_resultado['NDVI'] = NDVI(df_bandas)
    df_resultado['GNDVI'] = GNDVI(df_bandas)
    df_resultado['VARI'] = VARI(df_bandas)
    df_resultado['ARVI'] = ARVI(df_bandas)
    df_resultado['NDWI'] = NDWI(df_bandas)
    df_resultado['NDMI'] = NDMI(df_bandas)
    df_resultado['SAVI'] = SAVI(df_bandas)
    df_resultado['MSI'] = MSI(df_bandas)
    #df_resultado['EVI'] = EVI(df_bandas)
    df_resultado['SIPI'] = SIPI(df_bandas)
    df_resultado['FIDET'] = FIDET(df_bandas)
    df_resultado['NDRE'] = NDRE(df_bandas)
    df_resultado['brightness'] = brightness(df_bandas)

    # Índices RGB adicionais
    df_resultado['NGRDI'] = NGRDI(df_bandas)
    df_resultado['RI'] = RI(df_bandas)
    df_resultado['ExR'] = ExR(df_bandas)
    df_resultado['GLI'] = GLI(df_bandas)
    df_resultado['VARIgreen'] = VARIgreen(df_bandas)
    df_resultado['CIVE'] = CIVE(df_bandas)
    df_resultado['VEG'] = VEG(df_bandas)
    df_resultado['VDVI'] = VDVI(df_bandas)
    df_resultado['IAF'] = IAF(df_bandas)
    df_resultado['ExG'] = ExG(df_bandas)
    df_resultado['ExGR'] = ExGR(df_bandas)
    df_resultado['COM'] = COM(df_bandas)

    return df_resultado

def normalizar_dataframe(df, range_min=-1, range_max=1):
    """
    Normaliza um DataFrame para o intervalo especificado.
    Mantém as colunas de identificação (fazenda, talhao, data) sem normalização.
    """
    colunas_para_normalizar = [col for col in df.columns if col not in ['fazenda', 'talhao', 'data']]
    df_normalizado = df.copy()
    
    for coluna in colunas_para_normalizar:
        min_val = df[coluna].min()
        max_val = df[coluna].max()

        # Evita divisão por zero se todos os valores na coluna forem iguais
        if (max_val - min_val) == 0:
            df_normalizado[coluna] = range_min if range_min == 0 else 0
            continue

        if range_min == -1 and range_max == 1:
            # Normalização para [-1, 1]
            df_normalizado[coluna] = 2 * ((df[coluna] - min_val) / (max_val - min_val + CFG.eps)) - 1
        elif range_min == 0 and range_max == 1:
            # Normalização para [0, 1]
            df_normalizado[coluna] = (df[coluna] - min_val) / (max_val - min_val + CFG.eps)
            
    return df_normalizado

def processar_series_temporais(diretorio_raiz, forcar_processamento=False):
    """Processa todas as pastas com imagens Sentinel-2 criando série temporal"""
    
    arquivos_existentes = verificar_arquivos_existentes(diretorio_raiz)
    dados_atualizados = verificar_dados_atualizados(diretorio_raiz, arquivos_existentes) and len(arquivos_existentes) == 2
    
    if not forcar_processamento and arquivos_existentes and dados_atualizados:
        print(f"\nArquivos CSV para '{os.path.basename(diretorio_raiz)}' já existem e estão atualizados.")
        return pd.read_csv(os.path.join(diretorio_raiz, 'serie_temporal_normalizada_neg_pos.csv'))

    print(f"\nIniciando processamento das imagens para '{os.path.basename(diretorio_raiz)}'...")

    renomear_bandas_sentinel(diretorio_raiz)

    dfs_temporais = []
    
    nome_fazenda = os.path.basename(os.path.normpath(diretorio_raiz))
    print(f"Processando fazenda: {nome_fazenda}")

    try:
        talhoes = natsort.natsorted([
            t for t in os.listdir(diretorio_raiz)
            if os.path.isdir(os.path.join(diretorio_raiz, t)) and t.startswith('Talhao_')
        ])
    except FileNotFoundError:
        print(f"ERRO: Diretório da fazenda não encontrado: {diretorio_raiz}")
        return None

    if not talhoes:
        print(f"Nenhum diretório 'Talhao_' encontrado em {diretorio_raiz}")
        return None

    for talhao in talhoes:
        caminho_talhao = os.path.join(diretorio_raiz, talhao)
        # Extrai o identificador do talhão do nome da pasta (ex: 'Talhao_FTU1.0299-0024')
        try:
            # Divide a string 'Talhao_IDENTIFICADOR' no primeiro '_' e pega a segunda parte
            identificador_talhao = talhao.split('_', 1)[1]
        except IndexError:
            print(f"AVISO: Formato de pasta de talhão inesperado: '{talhao}'. Não contém '_'. Pulando.")
            continue

        print(f"  Processando Talhão {identificador_talhao}")

        datas_pastas = natsort.natsorted([
            d for d in os.listdir(caminho_talhao)
            if os.path.isdir(os.path.join(caminho_talhao, d))
        ])

        for data_pasta in datas_pastas:
            caminho_data = os.path.join(caminho_talhao, data_pasta)
            try:
                data = datetime.strptime(data_pasta, '%Y-%m-%d').date()
            except ValueError:
                print(f"    AVISO: Pasta '{data_pasta}' não está no formato AAAA-MM-DD. Pulando.")
                continue

            print(f"    Processando data: {data}")
            
            bandas = carregar_bandas(caminho_data)
            if not bandas or not any(b in bandas for b in ['B02', 'B03', 'B04', 'B08']):
                print(f"      AVISO: Bandas essenciais não encontradas em '{caminho_data}'. Pulando data.")
                continue

            df_bandas = pd.DataFrame(bandas)
            df_indices = calcular_indices(df_bandas)

            # Gera estatísticas (max) para cada coluna de índice/banda
            # Usa a variável 'identificador_talhao' que agora é uma string correta
            stats_dict = {'fazenda': nome_fazenda, 'talhao': identificador_talhao, 'data': data}
            for coluna in df_indices.columns:
                stats_dict[f'{coluna}'] = df_indices[coluna].max()

            dfs_temporais.append(pd.DataFrame([stats_dict]))


    if dfs_temporais:
        try:
            df_final = pd.concat(dfs_temporais, ignore_index=True)
            df_final['data'] = pd.to_datetime(df_final['data'])
            df_final = df_final.sort_values(['fazenda', 'talhao', 'data'])

            if df_final is None or df_final.empty:
                print("\nAVISO: DataFrame final está vazio após a concatenação. Nada para salvar.")
                return None

            # --- Normaliza e salva o arquivo [-1, 1] ---
            df_normalizado_neg_pos = normalizar_dataframe(df_final, -1, 1)
            if df_normalizado_neg_pos is not None and not df_normalizado_neg_pos.empty:
                arquivo_saida_neg_pos = os.path.join(diretorio_raiz, 'serie_temporal_normalizada_neg_pos.csv')
                df_normalizado_neg_pos.to_csv(arquivo_saida_neg_pos, index=False)
                print(f"\nSérie temporal normalizada [-1, 1] salva em: {arquivo_saida_neg_pos}")

            # --- Normaliza e salva o arquivo [0, 1] ---
            df_normalizado_zero_um = normalizar_dataframe(df_final, 0, 1)
            if df_normalizado_zero_um is not None and not df_normalizado_zero_um.empty:
                arquivo_saida_zero_um = os.path.join(diretorio_raiz, 'serie_temporal_normalizada_zero_um.csv')
                df_normalizado_zero_um.to_csv(arquivo_saida_zero_um, index=False)
                print(f"Série temporal normalizada [0, 1] salva em: {arquivo_saida_zero_um}")

            return df_final

        except Exception as e:
            print(f"\nERRO CRÍTICO ao concatenar ou salvar arquivos CSV para {diretorio_raiz}:")
            traceback.print_exc()
            return None
    else:
        print(f"Nenhum dado foi processado para o diretório {diretorio_raiz}.")
        return None

if __name__ == "__main__":
    diretorio = input("Digite o caminho do diretório raiz: ")
    forcar = input("Forçar reprocessamento mesmo se arquivos existirem? (s/N): ").lower() == 's'
    
    inicio = datetime.now()
    print(f"\nInício do processamento: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    
    df_temporal = processar_series_temporais(diretorio, forcar_processamento=forcar)
    
    fim = datetime.now()
    tempo_execucao = fim - inicio
    print(f"\nFim do processamento: {fim.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tempo total de execução: {tempo_execucao}")

    if df_temporal is not None:
        print("\nProcesso concluído com sucesso!")
    else:
        print("\nProcesso concluído com erros ou avisos.")
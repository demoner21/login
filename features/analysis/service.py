import logging
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
import rasterio
from skimage.transform import resize

# Configurações do serviço de 
class CFG:
    eps = 1e-6
    # Lista de bandas que o GEE deve baixar
    BANDS_TO_DOWNLOAD = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12']

# Obtém o logger
logger = logging.getLogger(__name__)

class TchAtrAnalysisService:
    """
    Serviço para orquestrar a análise e predição de TCH e ATR.
    Este é o "Motor Central" da análise.
    """
    def __init__(self):
        """
        Inicializa o serviço. Os modelos e artefatos
        NÃO SÃO MAIS carregados aqui. Eles serão carregados sob demanda.
        """
        logger.info("TchAtrAnalysisService inicializado (carregamento de modelo sob demanda).")
        pass


    def _load_and_resize_bands(self, band_paths: Dict[str, Path]) -> Dict[str, np.ndarray]:
        """
        Carrega e redimensiona as bandas para um tamanho comum.
        Esta função substitui e corrige a 'carregar_bandas' do script.
        """
        bands_data = {}
        target_shape = None

        for band_name, file_path in band_paths.items():
            try:
                with rasterio.open(file_path) as src:
                    if target_shape is None or (src.height * src.width 
 > target_shape[0] * target_shape[1]):
                        target_shape = (src.height, src.width)
            except rasterio.errors.RasterioIOError:
                raise IOError(f"Erro ao ler o arquivo da banda {band_name}: {file_path}")

        if target_shape is None:
            raise ValueError("Nenhuma banda pôde ser lida para determinar o shape alvo.")

        for band_name, file_path in band_paths.items():
            with rasterio.open(file_path) as src:
                data = src.read(1)
                if data.shape != target_shape:
                    data = resize(data, target_shape, preserve_range=True, anti_aliasing=True)
          
                bands_data[band_name] = data.flatten()
        
        return bands_data

    def _calculate_indices(self, df_bandas: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula todos os índices de vegetação.
        (Lógica idêntica à fornecida, mantida como está)
        """
        def NDVI(df): return (df['B08'] - df['B04']) / (df['B08'] + df['B04'] + CFG.eps)
        def GNDVI(df): return (df['B08'] - df['B03']) / (df['B08'] + df['B03'] + CFG.eps)
        def VARI(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] - df['B02'] + CFG.eps)
        def ARVI(df): return (df['B08'] - (2 * df['B04']) + df['B02']) / (df['B08'] + (2 * df['B04']) + df['B02'] + CFG.eps)
        def NDWI(df): return (df['B03'] - df['B08']) / (df['B08'] + df['B03'] + CFG.eps)
        def NDMI(df): return (df['B08'] - df['B11']) / (df['B08'] + df['B11'] + CFG.eps)
        def SAVI(df): return (df['B08'] - df['B11']) / ((df['B08'] + df['B11'] + 0.55) * (1 + 0.55))
        def MSI(df): return df['B11'] / (df['B8A'] + CFG.eps)
        def SIPI(df): return (df['B08'] - df['B02']) / (df['B08'] - df['B04'] + CFG.eps)
        def FIDET(df): return df['B12'] / (df['B8A'] * df['B09'] + CFG.eps)
        def NDRE(df): return (df['B09'] - df['B05']) / (df['B09'] + df['B05'] + CFG.eps)
        def brightness(df): return (df[CFG.BANDS_TO_DOWNLOAD].apply(abs, axis=1).sum(axis=1)) / 12
        def NGRDI(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] + CFG.eps)
        def RI(df): return (df['B04'] / (df['B03'] + CFG.eps)) - 1
        def GLI(df): return df['B03'] / (df['B04'] + df['B03'] + df['B02'] + CFG.eps)
        def VARIgreen(df): return (df['B03'] - df['B04']) / (df['B03'] + df['B04'] - df['B02'] + CFG.eps)
        def CIVE(df): return (0.441 * df['B04']) - (0.811 * df['B03']) + (0.385 * df['B02']) + 18.78745
        def VEG(df): return ((df['B04'] - df['B02']) * (df['B04'] - df['B03']))**.5 / (df['B04'] + df['B02'] + df['B03'] + CFG.eps)
        def VDVI(df): return (df['B03'] - df['B02']) / (df['B03'] + df['B02'] + CFG.eps)
        def IAF(df): return df['B08'] / (df['B04'] + CFG.eps)
        def ExG(df): return 2 * df['B03'] - df['B04'] - df['B02']
        def ExGR(df): return (3 * df['B03'] - 2.4 * df['B04'] - 1.5 * df['B08']) / (df['B03'] + 2.4 * df['B04'] + 1.5 * df['B08'] + CFG.eps)
        def COM(df): return df['B08'] / (df['B03'] + CFG.eps)
        
        df_resultado = df_bandas.copy()

        # Calcula e adiciona cada índice
        df_resultado['NDVI'] = NDVI(df_bandas)
        df_resultado['GNDVI'] = GNDVI(df_bandas)
        df_resultado['VARI'] = VARI(df_bandas)
        df_resultado['ARVI'] = ARVI(df_bandas)
        df_resultado['NDWI'] = NDWI(df_bandas)
        df_resultado['NDMI'] = NDMI(df_bandas)
        df_resultado['SAVI'] = SAVI(df_bandas)
        df_resultado['MSI'] = MSI(df_bandas)
        df_resultado['SIPI'] = SIPI(df_bandas)
        df_resultado['FIDET'] = FIDET(df_bandas)
        df_resultado['NDRE'] = NDRE(df_bandas)
        df_resultado['brightness'] = brightness(df_bandas)
        df_resultado['NGRDI'] = NGRDI(df_bandas)
        df_resultado['RI'] = RI(df_bandas)
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

    def _normalize_dataframe(self, df: pd.DataFrame, feature_stats: dict) -> pd.DataFrame:
        """
        Normaliza as colunas do DataFrame para o intervalo [-1, 1]
        usando o dicionário de estatísticas carregado.
        """
        df_normalizado = df.copy()
        
        for col in df_normalizado.columns:
            if col in feature_stats:
                stats = feature_stats[col]
                min_val = stats.get('min')
                max_val = stats.get('max')

                if min_val is not None and max_val is not None:
                    range_val = max_val - min_val
                    if range_val > 0:
                        df_normalizado[col] = 2 * ((df_normalizado[col] - min_val) / range_val) - 1
                    else:
                        df_normalizado[col] = 0
        
        return df_normalizado

    def _prepare_image_features(self, band_paths: Dict[str, Path]) -> pd.DataFrame:
        """
        Prepara um DataFrame com todas as features 
 derivadas das imagens.
        """
        bands_data = self._load_and_resize_bands(band_paths)
        df_bands = pd.DataFrame(bands_data)
        df_indices = self._calculate_indices(df_bands)
        df_aggregated = df_indices.max().to_frame().T
        return df_aggregated

    def _predict(self, image_features_df: pd.DataFrame, hectares: float, model_artifacts: dict) -> float:
        """
        Adiciona features externas, normaliza e executa a predição.
        USA OS ARTEFATOS DO MODELO FORNECIDOS.
        """
        # Copia para não alterar o DataFrame original
        feature_vector = image_features_df.copy()

        # Adiciona a feature 'Hectares' que vem dos metadados da ROI
        feature_vector['Hectares'] = hectares
        
        # Pega a lista de features do dicionário de artefatos
        model_feature_list = model_artifacts['model_feature_list']
        
        # Garante que o DataFrame final tenha todas as colunas que o modelo espera.
        final_vector = pd.DataFrame(columns=model_feature_list)
        final_vector = pd.concat([final_vector, feature_vector], ignore_index=True).fillna(0)
        
        # Seleciona e reordena as colunas para bater com a ordem exata do modelo
        vector_for_scaling = final_vector[model_feature_list]

        # Normaliza 
        vector_normalized = self._normalize_dataframe(
            vector_for_scaling, 
            feature_stats=model_artifacts['feature_stats']
        )
        
        # Realiza a predição (usando o modelo correto)
        prediction = model_artifacts['model'].predict(vector_normalized)
        
        return float(prediction[0])

    def run_analysis_pipeline(self, band_paths: Dict[str, Path], hectares: float, model_artifacts: dict) -> Dict:
        """
        Ponto de entrada público para executar todo o pipeline de análise.
        AGORA REQUER OS ARTEFATOS DO MODELO.
        """
        try:
            # 1. Prepara features das imagens
            image_features = self._prepare_image_features(band_paths)
            
            # 2. Adiciona features externas e faz a predição
            predicted_value = self._predict(
                image_features, 
                hectares, 
                model_artifacts
            )
            
            logger.info(f"Análise para o conjunto de bandas concluída. Valor predito: {predicted_value}")
            
            return {
                "status": "success",
                "predicted_atr": predicted_value
            }
        except Exception as e:
            logger.error(f"Falha no pipeline de análise para o conjunto de bandas: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

# Instancia o serviço sem carregar modelos
analysis_service = TchAtrAnalysisService()
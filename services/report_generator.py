import logging
from io import BytesIO
from typing import Dict, Any, List
from datetime import date
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import rasterio
from fpdf import FPDF, HTMLMixin 
from pathlib import Path

logger = logging.getLogger(__name__)

def calculate_ndvi(nir_band: np.ndarray, red_band: np.ndarray) -> np.ndarray:
    ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10) 
    ndvi = np.clip(ndvi, -1, 1)
    return ndvi

class PDF(FPDF, HTMLMixin):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Portal Multiespectral - Relatório de Análise ATR', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

class ReportGeneratorService:
    
    def _create_heatmap(self, band_paths: Dict[str, Path], threshold: float) -> tuple[BytesIO, np.ndarray]:
        try:
            b04_path = band_paths.get('B04')
            b08_path = band_paths.get('B08')

            if not b04_path or not b08_path or not b04_path.exists() or not b08_path.exists():
                logger.error(f"Caminhos de banda B04 ({b04_path}) e B08 ({b08_path}) não fornecidos ou não encontrados.")
                raise FileNotFoundError("Arquivos de banda necessários não encontrados para cálculo do NDVI.")

            with rasterio.open(b04_path) as src_red, rasterio.open(b08_path) as src_nir:
                b04 = src_red.read(1).astype('float64')
                b08 = src_nir.read(1).astype('float64')
                
                if b04.shape != b08.shape:
                    logger.warning("Shapes das bandas B04 e B08 não coincidem. A plotagem pode ser imprecisa.")

            ndvi_data = calculate_ndvi(b08, b04)
            
            fig, ax = plt.subplots(figsize=(8, 8))
            
            colors = ['#d73027', '#fee090', '#a6d96a', '#1a9850']
            ndvi_cmap = LinearSegmentedColormap.from_list("ndvi_custom", colors, N=256)
            
            if threshold > 0.0:
                logger.info(f"Aplicando destaque UX, atenuando áreas abaixo de {threshold}")
            
                ax.imshow(ndvi_data, cmap=ndvi_cmap, vmin=-1, vmax=1, alpha=0.3) 
                
                high_ndvi_mask = ndvi_data > threshold
                highlight_data = np.ma.masked_where(~high_ndvi_mask, ndvi_data)
                im = ax.imshow(highlight_data, cmap=ndvi_cmap, vmin=-1, vmax=1, alpha=1.0)
                
                ax.set_title(f'Mapa de NDVI (Destaque > {threshold:.3f})', pad=10)
            else:
                im = ax.imshow(ndvi_data, cmap=ndvi_cmap, vmin=-1, vmax=1) 
                ax.set_title('Mapa de NDVI Completo', pad=10) 
            
            ax.axis('off')
            
            plt.tight_layout(pad=0)

            buffer = BytesIO()
            plt.savefig(
                buffer,
                format='png',
                bbox_inches='tight',
                pad_inches=0.0,
                transparent=True
            )
            buffer.seek(0)
            plt.close(fig)
            return buffer, ndvi_data
        
        except Exception as e:
            logger.error(f"Erro ao criar mapa de calor NDVI: {e}", exc_info=True)
            return BytesIO(b''), np.array([]) 

    def _create_histogram(self, ndvi_data: np.ndarray) -> BytesIO:
        valid_ndvi = ndvi_data[~np.isnan(ndvi_data) & (ndvi_data >= -1) & (ndvi_data <= 1)]
        
        if valid_ndvi.size == 0:
            logger.warning("Nenhum dado NDVI válido para gerar o histograma.")
            return BytesIO(b'')

        stats = {
            'Média': valid_ndvi.mean(),
            'Mediana': np.median(valid_ndvi),
            'Desvio Padrão': valid_ndvi.std(),
            'Min': valid_ndvi.min(),
            'Máx': valid_ndvi.max(),
        }

        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.hist(valid_ndvi.flatten(), bins=50, color='#38761d', alpha=0.8)
        ax.set_title('Distribuição de Valores NDVI', fontsize=14)
        ax.set_xlabel('Valor NDVI', fontsize=12)
        ax.set_ylabel('Frequência', fontsize=12)
        ax.grid(True, alpha=0.3)

        stats_text = '\n'.join([f'{k}: {v:.3f}' for k, v in stats.items()])
        ax.text(0.98, 0.95, stats_text,
                 transform=ax.transAxes,
                 verticalalignment='top',
                 horizontalalignment='right',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
                 fontsize=10)

        plt.tight_layout(pad=0.5)

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close(fig)
        return buffer

    def generate_report(
        self,
        job_details: Dict[str, Any],
        results: List[Dict[str, Any]],
        roi_metadata: Dict[str, Any],
        image_buffer: BytesIO,
        histogram_buffer: BytesIO,
        threshold: float
    ) -> BytesIO:
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        pdf.set_font('Arial', '', 10)
        
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(0, 8, '1. Detalhes da Região e Análise', 0, 1, 'L', 1)
        pdf.ln(2)

        pdf.set_font('Arial', '', 10) 

        pdf.cell(50, 6, 'Propriedade:', 0, 0, 'L')
        pdf.cell(0, 6, roi_metadata.get('nome_propriedade', 'N/A'), 0, 1, 'L')
        
        pdf.cell(50, 6, 'Talhão:', 0, 0, 'L')
        pdf.cell(0, 6, f"{roi_metadata.get('nome_talhao', 'N/A')} (ID: {roi_metadata.get('roi_id')})", 0, 1, 'L')
        
        pdf.cell(50, 6, 'Data de Emissão:', 0, 0, 'L')
        pdf.cell(0, 6, date.today().strftime('%d/%m/%Y'), 0, 1, 'L')
        
        pdf.cell(50, 6, 'Área Total (ha):', 0, 0, 'L')
        pdf.cell(0, 6, str(roi_metadata.get('metadata', {}).get('area_ha', 'N/A')), 0, 1, 'L')
        
        pdf.ln(5)
        
        pdf.set_fill_color(200, 255, 220)
        pdf.cell(0, 8, '2. Resultados Principais de ATR Predito', 0, 1, 'L', 1)
        pdf.ln(2)
        
        pdf.set_font('Arial', 'B', 10)
        col_width = pdf.w / 3.5
        pdf.cell(col_width, 7, 'Data', 1, 0, 'C')
        pdf.cell(col_width, 7, 'ATR Predito', 1, 1, 'C')
        
        pdf.set_font('Arial', '', 10)
        for result in results:
            pdf.cell(col_width, 6, result['date_analyzed'].strftime('%Y-%m-%d'), 1, 0, 'C')
            pdf.cell(col_width, 6, f"{result['predicted_atr']:.4f}", 1, 1, 'C')
        
        pdf.ln(5)
        
        pdf.set_fill_color(255, 255, 200)
        pdf.cell(0, 8, '3. Visualização da Análise (Mapa de NDVI)', 0, 1, 'L', 1)
        pdf.ln(2)
        
        if image_buffer.getbuffer().nbytes > 0:
            pdf.image(image_buffer, x=pdf.get_x() + 10, y=pdf.get_y(), w=150, type='PNG')
        else:
            pdf.multi_cell(0, 5, "Não foi possível gerar a imagem do mapa de NDVI. Verifique se os arquivos de banda B04 e B08 estavam disponíveis.")
            
        pdf.ln(155) 
        
        pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 8, '4. Notas e Observações', 0, 1, 'L', 1)
        pdf.ln(2)
        
        pdf.multi_cell(0, 5, f'Este relatório é uma predição de ATR baseada em um modelo de aprendizado de máquina e utiliza o mapa de NDVI para visualização da saúde da vegetação.\n\nLimiar de Destaque no NDVI: {threshold:.3f}')
        
        pdf.add_page()
        
        pdf.set_fill_color(220, 220, 255)
        pdf.cell(0, 8, '5. Distribuição de Frequência do NDVI', 0, 1, 'L', 1)
        pdf.ln(2)

        if histogram_buffer.getbuffer().nbytes > 0:
            pdf.image(histogram_buffer, x=15, y=pdf.get_y() + 10, w=180, type='PNG')
        else:
            pdf.multi_cell(0, 5, "Não foi possível gerar o histograma de NDVI.")

        pdf.ln(120)
        
        pdf_buffer = BytesIO()
        pdf.output(pdf_buffer) 
        pdf_buffer.seek(0)
        return pdf_buffer

report_generator = ReportGeneratorService()
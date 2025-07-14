import {
    startBatchDownloadForIds,
    startVarietyDownloadForProperty,
    uploadAnalysisFile,
    getAnalysisJobStatus
} from '../module/api.js';
import { initializeMapWithLayers } from '../module/map-utils.js';
import { normalizeName } from '../module/text-normalizer.js';

// Variáveis de estado para a visualização de detalhes
let roiMap;
let roiLayer;
const talhoesSelecionados = new Set();

/**
 * Lida com o envio do formulário de upload para análise.
 */
async function handleAnalysisUpload(e) {
    e.preventDefault();
    const roiId = document.getElementById('analysisRoiId').value;
    const fileInput = document.getElementById('analysisZipFile');
    const statusContainer = document.getElementById('analysisStatusContainer');
    const submitBtn = document.getElementById('startAnalysisBtn');

    if (!fileInput.files || fileInput.files.length === 0) {
        statusContainer.innerHTML = `<div class="warning">Por favor, selecione um arquivo .zip para enviar.</div>`;
        return;
    }

    const file = fileInput.files[0];
    statusContainer.innerHTML = `<div class="info"><span class="loading-spinner"></span>Enviando arquivo e iniciando job...</div>`;
    submitBtn.disabled = true;

    try {
        const result = await uploadAnalysisFile(roiId, file);
        statusContainer.innerHTML = `<div class="success">${result.message} (Job ID: ${result.job_id})</div>`;
        pollJobStatus(result.job_id, statusContainer);
    } catch (error) {
        statusContainer.innerHTML = `<div class="error">Erro ao iniciar job: ${error.message}</div>`;
    } finally {
        submitBtn.disabled = false;
        fileInput.value = '';
    }
}

/**
 * Verifica o status de um job de análise periodicamente.
 */
function pollJobStatus(jobId, statusContainer) {
    statusContainer.innerHTML += `<div id="job-${jobId}-status" class="info" style="margin-top: 10px;">Aguardando processamento...</div>`;
    const statusEl = document.getElementById(`job-${jobId}-status`);

    const intervalId = setInterval(async () => {
        try {
            const job = await getAnalysisJobStatus(jobId);

            if (job.status === 'PROCESSING') {
                statusEl.className = 'info';
                statusEl.innerHTML = `<span class="loading-spinner"></span>Status: Processando...`;
            } else if (job.status === 'COMPLETED') {
                clearInterval(intervalId);
                statusEl.className = 'success';
                let resultsHtml = '<h4>Análise Concluída</h4><ul>';
                job.results.forEach(res => {
                    resultsHtml += `<li>Data: ${res.date_analyzed} - ATR Predito: <strong>${res.predicted_atr.toFixed(4)}</strong></li>`;
                });
                resultsHtml += '</ul>';
                statusEl.innerHTML = resultsHtml;
            } else if (job.status === 'FAILED') {
                clearInterval(intervalId);
                statusEl.className = 'error';
                statusEl.innerHTML = `<strong>Falha na Análise:</strong> ${job.error_message}`;
            }
        } catch (error) {
            clearInterval(intervalId);
            statusEl.className = 'error';
            statusEl.textContent = `Erro ao consultar status do job: ${error.message}`;
        }
    }, 5000); // Verifica a cada 5 segundos
}

/**
 * Função auxiliar para verificar a existência de um arquivo ZIP no servidor.
 */
function pollForFile(downloadUrl, statusEl) {
    statusEl.innerHTML = `<div class="info">Processando no servidor... Por favor, aguarde. O download começará automaticamente.</div>`;
    
    const intervalId = setInterval(async () => {
        try {
            const response = await fetch(downloadUrl, { method: 'HEAD' });
            if (response.ok) {
                clearInterval(intervalId);
                statusEl.innerHTML = `<div class="success">Arquivo pronto! Iniciando download...</div>`;
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = downloadUrl.split('/').pop();
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
        } catch (error) {
            console.error("Erro na verificação do arquivo:", error);
            statusEl.innerHTML = `<div class="error">Ocorreu um erro ao verificar o status do arquivo.</div>`;
            clearInterval(intervalId);
        }
    }, 5000);
}

/**
 * Renderiza o conteúdo da tela de detalhes da ROI.
 */
function renderROIDetailsContent(roi) {
    // Busca as variedades únicas para o dropdown
    const variedadesNaPropriedade = new Set();
    if (roi.geometria && roi.geometria.type === 'FeatureCollection') {
        roi.geometria.features.forEach(feature => {
            if (feature.properties && feature.properties.variedade) {
                variedadesNaPropriedade.add(feature.properties.variedade);
            }
        });
    }
    const variedadesOptions = [...variedadesNaPropriedade].map(v => `<option value="${v}">${v}</option>`).join('');

    const roiInfoContainer = document.getElementById('roiInfo');
    
    // TEMPLATE HTML UNIFICADO
    roiInfoContainer.innerHTML = `
        <p><strong>Propriedade:</strong> ${roi.nome_propriedade || roi.nome}</p>
        <p><strong>Descrição:</strong> ${roi.descricao || 'Não informada'}</p>

        <hr>

        <div class="analysis-section" style="margin-top: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
            <h4>Análise de TCH & ATR (com Upload Manual)</h4>
            <p>Faça o upload de um arquivo .zip com as imagens para esta ROI para iniciar uma nova análise.</p>
            <form id="analysisUploadForm">
                <input type="hidden" id="analysisRoiId" value="${roi.roi_id}">
                <div>
                    <label for="analysisZipFile">Arquivo .zip:</label>
                    <input type="file" id="analysisZipFile" name="file" accept=".zip" required style="display: inline-block; width: auto;">
                </div>
                <button type="submit" id="startAnalysisBtn">Iniciar Análise</button>
            </form>
            <div id="analysisStatusContainer" style="margin-top: 15px;"></div>
        </div>

        <div class="batch-download-form" style="margin-top: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
             <h4>Download GEE por Seleção de Talhões</h4>
             <p>Selecione os talhões no mapa e defina o período para iniciar o download.</p>
             <div>
                 <label for="geeStartDate">Data Início:</label>
                 <input type="date" id="geeStartDate" required>
             </div>
             <div>
                 <label for="geeEndDate">Data Fim:</label>
                 <input type="date" id="geeEndDate" required>
             </div>
             <div>
                <label for="geeCloudPercentage">Máx. Nuvens (%):</label>
                <input type="number" id="geeCloudPercentage" value="5" min="0" max="100" style="width: 80px;">
            </div>
             <div id="lote-actions" style="margin-top: 15px; display: none;">
                 <button id="processarLoteBtn" class="btn-process">
                     Iniciar Download de Lote (<span id="contadorLote">0</span>)
                 </button>
             </div>
             <div id="geeDownloadStatus" style="margin-top: 10px;"></div>
        </div>

        <div class="variety-download-form" style="margin-top: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
            <h4>Download GEE por Variedade</h4>
            ${variedadesNaPropriedade.size > 0 ? `
                <form id="propertyVarietyDownloadForm">
                    <div>
                        <label for="propertyVarietySelect">Variedade:</label>
                        <select id="propertyVarietySelect">
                            <option value="">-- Nenhuma (mostrar todos) --</option>
                            ${variedadesOptions}
                        </select>
                    </div>
                    <div>
                        <label for="varietyStartDate">Data Início:</label>
                        <input type="date" id="varietyStartDate" required>
                    </div>
                    <div>
                        <label for="varietyEndDate">Data Fim:</label>
                        <input type="date" id="varietyEndDate" required>
                    </div>
                    <div>
                        <label for="varietyCloudPercentage">Máx. Nuvens (%):</label>
                        <input type="number" id="varietyCloudPercentage" value="5" min="0" max="100" style="width: 80px;">
                    </div>
                    <button type="submit">Iniciar Download da Variedade</button>
                </form>
            ` : '<p>Nenhuma variedade encontrada nos dados desta propriedade.</p>'}
            <div id="propertyVarietyDownloadStatus" style="margin-top: 10px;"></div>
        </div>
    `;
}

/**
 * Configura os event listeners para os formulários e botões na tela de detalhes.
 */
function setupDetailsEventListeners(roi) {
    document.getElementById('analysisUploadForm').addEventListener('submit', handleAnalysisUpload);

    const btnProcessarLote = document.getElementById('processarLoteBtn');
    if (btnProcessarLote) {
        btnProcessarLote.onclick = async () => {
            const geeDownloadStatusEl = document.getElementById('geeDownloadStatus');
            const totalSelecionados = talhoesSelecionados.size;
            if (totalSelecionados === 0) {
                geeDownloadStatusEl.innerHTML = '<div class="warning">Nenhum talhão selecionado.</div>';
                return;
            }
            const startDate = document.getElementById('geeStartDate').value;
            const endDate = document.getElementById('geeEndDate').value;
            const cloudPercentage = document.getElementById('geeCloudPercentage').value;
            if (!startDate || !endDate) {
                geeDownloadStatusEl.innerHTML = '<div class="error">Por favor, selecione as datas de início e fim.</div>';
                return;
            }
            const idsParaProcessar = Array.from(talhoesSelecionados);
            geeDownloadStatusEl.innerHTML = `<div class="info">Iniciando processo para ${totalSelecionados} talhões...</div>`;
            btnProcessarLote.disabled = true;
            try {
                const result = await startBatchDownloadForIds(idsParaProcessar, startDate, endDate, cloudPercentage);
                pollForFile(result.task_details.download_link, geeDownloadStatusEl);
                talhoesSelecionados.clear();
                document.getElementById('contadorLote').textContent = 0;
                document.getElementById('lote-actions').style.display = 'none';
                if (roiLayer) roiLayer.resetStyle();
            } catch (error) {
                geeDownloadStatusEl.innerHTML = `<div class="error">Erro ao iniciar tarefa: ${error.message}</div>`;
            } finally {
                btnProcessarLote.disabled = false;
            }
        };
    }

    const propertyVarietyDownloadForm = document.getElementById('propertyVarietyDownloadForm');
    if (propertyVarietyDownloadForm) {
        propertyVarietyDownloadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const statusEl = document.getElementById('propertyVarietyDownloadStatus');
            const variety = document.getElementById('propertyVarietySelect').value;
            const startDate = document.getElementById('varietyStartDate').value;
            const endDate = document.getElementById('varietyEndDate').value;
            const cloud = document.getElementById('varietyCloudPercentage').value;

            if (!variety || !startDate || !endDate) {
                statusEl.innerHTML = '<div class="error">Por favor, preencha todos os campos.</div>';
                return;
            }
            statusEl.innerHTML = '<div class="info">Iniciando tarefa de download...</div>';
            try {
                const result = await startVarietyDownloadForProperty(roi.roi_id, variety, startDate, endDate, cloud);
                pollForFile(result.task_details.download_link, statusEl);
            } catch (error) {
                statusEl.innerHTML = `<div class="error">Erro ao iniciar tarefa: ${error.message}</div>`;
            }
        });
    }
}

/**
 * Inicializa e configura o mapa interativo com os talhões da ROI.
 */
function setupInteractiveMap(roi) {
    if (roiMap) {
        roiMap.remove();
        roiMap = null;
    }
    roiMap = initializeMapWithLayers('map');

    if (!roi.geometria || roi.geometria.type !== 'FeatureCollection') {
        console.warn("A geometria recebida não é uma FeatureCollection ou está vazia.", roi);
        return;
    }

    const estiloPadrao = { color: '#FF8C00', weight: 2, opacity: 0.9, fillColor: '#FFA500', fillOpacity: 0.2 };
    const estiloHover = { weight: 4, fillOpacity: 0.5 };
    const estiloSelecionado = { fillColor: '#3388ff', color: '#005eff', weight: 3, fillOpacity: 0.6 };
    const estiloVariedadeDestaque = { color: '#00FF00', weight: 3, fillOpacity: 0.7, fillColor: '#00FF00' };

    const atualizarBotaoLote = () => {
        const totalSelecionados = talhoesSelecionados.size;
        document.getElementById('contadorLote').textContent = totalSelecionados;
        document.getElementById('lote-actions').style.display = totalSelecionados > 0 ? 'block' : 'none';
    };

    roiLayer = L.geoJSON(roi.geometria, {
        style: estiloPadrao,
        onEachFeature: (feature, layer) => {
            const props = feature.properties;
            const talhaoId = props.roi_id;
            layer.bindTooltip(`<strong>Talhão:</strong> ${normalizeName(props.nome_talhao) || 'N/A'}<br><strong>Variedade:</strong> ${props.variedade || 'N/A'}<br><strong>Área:</strong> ${props.area_ha ? `${props.area_ha.toFixed(2)} ha` : 'N/A'}`);

            layer.on('click', () => {
                if (!talhaoId) return;
                if (talhoesSelecionados.has(talhaoId)) {
                    talhoesSelecionados.delete(talhaoId);
                } else {
                    talhoesSelecionados.add(talhaoId);
                }
                atualizarBotaoLote();
                layer.setStyle(talhoesSelecionados.has(talhaoId) ? estiloSelecionado : estiloPadrao);
            });

            layer.on({
                mouseover: (e) => e.target.setStyle(estiloHover),
                mouseout: (e) => talhoesSelecionados.has(talhaoId) ? e.target.setStyle(estiloSelecionado) : roiLayer.resetStyle(e.target)
            });
        }
    }).addTo(roiMap);

    if (roiLayer.getBounds().isValid()) {
        roiMap.fitBounds(roiLayer.getBounds());
    }

    const propertyVarietySelect = document.getElementById('propertyVarietySelect');
    if (propertyVarietySelect) {
        propertyVarietySelect.addEventListener('change', (e) => {
            const variedadeSelecionada = e.target.value;
            roiLayer.eachLayer(layer => {
                const props = layer.feature.properties;
                const isSelected = talhoesSelecionados.has(props.roi_id);
                if (isSelected) {
                    layer.setStyle(estiloSelecionado);
                } else if (variedadeSelecionada && props.variedade === variedadeSelecionada) {
                    layer.setStyle(estiloVariedadeDestaque);
                } else {
                    layer.setStyle(estiloPadrao);
                }
            });
        });
    }
}

/**
 * Ponto de entrada principal para exibir a tela de detalhes de uma ROI.
 */
export function displayROIDetails(roi) {
    // Limpa seleções anteriores
    talhoesSelecionados.clear();

    // Esconde a lista e mostra a tela de detalhes
    document.getElementById('roiFilters').classList.add('hidden');
    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('paginationControls').classList.add('hidden');
    document.getElementById('roiDetails').classList.remove('hidden');
    document.getElementById('propertySelect').disabled = true;
    document.getElementById('varietySelect').disabled = true;

    // Renderiza o conteúdo dinâmico (formulários e informações)
    renderROIDetailsContent(roi);

    // Configura os event listeners para os novos elementos
    setupDetailsEventListeners(roi);

    // Configura o mapa interativo
    setupInteractiveMap(roi);
}
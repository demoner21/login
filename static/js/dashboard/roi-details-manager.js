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
    // const roiId = document.getElementById('analysisRoiId').value;
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
        const result = await uploadAnalysisFile(file); // roiId, 
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
function pollJobStatus(jobId, statusEl) {
    statusEl.innerHTML = `<div class="info"><span class="loading-spinner"></span>A tarefa em lote foi iniciada... Verificando status.</div>`;
    let attempts = 0;
    const maxAttempts = 120; // 10 minutos de timeout

    const intervalId = setInterval(async () => {
        if (++attempts > maxAttempts) {
            clearInterval(intervalId);
            statusEl.innerHTML = `<div class="error">Timeout: A tarefa demorou muito para responder.</div>`;
            return;
        }

        try {
            // A rota de consulta é a mesma, mas agora ela retorna uma estrutura hierárquica
            const job = await getAnalysisJobStatus(jobId);
            
            let statusHTML = '';
            // Renderiza o status do Job Pai
            statusHTML += `<div><strong>Job em Lote #${job.job_id}</strong> - Status: <span class="status-${job.status.toLowerCase()}">${job.status}</span></div>`;
            
            if (job.error_message) {
                 statusHTML += `<div class="error-details">Motivo da falha: ${job.error_message}</div>`;
            }

            // Renderiza o status dos Jobs Filhos
            if (job.child_jobs && job.child_jobs.length > 0) {
                statusHTML += '<ul class="child-job-list">';
                job.child_jobs.forEach(child => {
                    statusHTML += `<li>Talhão (ROI ID: ${child.roi_id}) - Status: <span class="status-${child.status.toLowerCase()}">${child.status}</span>`;
                    if (child.status === 'COMPLETED' && child.results.length > 0) {
                        statusHTML += `<ul>`;
                        child.results.forEach(res => {
                             statusHTML += `<li>Data: ${res.date_analyzed} -> ATR Predito: ${res.predicted_atr.toFixed(4)}</li>`;
                        });
                        statusHTML += `</ul>`;
                    } else if (child.status === 'FAILED') {
                        statusHTML += `<div class="error-details-child">Falha: ${child.error_message}</div>`;
                    }
                    statusHTML += '</li>';
                });
                statusHTML += '</ul>';
            }

            statusEl.innerHTML = statusHTML;

            // Para o polling se o job pai estiver concluído ou falhou
            if (job.status === 'COMPLETED' || job.status === 'FAILED') {
                clearInterval(intervalId);
            }

        } catch (error) {
            clearInterval(intervalId);
            statusEl.innerHTML = `<div class="error">Erro de rede ao consultar o status da tarefa: ${error.message}</div>`;
            console.error("Polling error:", error);
        }
    }, 5000); // Verifica a cada 5 segundos
}

/**
 * Função auxiliar para verificar a existência de um arquivo ZIP no servidor.
 */
function pollDownloadJobStatus(jobId, statusEl) {
    statusEl.innerHTML = `<div class="info"><span class="loading-spinner"></span>A tarefa de download foi iniciada... Verificando status.</div>`;
    let attempts = 0;
    const maxAttempts = 12;

    const intervalId = setInterval(async () => {
        if (++attempts > maxAttempts) {
            clearInterval(intervalId);
            statusEl.innerHTML = `<div class="error">Timeout: A tarefa de download demorou muito para responder.</div>`;
            return;
        }

        try {
            const response = await fetch(`/api/v1/roi/jobs/${jobId}/status`);
            if (!response.ok) {
                if (response.status === 404) {
                    console.log(`Job de download ${jobId} ainda não encontrado, tentando novamente...`);
                    return;
                }
                clearInterval(intervalId);
                statusEl.innerHTML = `<div class="error">Erro ao consultar o status da tarefa de download.</div>`;
                return;
            }

            const job = await response.json();
            
            let statusHTML = `<div class="info"><strong>Status do Download:</strong> ${job.message || job.status}</div>`;

            switch (job.status) {
                case 'COMPLETED':
                    clearInterval(intervalId);
                    statusEl.innerHTML = `<div class="success"><strong>Download Concluído!</strong><br>${job.message} Iniciando download do arquivo...</div>`;
                    
                    const downloadUrl = `/api/v1/roi/jobs/${job.job_id}/result`;
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = downloadUrl.split('/').pop() || 'download.zip';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    break;
                case 'FAILED':
                    clearInterval(intervalId);
                    statusEl.innerHTML = `<div class="error"><strong>Falha na Tarefa de Download</strong><br>${job.message || 'Ocorreu um erro desconhecido.'}</div>`;
                    break;
                case 'PROCESSING':
                    statusEl.innerHTML = `<div class="info"><span class="loading-spinner"></span>Processando download...<br><small>${job.message || ''}</small></div>`;
                    break;
                default:
                    statusEl.innerHTML = `<div class="info"><span class="loading-spinner"></span>Aguardando na fila...<br><small>${job.status}</small></div>`;
                    break;
            }

        } catch (error) {
            clearInterval(intervalId);
            statusEl.innerHTML = `<div class="error">Erro de rede ao consultar o status da tarefa de download.</div>`;
            console.error("Polling de download error:", error);
        }
    }, 5000); // Verifica a cada 5 segundos
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
        <p><strong>Descrição:</strong> ${roi.descricao ||'Não informada'}</p>

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

            geeDownloadStatusEl.innerHTML = `<div class="info">Iniciando processo para ${totalSelecionados} talhões...</div>`;
            btnProcessarLote.disabled = true;

            try {
                const idsParaProcessar = Array.from(talhoesSelecionados);
                const result = await startBatchDownloadForIds(idsParaProcessar, startDate, endDate, cloudPercentage);

                if (result && result.job_id) {
                    pollDownloadJobStatus(result.job_id, geeDownloadStatusEl);
                } else {
                    throw new Error("A resposta do servidor não incluiu um ID de tarefa válido.");
                }

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
            const propertyId = roi.roi_id; // Usa o ID da ROI atual
            const variety = document.getElementById('propertyVarietySelect').value;
            const startDate = document.getElementById('varietyStartDate').value;
            const endDate = document.getElementById('varietyEndDate').value;
            const cloud = document.getElementById('varietyCloudPercentage').value;

            if (!variety || !startDate || !endDate) {
                statusEl.innerHTML = '<div class="error">Por favor, preencha todos os campos.</div>';
                return;
            }
            statusEl.innerHTML = '<div class="info">Iniciando tarefa de download por variedade...</div>';

            try {
                const result = await startVarietyDownloadForProperty(propertyId, variety, startDate, endDate, cloud);
                if (result && result.job_id) {
                    pollDownloadJobStatus(result.job_id, statusEl);
                } else {
                    throw new Error("A resposta do servidor não incluiu um ID de tarefa válido.");
                }

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
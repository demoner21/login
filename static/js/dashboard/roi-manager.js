import {
    fetchUserROIs,
    fetchROIDetails,
    deleteUserROI,
    fetchAvailableVarieties,
    fetchAvailableProperties,
    requestROIDownload,
    requestVarietyDownload,
    startBatchDownloadForIds,
} from '../module/api.js';
import { initializeMapWithLayers } from '../module/map-utils.js';
import { fillEditModal } from '../module/ui-handlers.js';
import { normalizeName } from '../module/text-normalizer.js';

let roiMap;
let currentPage = 1;
const ROIS_PER_PAGE = 10;
let currentSearchTerm = '';
let currentPropertyFilter = '';

/**
 * Renderiza a lista de ROIs na tela de forma segura, criando elementos DOM.
 */
function displayROIList(rois) {
    const roiListElement = document.getElementById('roiList');
    roiListElement.innerHTML = '';

    if (rois.length === 0) {
        roiListElement.innerHTML = '<p>Nenhuma ROI encontrada com os filtros atuais.</p>';
        return;
    }

    const list = document.createElement('ul');
    rois.forEach(roi => {
        const displayName = (roi.nome_propriedade || roi.nome).replace(/_/g, ' ');
        const listItem = document.createElement('li');
        
        listItem.innerHTML = `
            <div>
                <strong>${displayName}</strong> - ${roi.descricao || 'Sem descrição'}
                <div class="small">Criado em: ${new Date(roi.data_criacao).toLocaleDateString('pt-BR')}</div>
            </div>
            <div>
                <button data-roi-id-view="${roi.roi_id}">Visualizar</button>
                <button data-roi-id-edit="${roi.roi_id}">Editar</button>
                <button data-roi-id-delete="${roi.roi_id}">Excluir</button>
            </div>
        `;
        list.appendChild(listItem);
    });

    roiListElement.appendChild(list);
}

/**
 * Popula o menu dropdown de Propriedades com os dados da API.
 */
async function populatePropertyDropdown() {
    const selectElement = document.getElementById('propertySelect');
    try {
        const propriedades = await fetchAvailableProperties();
        selectElement.options.length = 1;

        propriedades.forEach(prop => {
            if (prop) {
                const option = document.createElement('option');
                option.value = prop;
                option.textContent = prop;
                selectElement.appendChild(option);
            }
        });
    } catch (error) {
        console.error("Erro ao popular dropdown de propriedades:", error);
    }
}

/**
 * Popula o menu dropdown de Variedades com os dados da API.
 */
async function populateVarietyDropdown() {
    const selectElement = document.getElementById('varietySelect');
    try {
        const variedades = await fetchAvailableVarieties();
        selectElement.options.length = 1;

        variedades.forEach(variedade => {
            if (variedade) {
                const option = document.createElement('option');
                option.value = variedade;
                option.textContent = variedade;
                selectElement.appendChild(option);
            }
        });
    } catch (error) {
        console.error("Erro ao popular dropdown de variedades:", error);
    }
}

/**
 * Carrega as ROIs da API com base nos filtros e paginação atuais e atualiza a UI.
 */
export async function loadUserROIs() {
    const roiListElement = document.getElementById('roiList');
    const totalCountElement = document.getElementById('roiTotalCount');
    roiListElement.innerHTML = '<p>Carregando suas ROIs...</p>';
    
    try {
        const offset = (currentPage - 1) * ROIS_PER_PAGE;
        const responseData = await fetchUserROIs(ROIS_PER_PAGE, offset, currentSearchTerm, currentPropertyFilter);
        
        totalCountElement.textContent = responseData.total;
        displayROIList(responseData.rois);
        updatePaginationControls(responseData.total);
    } catch (error) {
        roiListElement.innerHTML = `<p class="error">${error.message}</p>`;
        totalCountElement.textContent = '0';
        
        const paginationControls = document.getElementById('paginationControls');
        if (paginationControls) {
            paginationControls.classList.add('hidden');
        }
    }
}

/**
 * Configura todos os eventos de interação da página de ROIs.
 */
export function setupROIEvents() {
    populatePropertyDropdown();
    populateVarietyDropdown();

    const varietySelect = document.getElementById('varietyDownloadSelect');
    const varietyDownloadForm = document.getElementById('varietyDownloadForm');
    const varietyStatusEl = document.getElementById('varietyDownloadStatus');

    fetchAvailableVarieties().then(variedades => {
        varietySelect.innerHTML = '<option value="">-- Selecione uma Variedade --</option>';
        variedades.forEach(v => {
            const option = document.createElement('option');
            option.value = v;
            option.textContent = v;
            varietySelect.appendChild(option);
        });
    });

    varietyDownloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const variety = varietySelect.value;
        const startDate = document.getElementById('varietyStartDate').value;
        const endDate = document.getElementById('varietyEndDate').value;

        if (!variety || !startDate || !endDate) {
            varietyStatusEl.innerHTML = '<div class="error">Por favor, preencha todos os campos.</div>';
            return;
        }

        varietyStatusEl.innerHTML = '<div class="info">Processando todos os talhões no GEE, isso pode levar um momento...</div>';

        try {
            const results = await requestVarietyDownload(variety, startDate, endDate);
            
            let resultHTML = '<h4>Resultados do Processamento:</h4><ul>';
            results.forEach(res => {
                if (res.status === 'success') {
                    resultHTML += `
                        <li>
                            <strong>Talhão:</strong> ${res.nome_talhao} (ID: ${res.roi_id}) - 
                            <a href="${res.download_url}" target="_blank" rel="noopener noreferrer">Baixar Imagem</a>
                        </li>`;
                } else {
                    resultHTML += `
                        <li style="color: red;">
                            <strong>Talhão:</strong> ${res.nome_talhao} (ID: ${res.roi_id}) - 
                            Falha no processamento: ${res.error_message}
                        </li>`;
                }
            });
            resultHTML += '</ul>';

            varietyStatusEl.innerHTML = `<div class="success">${resultHTML}</div>`;

        } catch (error) {
            varietyStatusEl.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
        }
    });

    document.getElementById('roiList').addEventListener('click', (e) => {
        const target = e.target;
        if (target.matches('[data-roi-id-view]')) {
            viewROIDetails(target.dataset.roiIdView);
        } else if (target.matches('[data-roi-id-edit]')) {
            openEditModal(target.dataset.roiIdEdit);
        } else if (target.matches('[data-roi-id-delete]')) {
            deleteROI(target.dataset.roiIdDelete);
        }
    });

    document.getElementById('propertySelect').addEventListener('change', (e) => {
        currentPropertyFilter = e.target.value;
        currentPage = 1;
        loadUserROIs();
    });

    document.getElementById('varietySelect').addEventListener('change', (e) => {
        currentSearchTerm = e.target.value;
        currentPage = 1;
        loadUserROIs();
    });

    document.getElementById('nextPageBtn').addEventListener('click', () => {
        currentPage++;
        loadUserROIs();
    });

    document.getElementById('prevPageBtn').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadUserROIs();
        }
    });

    document.getElementById('backToList').addEventListener('click', () => {
        const filtersContainer = document.getElementById('roiFilters');
        if (filtersContainer) {
            filtersContainer.classList.remove('hidden');
        }

        document.getElementById('roiList').classList.remove('hidden');
        document.getElementById('roiDetails').classList.add('hidden');
        document.getElementById('propertySelect').disabled = false;
        document.getElementById('varietySelect').disabled = false;
        updatePaginationControls(parseInt(document.getElementById('roiTotalCount').textContent, 10));

        if (roiMap) {
            roiMap.remove();
            roiMap = null;
        }
    });
}

/**
 * Abre o modal de edição com os dados da ROI especificada.
 */
async function openEditModal(roiId) {
    try {
        const statusElement = document.getElementById('editRoiStatus');
        if (statusElement) statusElement.innerHTML = '';

        const roi = await fetchROIDetails(roiId);
        fillEditModal(roi);
    } catch (error) {
        alert(`Erro: ${error.message}`);
    }
}

/**
 * Deleta uma ROI após confirmação do usuário.
 */
async function deleteROI(roiId) {
    if (!confirm('Tem certeza que deseja excluir esta ROI?')) return;

    try {
        await deleteUserROI(roiId);
        alert('ROI excluída com sucesso!');
        loadUserROIs();
    } catch (error) {
        alert(error.message);
    }
}

/**
 * Atualiza a visibilidade e o estado dos controles de paginação.
 */
function updatePaginationControls(totalRois) {
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const currentPageSpan = document.getElementById('currentPageSpan');
    const paginationControls = document.getElementById('paginationControls');
    const totalPages = Math.ceil(totalRois / ROIS_PER_PAGE);

    if (paginationControls) {
        if (totalPages > 1) {
            paginationControls.classList.remove('hidden');
            currentPageSpan.textContent = currentPage;
            prevPageBtn.disabled = currentPage === 1;
            nextPageBtn.disabled = currentPage >= totalPages;
        } else {
            paginationControls.classList.add('hidden');
        }
    }
}

/**
 * Busca os detalhes de uma ROI e chama a função para exibi-los.
 */
async function viewROIDetails(roiId) {
    try {
        const roi = await fetchROIDetails(roiId);
        displayROIDetails(roi);
    } catch (error) {
        alert(error.message);
    }
}

/**
 * Exibe a tela de detalhes para uma ROI específica.
*/
function displayROIDetails(roi) {
    const filtersContainer = document.getElementById('roiFilters');
    if (filtersContainer) {
        filtersContainer.classList.add('hidden');
    }

    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('paginationControls').classList.add('hidden');
    document.getElementById('roiDetails').classList.remove('hidden');
    document.getElementById('propertySelect').disabled = true;
    document.getElementById('varietySelect').disabled = true;
    
    document.getElementById('roiInfo').innerHTML = `
        <p><strong>Propriedade:</strong> ${roi.nome_propriedade || roi.nome}</p>
        <p><strong>Descrição:</strong> ${roi.descricao || 'Não informada'}</p>
        <div id="lote-actions" style="margin-top: 15px; display: none;">
            <button id="processarLoteBtn" class="btn-process">
                Processar Selecionados (<span id="contadorLote">0</span>)
            </button>
        </div>
        <div class="gee-download-form" style="margin-top: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
            <h4>Download de Imagem (GEE)</h4>
            <form id="geeDownloadForm">
                <input type="hidden" id="geeRoiId" value="${roi.roi_id}">
                <div>
                    <label for="geeStartDate">Data Início:</label>
                    <input type="date" id="geeStartDate" required>
                </div>
                <div>
                    <label for="geeEndDate">Data Fim:</label>
                    <input type="date" id="geeEndDate" required>
                </div>
                <button type="submit">Gerar Link de Download</button>
            </form>
            <div id="geeDownloadStatus" style="margin-top: 10px;"></div>
        </div>
    `;

    document.getElementById('geeDownloadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const roiId = document.getElementById('geeRoiId').value;
        const startDate = document.getElementById('geeStartDate').value;
        const endDate = document.getElementById('geeEndDate').value;
        const statusEl = document.getElementById('geeDownloadStatus');

        if (!startDate || !endDate) {
            statusEl.innerHTML = '<div class="error">Por favor, selecione as datas de início e fim.</div>';
            return;
        }

        statusEl.innerHTML = '<div class="info">Processando no GEE, por favor aguarde...</div>';

        try {
            const result = await requestROIDownload(roiId, startDate, endDate);
            statusEl.innerHTML = `
                <div class="success">
                    Link gerado! <a href="${result.download_url}" target="_blank" rel="noopener noreferrer">Clique aqui para baixar a imagem</a>.
                </div>
            `;
        } catch (error) {
            statusEl.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
        }
    });


    const talhoesSelecionados = new Set();
    const btnProcessarLote = document.getElementById('processarLoteBtn');
    const contadorLote = document.getElementById('contadorLote');
    const geeDownloadStatusEl = document.getElementById('geeDownloadStatus');
    
    let roiLayer = null; // Declaramos a variável da camada aqui para que ela seja acessível por toda a função

    const atualizarBotaoLote = () => {
        const totalSelecionados = talhoesSelecionados.size;
        contadorLote.textContent = totalSelecionados;
        const containerAcoes = document.getElementById('lote-actions');
        containerAcoes.style.display = totalSelecionados > 0 ? 'block' : 'none';
    };

    btnProcessarLote.onclick = async () => {
        const totalSelecionados = talhoesSelecionados.size;
        if (totalSelecionados === 0) {
            geeDownloadStatusEl.innerHTML = '<div class="warning">Nenhum talhão selecionado.</div>';
            return;
        }
        const startDate = document.getElementById('geeStartDate').value;
        const endDate = document.getElementById('geeEndDate').value;
        if (!startDate || !endDate) {
            geeDownloadStatusEl.innerHTML = '<div class="error">Por favor, selecione as datas de início e fim.</div>';
            return;
        }
        const idsParaProcessar = Array.from(talhoesSelecionados);
        geeDownloadStatusEl.innerHTML = `<div class="info">Iniciando processo para ${totalSelecionados} talhões...</div>`;
        btnProcessarLote.disabled = true;
        try {
            const result = await startBatchDownloadForIds(idsParaProcessar, startDate, endDate);
            const downloadUrl = result.task_details.download_link;
            geeDownloadStatusEl.innerHTML = `
                <div class="success">
                    ${result.message}<br>
                    <strong><a href="${downloadUrl}" target="_blank" rel="noopener noreferrer">Clique aqui para baixar o arquivo ZIP</a>.</strong>
                    <br><small>(Aguarde alguns instantes para o processamento ser concluído).</small>
                </div>
            `;
            talhoesSelecionados.clear();
            atualizarBotaoLote();
            
            // Chama o resetStyle na variável roiLayer, que é a camada GeoJSON correta
            if (roiLayer) {
                roiLayer.resetStyle();
            }

        } catch (error) {
            geeDownloadStatusEl.innerHTML = `<div class="error">Erro ao iniciar tarefa: ${error.message}</div>`;
        } finally {
            btnProcessarLote.disabled = false;
        }
    };

    if (window.roiMap) {
        window.roiMap.remove();
        window.roiMap = null;
    }

    window.roiMap = initializeMapWithLayers('map');

    if (roi.geometria && roi.geometria.type === 'FeatureCollection') {
        const estiloPadrao = { color: '#FF8C00', weight: 2, opacity: 0.9, fillColor: '#FFA500', fillOpacity: 0.2 };
        const estiloHover = { weight: 4, fillOpacity: 0.5 };
        const estiloSelecionado = { fillColor: '#3388ff', color: '#005eff', weight: 3, fillOpacity: 0.6 };

        // Atribui o resultado de L.geoJSON à variável roiLayer
        roiLayer = L.geoJSON(roi.geometria, {
            style: estiloPadrao,
            onEachFeature: function(feature, layer) {
                const props = feature.properties;
                const talhaoNumero = normalizeName(props.nome_talhao) || 'N/A';
                const variedade = props.variedade || 'N/A';
                const areaHa = props.area_ha ? `${props.area_ha.toFixed(2)} ha` : 'N/A';
                const talhaoId = props.roi_id;

                layer.bindTooltip(`<strong>Talhão:</strong> ${talhaoNumero}<br><strong>Variedade:</strong> ${variedade}<br><strong>Área:</strong> ${areaHa}`);

                layer.on('click', () => {
                    if (!talhaoId) return;
                    if (talhoesSelecionados.has(talhaoId)) {
                        talhoesSelecionados.delete(talhaoId);
                        layer.setStyle(estiloPadrao);
                    } else {
                        talhoesSelecionados.add(talhaoId);
                        layer.setStyle(estiloSelecionado);
                    }
                    atualizarBotaoLote();
                });

                layer.on({
                    mouseover: (e) => e.target.setStyle(estiloHover),
                    mouseout: (e) => {
                        if (!talhoesSelecionados.has(talhaoId)) {
                            // Aqui usamos a própria roiLayer para resetar o estilo da feature específica
                            roiLayer.resetStyle(e.target);
                        }
                    }
                });
            }
        }).addTo(window.roiMap);

        if (roiLayer.getBounds().isValid()) {
            window.roiMap.fitBounds(roiLayer.getBounds());
        }
    } else {
        console.warn("A geometria recebida não é uma FeatureCollection ou está vazia.", roi);
    }
}

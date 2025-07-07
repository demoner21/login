import { fetchUserROIs, fetchROIDetails, deleteUserROI, fetchAvailableVarieties, fetchAvailableProperties } from '../module/api.js';
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
    roiListElement.innerHTML = ''; // Limpa completamente o conteúdo anterior

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
        selectElement.options.length = 1; // Limpa opções antigas

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
        selectElement.options.length = 1; // Limpa opções antigas
        
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

    // Event listener para o filtro de Propriedade
    document.getElementById('propertySelect').addEventListener('change', (e) => {
        currentPropertyFilter = e.target.value;
        currentPage = 1;
        loadUserROIs();
    });

    // Event listener para o filtro de Variedade
    document.getElementById('varietySelect').addEventListener('change', (e) => {
        currentSearchTerm = e.target.value;
        currentPage = 1;
        loadUserROIs();
    });

    // Event listeners para os botões de paginação
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

    // Event listener para o botão "Voltar para lista" na tela de detalhes
    document.getElementById('backToList').addEventListener('click', () => {
        const filtersContainer = document.getElementById('roiFilters');
        if (filtersContainer) {
            filtersContainer.classList.remove('hidden');
        }
        
        document.getElementById('roiList').classList.remove('hidden');
        document.getElementById('roiDetails').classList.add('hidden');

        // Reabilita os filtros
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

    // Desabilita os filtros
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
    `;

    const talhoesSelecionados = new Set();
    const btnProcessarLote = document.getElementById('processarLoteBtn');
    const contadorLote = document.getElementById('contadorLote');
    
    const atualizarBotaoLote = () => {
        const totalSelecionados = talhoesSelecionados.size;
        contadorLote.textContent = totalSelecionados;
        const containerAcoes = document.getElementById('lote-actions');
        containerAcoes.style.display = totalSelecionados > 0 ? 'block' : 'none';
    };

    btnProcessarLote.onclick = () => {
        console.log("Processando talhões:", Array.from(talhoesSelecionados));
        // Aqui você chamaria a API para processar o lote
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

        const roiLayer = L.geoJSON(roi.geometria, {
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
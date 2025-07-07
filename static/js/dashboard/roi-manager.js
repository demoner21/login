// Importações no topo do arquivo
import { fetchUserROIs, fetchROIDetails, deleteUserROI, fetchAvailableVarieties } from '../module/api.js';
import { initializeMapWithLayers } from '../module/map-utils.js';
import { fillEditModal } from '../module/ui-handlers.js';
import { normalizeName } from '../module/text-normalizer.js';

// Variáveis de estado
let roiMap;
let currentPage = 1;
const ROIS_PER_PAGE = 10;
let currentSearchTerm = '';

/**
 * Renderiza a lista de ROIs na tela de forma segura, criando elementos DOM.
 * @param {Array} rois - A lista de objetos ROI.
 */
function displayROIList(rois) {
    const roiListElement = document.getElementById('roiList');
    // Limpa completamente o conteúdo anterior
    roiListElement.innerHTML = '';

    if (rois.length === 0) {
        roiListElement.innerHTML = '<p>Nenhuma ROI encontrada com os filtros atuais.</p>';
        return;
    }
    
    // Cria um elemento <ul> para a lista
    const list = document.createElement('ul');

    rois.forEach(roi => {
        const displayName = (roi.nome_propriedade || roi.nome).replace(/_/g, ' ');
        
        // Cria um elemento <li> para cada item
        const listItem = document.createElement('li');
        
        // Define o HTML interno do item da lista
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
        // Adiciona o item <li> à lista <ul>
        list.appendChild(listItem);
    });

    // Adiciona a lista completa <ul> ao container principal
    roiListElement.appendChild(list);
}

/**
 * Popula o menu dropdown com as variedades disponíveis.
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
 * Carrega as ROIs da API e comanda a atualização da UI.
 */
export async function loadUserROIs() {
    const roiListElement = document.getElementById('roiList');
    const totalCountElement = document.getElementById('roiTotalCount');
    roiListElement.innerHTML = '<p>Carregando suas ROIs...</p>';
    
    try {
        const offset = (currentPage - 1) * ROIS_PER_PAGE;
        const responseData = await fetchUserROIs(ROIS_PER_PAGE, offset, currentSearchTerm);
        
        totalCountElement.textContent = responseData.total;
        displayROIList(responseData.rois);
        updatePaginationControls(responseData.total);
    } catch (error) {
        roiListElement.innerHTML = `<p class="error">${error.message}</p>`;
        totalCountElement.textContent = '0';
        document.getElementById('paginationControls').style.display = 'none';
    }
}

/**
 * Configura todos os eventos de clique da página.
 */
export function setupROIEvents() {
    // Popula o dropdown assim que a UI é configurada
    populateVarietyDropdown();

    document.getElementById('roiList').addEventListener('click', (e) => {
        const target = e.target;
        if (target.matches('[data-roi-id-view]')) {
            viewROIDetails(target.dataset.roiIdView);
        }
        if (target.matches('[data-roi-id-edit]')) {
            openEditModal(target.dataset.roiIdEdit);
        }
        if (target.matches('[data-roi-id-delete]')) {
            deleteROI(target.dataset.roiIdDelete);
        }
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
        document.getElementById('roiList').classList.remove('hidden');
        updatePaginationControls(parseInt(document.getElementById('roiTotalCount').textContent, 10)); 
        document.getElementById('roiDetails').classList.add('hidden');
        if (roiMap) {
            roiMap.remove();
            roiMap = null;
        }
    });
}


// As funções abaixo (deleteROI, openEditModal, viewROIDetails, updatePaginationControls, etc.)
// devem ser mantidas como nas versões anteriores, pois sua lógica interna está correta.
// Apenas as colei aqui para garantir que você tenha o arquivo completo e correto.

async function openEditModal(roiId) {
    try {
        document.getElementById('editRoiStatus').innerHTML = '';
        const roi = await fetchROIDetails(roiId);
        fillEditModal(roi);
    } catch (error) {
        alert(`Erro: ${error.message}`);
    }
}

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

function updatePaginationControls(totalRois) {
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const currentPageSpan = document.getElementById('currentPageSpan');
    const paginationControls = document.getElementById('paginationControls');
    const totalPages = Math.ceil(totalRois / ROIS_PER_PAGE);

    if (totalPages > 0) {
        paginationControls.classList.remove('hidden');
        currentPageSpan.textContent = currentPage;
        prevPageBtn.disabled = currentPage === 1;
        nextPageBtn.disabled = currentPage >= totalPages;
    } else {
        paginationControls.classList.add('hidden');
    }
}

async function viewROIDetails(roiId) {
    try {
        const roi = await fetchROIDetails(roiId);
        displayROIDetails(roi);
    } catch (error) {
        alert(error.message);
    }
}

function displayROIDetails(roi) {
    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('paginationControls').classList.add('hidden');
    document.getElementById('roiDetails').classList.remove('hidden');
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
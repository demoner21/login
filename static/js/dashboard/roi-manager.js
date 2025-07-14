import {
    fetchUserROIs,
    fetchROIDetails,
    deleteUserROI,
    fetchAvailableVarieties,
    fetchAvailableProperties,
} from '../module/api.js';
import { fillEditModal } from '../module/ui-handlers.js';
import { displayROIDetails } from './roi-details-manager.js';

let currentPage = 1;
const ROIS_PER_PAGE = 10;
let currentSearchTerm = '';
let currentPropertyFilter = '';

/**
 * Renderiza a lista de ROIs na tela de forma segura.
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
 * Carrega as ROIs da API com base nos filtros e paginação atuais.
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
 * Busca os detalhes de uma ROI e chama a função para exibi-los.
 * @param {string} roiId O ID da ROI.
 */
async function viewROIDetails(roiId) {
    try {
        const roi = await fetchROIDetails(roiId);
        // Delega a exibição para o novo módulo
        displayROIDetails(roi);
    } catch (error) {
        alert(error.message);
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
        document.getElementById('roiFilters').classList.remove('hidden');
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
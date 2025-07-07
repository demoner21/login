import { fetchUserROIs, fetchROIDetails, deleteUserROI } from '../module/api.js';
import { initializeMapWithLayers } from '../module/map-utils.js';
import { fillEditModal } from '../module/ui-handlers.js';

let roiMap;

// --- INÍCIO DAS VARIÁVEIS DE ESTADO DA PAGINAÇÃO ---
let currentPage = 1;
const ROIS_PER_PAGE = 10; // Deve corresponder ao 'limit' padrão do backend
// --- FIM DAS VARIÁVEIS DE ESTADO DA PAGINAÇÃO ---

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
        loadUserROIs(); // Recarrega a página atual
    } catch (error) {
        alert(error.message);
    }
}

function displayROIList(rois) {
    const roiListElement = document.getElementById('roiList');
    if (rois.length === 0 && currentPage === 1) {
        roiListElement.innerHTML = '<p>Você ainda não tem ROIs cadastradas.</p>';
        document.getElementById('paginationControls').classList.add('hidden'); // Esconde controles se não houver ROIs
        return;
    }
    
    document.getElementById('paginationControls').classList.remove('hidden');
    
    let html = '<ul>';
    rois.forEach(roi => {
        html += `
            <li>
                <div>
                    <strong>${roi.nome}</strong> - ${roi.descricao || 'Sem descrição'}
                    <div class="small">Criado em: ${new Date(roi.data_criacao).toLocaleDateString()}</div>
                </div>
                <div>
                    <button data-roi-id-view="${roi.roi_id}">Visualizar</button>
                    <button data-roi-id-edit="${roi.roi_id}">Editar</button>
                    <button data-roi-id-delete="${roi.roi_id}">Excluir</button>
                </div>
            </li>
        `;
    });
    html += '</ul>';
    roiListElement.innerHTML = html;
}

async function viewROIDetails(roiId) {
    try {
        const roi = await fetchROIDetails(roiId);
        displayROIDetails(roi);
    } catch (error) {
        alert(error.message);
    }
}

// ... a função displayROIDetails continua a mesma ...
function displayROIDetails(roi) {
    // 1. Prepara a interface, escondendo a lista e mostrando a área de detalhes
    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('paginationControls').classList.add('hidden'); // Esconde paginação na tela de detalhes
    document.getElementById('roiDetails').classList.remove('hidden');

    // 2. Exibe as informações textuais da Propriedade principal
    document.getElementById('roiInfo').innerHTML = `
        <p><strong>Propriedade:</strong> ${roi.nome_propriedade || roi.nome}</p>
        <p><strong>Descrição:</strong> ${roi.descricao || 'Não informada'}</p>
        <div id="lote-actions" style="margin-top: 15px; display: none;">
            <button id="processarLoteBtn" class="btn-process">
                Processar Selecionados (<span id="contadorLote">0</span>)
            </button>
        </div>
    `;
    // ... (o resto da função não muda)
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
        downloadSentinelImagesForLote(Array.from(talhoesSelecionados));
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
                const talhaoNumero = props.nome_talhao || 'N/A';
                const variedade = props.variedade || 'N/A'; 
                const areaHa = props.area_ha ? `${props.area_ha.toFixed(2)} ha` : 'N/A';
                const talhaoId = props.roi_id;

                const tooltipContent = `
                    <strong>Talhão:</strong> ${talhaoNumero}<br>
                    <strong>Variedade:</strong> ${variedade}<br>
                    <strong>Área:</strong> ${areaHa}
                `;
                layer.bindTooltip(tooltipContent);

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


/**
 * Atualiza o estado dos botões de paginação (ativado/desativado).
 * @param {Array} rois A lista de ROIs retornada pela API.
 */
function updatePaginationControls(rois) {
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    
    // Desativa o botão "Anterior" se estivermos na primeira página
    prevPageBtn.disabled = currentPage === 1;

    // Desativa o botão "Próximo" se a API retornou menos itens que o limite
    // (indicando que esta é a última página)
    nextPageBtn.disabled = rois.length < ROIS_PER_PAGE;
    
    // Atualiza o número da página na UI
    document.getElementById('currentPageSpan').textContent = currentPage;
}

/**
 * Carrega a lista de ROIs para uma página específica.
 */
export async function loadUserROIs() {
    const roiListElement = document.getElementById('roiList');
    roiListElement.innerHTML = '<p>Carregando suas ROIs...</p>';
    
    try {
        const offset = (currentPage - 1) * ROIS_PER_PAGE;
        const rois = await fetchUserROIs(ROIS_PER_PAGE, offset);
        displayROIList(rois);
        updatePaginationControls(rois); // Atualiza os botões após carregar
    } catch (error) {
        roiListElement.innerHTML = `<p class="error">${error.message}</p>`;
    }
}

/**
 * Configura os eventos de clique para a lista de ROIs e os novos botões de paginação.
 */
export function setupROIEvents() {
    const roiListElement = document.getElementById('roiList');
    roiListElement.addEventListener('click', (e) => {
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

    document.getElementById('backToList').addEventListener('click', () => {
        document.getElementById('roiList').classList.remove('hidden');
        document.getElementById('paginationControls').classList.remove('hidden'); // Mostra paginação ao voltar
        document.getElementById('roiDetails').classList.add('hidden');
        if (roiMap) roiMap.remove();
    });
    
    // --- EVENTOS DOS BOTÕES DE PAGINAÇÃO ---
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
}
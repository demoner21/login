import { fetchUserROIs, fetchROIDetails, deleteUserROI } from '../module/api.js';
import { initializeMapWithLayers } from '../module/map-utils.js';
import { fillEditModal } from '../module/ui-handlers.js';

let roiMap;

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

function displayROIList(rois) {
    const roiListElement = document.getElementById('roiList');
    if (rois.length === 0) {
        roiListElement.innerHTML = '<p>Você ainda não tem ROIs cadastradas.</p>';
        return;
    }
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

function displayROIDetails(roi) {
    // 1. Prepara a interface
    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('roiDetails').classList.remove('hidden');

    // 2. Exibe informações da propriedade e cria o container para ações de lote
    document.getElementById('roiInfo').innerHTML = `
        <p><strong>Propriedade:</strong> ${roi.nome_propriedade || roi.nome}</p>
        <p><strong>Descrição:</strong> ${roi.descricao || 'Não informada'}</p>
        <div id="lote-actions" style="margin-top: 15px; display: none;">
            <button id="processarLoteBtn">Processar Selecionados (<span id="contadorLote">0</span>)</button>
        </div>
    `;

    // 3. Gerencia o estado da seleção
    const talhoesSelecionados = new Set();
    const btnProcessarLote = document.getElementById('processarLoteBtn');
    const contadorLote = document.getElementById('contadorLote');

    const atualizarBotaoLote = () => {
        const total = talhoesSelecionados.size;
        contadorLote.textContent = total;
        document.getElementById('lote-actions').style.display = total > 0 ? 'block' : 'none';
    };

    btnProcessarLote.onclick = () => {
        downloadSentinelImagesForLote(Array.from(talhoesSelecionados));
    };

    // 4. Inicializa o mapa
    if (roiMap) roiMap.remove();
    roiMap = initializeMapWithLayers('map');

    // 5. Renderiza os talhões se a geometria for uma FeatureCollection
    if (roi.geometria && roi.geometria.type === 'FeatureCollection') {
        const estiloPadrao = { color: '#FF8C00', weight: 2, opacity: 0.9, fillColor: '#FFA500', fillOpacity: 0.2 };
        const estiloHover = { weight: 4, fillOpacity: 0.5 };
        const estiloSelecionado = { fillColor: '#3388ff', color: '#005eff', weight: 3, fillOpacity: 0.6 };

        const roiLayer = L.geoJSON(roi.geometria, {
            style: estiloPadrao,
            onEachFeature: function(feature, layer) {
                const props = feature.properties;
                const talhaoNumero = props.nome_talhao || 'N/A';
                // Acessando a variedade e a área dos metadados de cada talhão
                const variedade = props.Variedade || 'N/A';
                const areaHa = props.area_ha ? `${props.area_ha.toFixed(2)} ha` : 'N/A';
                const talhaoId = props.roi_id;

                // Tooltip de hover
                const tooltipContent = `
                    <strong>Talhão:</strong> ${talhaoNumero}<br>
                    <strong>Variedade:</strong> ${variedade}<br>
                    <strong>Área:</strong> ${areaHa}
                `;
                layer.bindTooltip(tooltipContent);

                // Evento de clique para seleção múltipla
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

                // Eventos de mouse para destaque visual
                layer.on({
                    mouseover: (e) => e.target.setStyle(estiloHover),
                    mouseout: (e) => {
                        if (!talhoesSelecionados.has(talhaoId)) {
                            roiLayer.resetStyle(e.target);
                        }
                    }
                });
            }
        }).addTo(roiMap);

        if (roiLayer.getBounds().isValid()) {
            roiMap.fitBounds(roiLayer.getBounds());
        }
        else {
        console.warn("A geometria recebida não é uma FeatureCollection ou está vazia.", roi);
    }
    }
}

export async function loadUserROIs() {
    const roiListElement = document.getElementById('roiList');
    try {
        const rois = await fetchUserROIs();
        displayROIList(rois);
    } catch (error) {
        roiListElement.innerHTML = `<p class="error">${error.message}</p>`;
    }
}

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
        document.getElementById('roiDetails').classList.add('hidden');
        if (roiMap) roiMap.remove();
    });
}
// =============================================================================
// GLOBAL VARIABLES
// =============================================================================
let map;
let roiMap;
let previewMap;
let currentShapefileLayer;
let currentShapefileData = null;
let isPreviewLoading = false;

// =============================================================================
// AUTHENTICATION FUNCTIONS
// =============================================================================
function logout() {
    // Remover o token do localStorage
    localStorage.removeItem('access_token');
    
    // Redirecionar para a página de login (ou página inicial)
    window.location.href = '/static/login.html';
}
// =============================================================================
// INITIALIZATION FUNCTIONS
// =============================================================================
document.addEventListener('DOMContentLoaded', function() {
    // Configurar logout
    document.querySelector('a[href="#logout"]').addEventListener('click', function(e) {
        e.preventDefault();
        logout();
    });

    // Verificar autenticação ao carregar
    if (!localStorage.getItem('access_token')) {
        logout();
        return;
    }

    // Inicializar componentes
    initPreviewMap();
    loadUserROIs();
    setupEventListeners();
});

function setupEventListeners() {
    // Configurar formulário de upload
    document.getElementById('shapefileForm').addEventListener('submit', handleShapefileUpload);
    
    // Configurar botão de voltar
    document.getElementById('backToList').addEventListener('click', function() {
        document.getElementById('roiList').classList.remove('hidden');
        document.getElementById('roiDetails').classList.add('hidden');
        if (roiMap) roiMap.remove();
    });
    
    // Configurar botões de preview
    document.getElementById('previewBtn').addEventListener('click', previewShapefile);
    document.getElementById('clearPreviewBtn').addEventListener('click', clearPreview);
    
    // Configurar eventos de mudança de arquivo
    ['shp', 'shx', 'dbf', 'prj', 'cpg'].forEach(id => {
        document.getElementById(id).addEventListener('change', (e) => {
            handleFileChange(e, id);
            checkPreviewAvailability();
        });
    });
}

function initializeMapWithLayers(mapId) {
    const streetMap = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: ''
    });

    const satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: ''
    });

    const baseLayers = {
        "Satélite": satelliteMap,
        "Ruas": streetMap,
    };

    const map = L.map(mapId, {
        layers: [satelliteMap], // Camada padrão
        attributionControl: false
    });

    L.control.layers(baseLayers).addTo(map);

    return map;
}

function initPreviewMap() {
    const previewMapElement = document.getElementById('previewMap');
    if (!previewMapElement) return;
    
    previewMap = initializeMapWithLayers('previewMap').setView([-15.788, -47.879], 4);
}

// Adicione estas novas funções ao seu arquivo dashboard.js

const editRoiModal = document.getElementById('editRoiModal');
const editRoiForm = document.getElementById('editRoiForm');
const editRoiStatus = document.getElementById('editRoiStatus');

/**
 * Abre o modal de edição e busca os dados da ROI para preencher o formulário.
 */
async function openEditModal(roiId) {
    editRoiStatus.innerHTML = '';
    try {
        const response = await fetch(`/api/v1/roi/${roiId}`, {
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            }
        });

        if (!response.ok) {
            throw new Error('Falha ao buscar dados da ROI.');
        }

        const roi = await response.json();

        // Preenche o formulário com os dados atuais
        document.getElementById('editRoiId').value = roi.roi_id;
        document.getElementById('editRoiName').value = roi.nome;
        document.getElementById('editRoiDescription').value = roi.descricao || '';

        editRoiModal.style.display = 'flex';

    } catch (error) {
        alert(`Erro: ${error.message}`);
    }
}

/**
 * Fecha o modal de edição.
 */
function closeEditModal() {
    editRoiModal.style.display = 'none';
    editRoiForm.reset();
}

/**
 * Lida com o envio do formulário de edição.
 */
editRoiForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const roiId = document.getElementById('editRoiId').value;
    const nome = document.getElementById('editRoiName').value;
    const descricao = document.getElementById('editRoiDescription').value;
    const submitBtn = this.querySelector('.btn-save');

    const updateData = { nome, descricao };

    editRoiStatus.innerHTML = '<div class="info">Salvando...</div>';
    submitBtn.disabled = true;

    try {
        const response = await fetch(`/api/v1/roi/${roiId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            },
            body: JSON.stringify(updateData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Falha ao atualizar a ROI.');
        }

        editRoiStatus.innerHTML = '<div class="success">ROI atualizada com sucesso!</div>';

        // Aguarda um instante e fecha o modal, depois recarrega a lista
        setTimeout(() => {
            closeEditModal();
            loadUserROIs(); // Recarrega a lista para mostrar as alterações
        }, 1500);

    } catch (error) {
        editRoiStatus.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
    } finally {
        submitBtn.disabled = false;
    }
});

// Fecha o modal se o usuário clicar fora dele
window.addEventListener('click', function(event) {
    if (event.target === editRoiModal) {
        closeEditModal();
    }
});

// =============================================================================
// FILE HANDLING FUNCTIONS
// =============================================================================
function handleFileChange(event, fileType) {
    const file = event.target.files[0];
    const infoElement = document.getElementById(`${fileType}-info`);
    
    if (file) {
        const size = (file.size / 1024).toFixed(1);
        const sizeUnit = size > 1024 ? `${(size / 1024).toFixed(1)} MB` : `${size} KB`;
        infoElement.textContent = `${file.name} (${sizeUnit})`;
        infoElement.style.color = '#28a745';
    } else {
        infoElement.textContent = '';
    }
    
    if (['shp', 'shx', 'dbf'].includes(fileType)) {
        clearPreview();
    }
}

function checkPreviewAvailability() {
    const shpFile = document.getElementById('shp').files[0];
    const shxFile = document.getElementById('shx').files[0];
    const dbfFile = document.getElementById('dbf').files[0];
    
    const previewBtn = document.getElementById('previewBtn');
    const hasRequiredFiles = shpFile && shxFile && dbfFile;
    
    if (hasRequiredFiles && !isPreviewLoading) {
        previewBtn.classList.remove('hidden');
        previewBtn.disabled = false;
    } else {
        previewBtn.classList.add('hidden');
        if (!hasRequiredFiles) {
            clearPreview();
        }
    }
}

// =============================================================================
// SHAPEFILE PREVIEW FUNCTIONS
// =============================================================================
function previewShapefile() {
    if (isPreviewLoading) return;
    
    const shpFile = document.getElementById('shp').files[0];
    const shxFile = document.getElementById('shx').files[0];
    const dbfFile = document.getElementById('dbf').files[0];
    const prjFile = document.getElementById('prj').files[0];
    
    const files = {
        shp: shpFile,
        shx: shxFile,
        dbf: dbfFile,
        prj: prjFile || null
    };
    
    processShapefilePreview(files);
}

function clearPreview() {
    // Limpar mapa
    if (currentShapefileLayer && previewMap) {
        previewMap.removeLayer(currentShapefileLayer);
        currentShapefileLayer = null;
    }
    
    // Esconder containers
    document.getElementById('previewContainer').classList.add('hidden');
    document.getElementById('shapefileInfo').classList.add('hidden');
    document.getElementById('clearPreviewBtn').classList.add('hidden');
    
    // Limpar dados
    currentShapefileData = null;
    
    // Limpar status se for de preview
    const statusElement = document.getElementById('uploadStatus');
    if (statusElement.textContent.includes('Shapefile carregado para visualização')) {
        statusElement.innerHTML = '';
    }
}

function processShapefilePreview(files) {
    isPreviewLoading = true;
    const statusElement = document.getElementById('uploadStatus');
    const previewBtn = document.getElementById('previewBtn');
    const spinner = document.getElementById('previewSpinner');
    
    // Mostrar loading
    statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Processando shapefile...</div>';
    previewBtn.disabled = true;
    spinner.classList.remove('hidden');
    
    try {
        // Criar URLs para os arquivos
        const shpUrl = URL.createObjectURL(files.shp);
        const shxUrl = URL.createObjectURL(files.shx);
        const dbfUrl = URL.createObjectURL(files.dbf);
        const prjUrl = files.prj ? URL.createObjectURL(files.prj) : null;
        
        // Usar shp.js para processar o shapefile
        const fileUrls = [shpUrl, shxUrl, dbfUrl];
        if (prjUrl) fileUrls.push(prjUrl);
        
        shp.combine(fileUrls).then(function(geojson) {
            try {
                // Processar dados
                currentShapefileData = geojson;
                
                // Mostrar container de preview
                document.getElementById('previewContainer').classList.remove('hidden');
                
                // Limpar camada anterior se existir
                if (currentShapefileLayer) {
                    previewMap.removeLayer(currentShapefileLayer);
                }
                
                // Adicionar o shapefile ao mapa
                currentShapefileLayer = L.geoJSON(geojson, {
                    style: function(feature) {
                        return {
                            color: '#3388ff',
                            weight: 2,
                            opacity: 0.8,
                            fillOpacity: 0.3,
                            fillColor: '#3388ff'
                        };
                    },
                    onEachFeature: function(feature, layer) {
                        // Adicionar popup com informações
                        let popupContent = '<div><strong>Feature</strong><br>';
                        if (feature.properties) {
                            Object.keys(feature.properties).forEach(key => {
                                if (feature.properties[key] !== null && feature.properties[key] !== '') {
                                    popupContent += `<strong>${key}:</strong> ${feature.properties[key]}<br>`;
                                }
                            });
                        }
                        popupContent += '</div>';
                        layer.bindPopup(popupContent);
                    }
                }).addTo(previewMap);
                
                // Ajustar a visualização para a extensão do shapefile
                previewMap.fitBounds(currentShapefileLayer.getBounds());
                
                // Mostrar informações do shapefile
                displayShapefileInfo(geojson);
                
                // Atualizar status
                statusElement.innerHTML = '<div class="success">Shapefile carregado para visualização com sucesso!</div>';
                
                // Mostrar botão de limpar
                document.getElementById('clearPreviewBtn').classList.remove('hidden');
                
            } catch (error) {
                console.error('Erro no processamento:', error);
                statusElement.innerHTML = `<div class="error">Erro ao processar shapefile: ${error.message}</div>`;
            }
        }).catch(function(error) {
            console.error('Erro no shp.js:', error);
            statusElement.innerHTML = `<div class="error">Erro ao processar shapefile: ${error.message}</div>`;
        }).finally(function() {
            // Limpar loading
            isPreviewLoading = false;
            previewBtn.disabled = false;
            spinner.classList.add('hidden');
            
            // Liberar objetos URL
            URL.revokeObjectURL(shpUrl);
            URL.revokeObjectURL(shxUrl);
            URL.revokeObjectURL(dbfUrl);
            if (prjUrl) URL.revokeObjectURL(prjUrl);
        });
        
    } catch (error) {
        console.error('Erro inicial:', error);
        statusElement.innerHTML = `<div class="error">Erro ao processar shapefile: ${error.message}</div>`;
        isPreviewLoading = false;
        previewBtn.disabled = false;
        spinner.classList.add('hidden');
    }
}

function displayShapefileInfo(geojson) {
    const shapefileInfo = document.getElementById('shapefileInfo');
    const shapefileDetails = document.getElementById('shapefileDetails');
    
    if (!geojson || !geojson.features) return;
    
    const features = geojson.features;
    const totalFeatures = features.length;
    
    // Analisar tipos de geometria
    const geometryTypes = [...new Set(features.map(f => f.geometry.type))];
    
    // Analisar propriedades
    const sampleProperties = features[0]?.properties || {};
    const propertyKeys = Object.keys(sampleProperties);
    
    // Calcular área aproximada (apenas para demonstração)
    let totalArea = 0;
    features.forEach(feature => {
        if (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon') {
            // Cálculo aproximado de área
            const layer = L.geoJSON(feature);
            const bounds = layer.getBounds();
            const area = bounds.getNorth() - bounds.getSouth() * bounds.getEast() - bounds.getWest();
            totalArea += Math.abs(area);
        }
    });
    
    let infoHTML = `
        <p><strong>Total de Features:</strong> ${totalFeatures}</p>
        <p><strong>Tipos de Geometria:</strong> ${geometryTypes.join(', ')}</p>
        <p><strong>Propriedades Encontradas:</strong> ${propertyKeys.length > 0 ? propertyKeys.join(', ') : 'Nenhuma'}</p>
    `;
    
    if (totalArea > 0) {
        infoHTML += `<p><strong>Área Total Aproximada:</strong> ${totalArea.toFixed(6)} graus²</p>`;
    }
    
    shapefileDetails.innerHTML = infoHTML;
    shapefileInfo.classList.remove('hidden');
}

// =============================================================================
// ROI MANAGEMENT FUNCTIONS
// =============================================================================
async function loadUserROIs() {
    try {
        const response = await fetch('/api/v1/roi/', {
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            }
        });
        
        if (!response.ok) throw new Error('Erro ao carregar ROIs');
        
        const rois = await response.json();
        displayROIList(rois);
    } catch (error) {
        document.getElementById('roiList').innerHTML = `<p class="error">${error.message}</p>`;
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
                    <button onclick="viewROIDetails(${roi.roi_id})">Visualizar</button>
                    <button onclick="openEditModal(${roi.roi_id})">Editar</button>
                    <button onclick="deleteROI(${roi.roi_id})">Excluir</button>
                </div>
            </li>
        `;
    });
    html += '</ul>';
    
    roiListElement.innerHTML = html;
}
async function viewROIDetails(roiId) {
    try {
        const response = await fetch(`/api/v1/roi/${roiId}`, {
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            }
        });
        
        if (!response.ok) throw new Error('Erro ao carregar ROI');
        
        const roi = await response.json();
        displayROIDetails(roi);
    } catch (error) {
        alert(error.message);
    }
}

function displayROIDetails(roi) {
    // Show details and hide list
    document.getElementById('roiList').classList.add('hidden');
    document.getElementById('roiDetails').classList.remove('hidden');

    // Add back button event listener
    const backButton = document.getElementById('backToList');
    // Remove existing event listeners to prevent duplicates
    const newBackButton = backButton.cloneNode(true);
    backButton.parentNode.replaceChild(newBackButton, backButton);
    newBackButton.addEventListener('click', function() {
        document.getElementById('roiList').classList.remove('hidden');
        document.getElementById('roiDetails').classList.add('hidden');
    });

    // Display basic information
    document.getElementById('roiInfo').innerHTML = `
        <p><strong>Nome:</strong> ${roi.nome}</p>
        <p><strong>Descrição:</strong> ${roi.descricao || 'Não informada'}</p>
        <p><strong>Tipo:</strong> ${roi.tipo_origem}</p>
        <p><strong>Status:</strong> ${roi.status}</p>
        <p><strong>Criada em:</strong> ${new Date(roi.data_criacao).toLocaleString()}</p>
        ${roi.metadata && roi.metadata.area_ha ? `<p><strong>Área:</strong> ${roi.metadata.area_ha.toFixed(2)} hectares</p>` : ''}
    `;

    // Properly cleanup and reinitialize map
    const mapElement = document.getElementById('map');

    // If map container exists, remove it and create a new one
    if (mapElement) {
        const newMapElement = document.createElement('div');
        newMapElement.id = 'map';
        newMapElement.style.height = '400px'; // Set appropriate height
        mapElement.parentNode.replaceChild(newMapElement, mapElement);
    }

    // If global roiMap exists, clean it up
    if (window.roiMap) {
        window.roiMap.remove();
        window.roiMap = null;
    }

    // Initialize new map
    window.roiMap = initializeMapWithLayers('map');

    // Add ROI geometry to map
    if (roi.geometria) {
        try {
            const geojson = typeof roi.geometria === 'string' ? JSON.parse(roi.geometria) : roi.geometria;
            const roiLayer = L.geoJSON(geojson, {
                style: {
                    color: '#ff7800',
                    weight: 3,
                    opacity: 0.8,
                    fillOpacity: 0.3,
                    fillColor: '#ff7800'
                }
            }).addTo(window.roiMap);

            // Adjust view to ROI bounds
            window.roiMap.fitBounds(roiLayer.getBounds());

            // Add popup with information
            roiLayer.bindPopup(`
                <b>${roi.nome}</b><br>
                ${roi.descricao || ''}<br>
                Área: ${roi.metadata?.area_ha ? roi.metadata.area_ha.toFixed(2) + ' ha' : 'não calculada'}
            `).openPopup();
        } catch (e) {
            console.error('Erro ao processar geometria:', e);
        }
    }
}

async function deleteROI(roiId) {
    if (!confirm('Tem certeza que deseja excluir esta ROI?')) return;
    
    try {
        const response = await fetch(`/api/v1/roi/${roiId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            }
        });
        
        if (!response.ok) throw new Error('Erro ao excluir ROI');
        
        alert('ROI excluída com sucesso!');
        loadUserROIs();
    } catch (error) {
        alert(error.message);
    }
}
// =============================================================================
// Função para lidar com o download
// =============================================================================
async function downloadSentinelImages(roiId) {
    try {
        // Solicitar datas e percentual de nuvens ao usuário
        const startDate = prompt("Digite a data de início (YYYY-MM-DD):");
        const endDate = prompt("Digite a data de término (YYYY-MM-DD):");
        const cloudPercentage = prompt("Digite o percentual máximo de nuvens (0-100):");

        // Validar entradas
        if (!startDate || !endDate || !cloudPercentage) {
            throw new Error("Todos os campos são obrigatórios");
        }

        if (isNaN(cloudPercentage) || cloudPercentage < 0 || cloudPercentage > 100) {
            throw new Error("Percentual de nuvens deve ser entre 0 e 100");
        }

        // Mostrar loading
        const statusElement = document.getElementById('uploadStatus');
        statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Preparando download das imagens Sentinel...</div>';

        // Construir URL com parâmetros
        const url = new URL(`/sentinel/${roiId}/download-sentinel`, window.location.origin);
        url.searchParams.append('start_date', startDate);
        url.searchParams.append('end_date', endDate);
        url.searchParams.append('cloud_pixel_percentage', cloudPercentage);

        // Fazer a requisição
        const response = await fetch(url, {
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao baixar imagens');
        }

        // Criar blob a partir da resposta
        const blob = await response.blob();
        
        // Criar link de download
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `sentinel_roi_${roiId}.zip`;
        document.body.appendChild(a);
        a.click();
        
        // Limpar
        window.URL.revokeObjectURL(downloadUrl);
        a.remove();
        
        statusElement.innerHTML = '<div class="success">Download iniciado com sucesso!</div>';
        
    } catch (error) {
        document.getElementById('uploadStatus').innerHTML = `<div class="error">Erro: ${error.message}</div>`;
    }

    
}
// =============================================================================
// UPLOAD FUNCTIONS
// =============================================================================
async function handleShapefileUpload(e) {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);
    const statusElement = document.getElementById('uploadStatus');
    const submitBtn = document.getElementById('submitBtn');

    try {
        // A lógica de loading permanece a mesma
        statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Enviando e processando o shapefile...</div>';
        submitBtn.disabled = true;
        submitBtn.textContent = 'Enviando...';

        const response = await fetch('/api/v1/roi/upload-shapefile-splitter', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro no upload do shapefile');
        }

        const result = await response.json();

        // MODIFICADO: A lógica de sucesso agora lida com a nova resposta,
        // que contém uma lista de ROIs em 'rois_criadas'.
        let successMessage = `
            <div class="success">
                <h4>${result.mensagem}</h4>
                <p><strong>Total de ROIs criadas:</strong> ${result.total_rois}</p>
                <p><strong>ROIs Geradas:</strong></p>
                <ul>
        `;

        result.rois_criadas.forEach(roi => {
            successMessage += `<li>${roi.nome} (ID: ${roi.roi_id})</li>`;
        });

        successMessage += '</ul></div>';
        statusElement.innerHTML = successMessage;

        await loadUserROIs();
        form.reset();
        ['shp', 'shx', 'dbf', 'prj', 'cpg'].forEach(type => {
            const infoElement = document.getElementById(`${type}-info`);
            if (infoElement) {
                infoElement.textContent = '';
            }
        });
        clearPreview();
        checkPreviewAvailability();

    } catch (error) {
        statusElement.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Shapefile';
    }
}
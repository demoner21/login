import { initializeMapWithLayers } from '../module/map-utils.js';

let previewMap;
let currentShapefileLayer;
let currentShapefileData = null;
let isPreviewLoading = false;

export function initPreviewMap() {
    if (document.getElementById('previewMap')) {
        previewMap = initializeMapWithLayers('previewMap').setView([-15.788, -47.879], 4);
    }
}

export function clearPreview() {
    if (currentShapefileLayer && previewMap) {
        previewMap.removeLayer(currentShapefileLayer);
        currentShapefileLayer = null;
    }
    document.getElementById('previewContainer').classList.add('hidden');
    document.getElementById('shapefileInfo').classList.add('hidden');
    document.getElementById('clearPreviewBtn').classList.add('hidden');
    currentShapefileData = null;
    const statusElement = document.getElementById('uploadStatus');
    if (statusElement.textContent.includes('Shapefile carregado para visualização')) {
        statusElement.innerHTML = '';
    }
}

function displayShapefileInfo(geojson) {
    const shapefileInfo = document.getElementById('shapefileInfo');
    const shapefileDetails = document.getElementById('shapefileDetails');
    const features = geojson.features;
    const totalFeatures = features.length;
    const geometryTypes = [...new Set(features.map(f => f.geometry.type))];
    const propertyKeys = Object.keys(features[0]?.properties || {});

    let infoHTML = `
        <p><strong>Total de Features:</strong> ${totalFeatures}</p>
        <p><strong>Tipos de Geometria:</strong> ${geometryTypes.join(', ')}</p>
        <p><strong>Propriedades Encontradas:</strong> ${propertyKeys.length > 0 ? propertyKeys.join(', ') : 'Nenhuma'}</p>
    `;
    shapefileDetails.innerHTML = infoHTML;
    shapefileInfo.classList.remove('hidden');
}

export function processShapefilePreview(files) { 
    if (isPreviewLoading || !files || files.length === 0) return;
    isPreviewLoading = true;
    
    const statusElement = document.getElementById('uploadStatus');
    const previewBtn = document.getElementById('previewBtn');
    const spinner = document.getElementById('previewSpinner');
    
    statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Processando shapefile...</div>';
    previewBtn.disabled = true;
    spinner.classList.remove('hidden');

    const fileUrls = Array.from(files).map(file => URL.createObjectURL(file));

    shp.combine(fileUrls).then(geojson => {
        currentShapefileData = geojson;
        document.getElementById('previewContainer').classList.remove('hidden');
        if (currentShapefileLayer) {
            previewMap.removeLayer(currentShapefileLayer);
        }
        currentShapefileLayer = L.geoJSON(geojson, {
            style: {
                color: '#3388ff',
                weight: 2,
                opacity: 0.8,
                fillOpacity: 0.3,
                fillColor: '#3388ff'
            },
            onEachFeature: (feature, layer) => {
                let popupContent = '<div><strong>Feature</strong><br>';
                if (feature.properties) {
                    for (const key in feature.properties) {
                        popupContent += `<strong>${key}:</strong> ${feature.properties[key]}<br>`;
                    }
                }
                popupContent += '</div>';
                layer.bindPopup(popupContent);
            }
        }).addTo(previewMap);
        previewMap.fitBounds(currentShapefileLayer.getBounds());
        displayShapefileInfo(geojson);
        statusElement.innerHTML = '<div class="success">Shapefile carregado para visualização com sucesso!</div>';
        document.getElementById('clearPreviewBtn').classList.remove('hidden');
    }).catch(error => {
        statusElement.innerHTML = `<div class="error">Erro ao processar shapefile: ${error.message}</div>`;
    }).finally(() => {
        isPreviewLoading = false;
        previewBtn.disabled = false;
        spinner.classList.add('hidden');
        fileUrls.forEach(url => URL.revokeObjectURL(url));
    });
}
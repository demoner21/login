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

export function processShapefilePreview() {
    if (isPreviewLoading) return;
    isPreviewLoading = true;
    
    const statusElement = document.getElementById('uploadStatus');
    const previewBtn = document.getElementById('previewBtn');
    const spinner = document.getElementById('previewSpinner');
    
    statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Processando shapefile...</div>';
    previewBtn.disabled = true;
    spinner.classList.remove('hidden');

    const files = {
        shp: document.getElementById('shp').files[0],
        shx: document.getElementById('shx').files[0],
        dbf: document.getElementById('dbf').files[0],
        prj: document.getElementById('prj').files[0]
    };

    const shpUrl = URL.createObjectURL(files.shp);
    const shxUrl = URL.createObjectURL(files.shx);
    const dbfUrl = URL.createObjectURL(files.dbf);
    const prjUrl = files.prj ? URL.createObjectURL(files.prj) : null;
    const fileUrls = [shpUrl, shxUrl, dbfUrl];
    if (prjUrl) fileUrls.push(prjUrl);

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
        URL.revokeObjectURL(shpUrl);
        URL.revokeObjectURL(shxUrl);
        URL.revokeObjectURL(dbfUrl);
        if (prjUrl) URL.revokeObjectURL(prjUrl);
    });
}
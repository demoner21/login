export function initializeMapWithLayers(mapId) {
    const satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: ''
    });

    const streetMap = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: ''
    });

    const baseLayers = {
        "Satélite": satelliteMap,
        "Ruas": streetMap,
    };

    const map = L.map(mapId, {
        layers: [satelliteMap],
        attributionControl: false
    });

    L.control.layers(baseLayers).addTo(map);
    return map;
}
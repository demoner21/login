import { checkAuth, logout } from '../module/auth-session.js';
import { uploadShapefile } from '../module/api.js';
import { initializeUI } from '../module/ui-handlers.js';
import { loadUserROIs, setupROIEvents } from './roi-manager.js';
import { initPreviewMap, clearPreview, processShapefilePreview } from './shapefile-preview.js';

let map;

document.addEventListener('DOMContentLoaded', function() {
    if (!checkAuth()) return;

    document.querySelector('a[href="#logout"]').addEventListener('click', (e) => {
        e.preventDefault();
        logout();
    });

    initPreviewMap();
    loadUserROIs();
    initializeUI();
    setupEventListeners();
    setupROIEvents();
});

function setupEventListeners() {
    document.getElementById('shapefileForm').addEventListener('submit', handleShapefileUpload);
    document.getElementById('previewBtn').addEventListener('click', processShapefilePreview);
    document.getElementById('clearPreviewBtn').addEventListener('click', clearPreview);

    ['shp', 'shx', 'dbf', 'prj', 'cpg'].forEach(id => {
        document.getElementById(id).addEventListener('change', (e) => handleFileChange(e, id));
    });
}

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
    checkPreviewAvailability();
}

function checkPreviewAvailability() {
    const shpFile = document.getElementById('shp').files[0];
    const shxFile = document.getElementById('shx').files[0];
    const dbfFile = document.getElementById('dbf').files[0];
    const previewBtn = document.getElementById('previewBtn');
    
    if (shpFile && shxFile && dbfFile) {
        previewBtn.classList.remove('hidden');
        previewBtn.disabled = false;
    } else {
        previewBtn.classList.add('hidden');
        clearPreview();
    }
}

async function handleShapefileUpload(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const statusElement = document.getElementById('uploadStatus');
    const submitBtn = document.getElementById('submitBtn');

    statusElement.innerHTML = '<div class="info"><span class="loading-spinner"></span>Enviando...</div>';
    submitBtn.disabled = true;

    try {
        const result = await uploadShapefile(formData);
        let successMessage = `
            <div class="success">
                <h4>${result.mensagem}</h4>
                <p><strong>Propriedades Criadas:</strong> ${result.propriedades_criadas}</p>
                <p><strong>Talhões Criados:</strong> ${result.talhoes_criados}</p>
            </div>
        `;
        statusElement.innerHTML = successMessage;
        await loadUserROIs();
        form.reset();
        ['shp', 'shx', 'dbf', 'prj', 'cpg'].forEach(type => {
            document.getElementById(`${type}-info`).textContent = '';
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

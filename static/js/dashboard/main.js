import { checkAuth, logout } from '../module/auth-session.js';
import { uploadShapefile } from '../module/api.js';
import { initializeUI } from '../module/ui-handlers.js';
import { loadUserROIs, setupROIEvents } from './roi-manager.js';


document.addEventListener('DOMContentLoaded', function() {
    if (!checkAuth()) return;

    
    loadUserROIs();
    initializeUI();
    setupEventListeners();
    setupROIEvents();
});
function setupEventListeners() {
    document.getElementById('shapefileForm').addEventListener('submit', handleShapefileUpload);
    
    document.getElementById('shapefileUpload').addEventListener('change', handleFileSelection);

    const logoutButton = document.getElementById('logoutBtn');
if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault(); // Impede o comportamento padrão do link
            logout(); // Chama a função de logout importada
        });
}

    
}

function handleFileSelection(event) {
    const files = event.target.files;
    const fileListElement = document.getElementById('fileList');
    fileListElement.innerHTML = '';
if (files.length > 0) {
        const list = document.createElement('ul');
const baseName = files[0].name.split('.').slice(0, -1).join('.');
        let allNamesMatch = true;

        for (const file of files) {
            const currentBaseName = file.name.split('.').slice(0, -1).join('.');
if (currentBaseName !== baseName) {
                allNamesMatch = false;
}
            const listItem = document.createElement('li');
            listItem.textContent = file.name;
            list.appendChild(listItem);
}
        fileListElement.appendChild(list);

        if (!allNamesMatch) {
            fileListElement.innerHTML += '<p class="error">Erro: Todos os arquivos selecionados devem ter o mesmo nome base (ex: Fazenda.shp, Fazenda.shx).</p>';
document.getElementById('submitBtn').disabled = true;
            return;
        }
    }
    document.getElementById('submitBtn').disabled = false;
    
}



async function handleShapefileUpload(e) {
    e.preventDefault();
const form = e.target;
    const statusElement = document.getElementById('uploadStatus');
    const submitBtn = document.getElementById('submitBtn');
    const files = document.getElementById('shapefileUpload').files;
const formData = new FormData();
    formData.append('propriedade_col', form.elements.propriedade_col.value);
    formData.append('talhao_col', form.elements.talhao_col.value);

    const extensionToFieldMap = {
        'shp': 'shp',
        'shx': 'shx',
        'dbf': 'dbf',
        'prj': 'prj',
        'cpg': 'cpg'
    };
for (const file of files) {
        const extension = file.name.split('.').pop().toLowerCase();
const fieldName = extensionToFieldMap[extension];
        if (fieldName) {
            formData.append(fieldName, file);
}
    }

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
        form.reset();
        document.getElementById('fileList').innerHTML = '';
        
        
    } catch (error) {
        statusElement.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
} finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Shapefile';
}
}
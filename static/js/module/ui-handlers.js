import { updateUserROI } from './api.js';
import { loadUserROIs } from '../dashboard/roi-manager.js';

const editRoiModal = document.getElementById('editRoiModal');
const editRoiForm = document.getElementById('editRoiForm');
const editRoiStatus = document.getElementById('editRoiStatus');

export function fillEditModal(roi) {
    document.getElementById('editRoiId').value = roi.roi_id;
    document.getElementById('editRoiName').value = roi.nome;
    document.getElementById('editRoiDescription').value = roi.descricao || '';
    editRoiModal.style.display = 'flex';
}

export function closeEditModal() {
    if (editRoiModal) {
        editRoiModal.style.display = 'none';
        editRoiForm.reset();
    }
}

function setupModalEventListeners() {
    editRoiForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const roiId = document.getElementById('editRoiId').value;
        const nome = document.getElementById('editRoiName').value;
        const descricao = document.getElementById('editRoiDescription').value;
        const submitBtn = this.querySelector('.btn-save');

        editRoiStatus.innerHTML = '<div class="info">Salvando...</div>';
        submitBtn.disabled = true;

        try {
            await updateUserROI(roiId, { nome, descricao });
            editRoiStatus.innerHTML = '<div class="success">ROI atualizada com sucesso!</div>';
            setTimeout(() => {
                closeEditModal();
                loadUserROIs();
            }, 1500);
        } catch (error) {
            editRoiStatus.innerHTML = `<div class="error">Erro: ${error.message}</div>`;
        } finally {
            submitBtn.disabled = false;
        }
    });

    window.addEventListener('click', (event) => {
        if (event.target === editRoiModal) {
            closeEditModal();
        }
    });

    document.querySelector('.close-modal').addEventListener('click', closeEditModal);
    document.querySelector('.btn-cancel').addEventListener('click', closeEditModal);
}

export function initializeUI() {
    setupModalEventListeners();
}

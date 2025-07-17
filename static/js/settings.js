import { checkAuth, logout } from './module/auth-session.js';
import { getUserData, updateUserData, updateUserPassword } from './module/api.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!await checkAuth()) return;

    setupEventListeners();
    loadUserData();
});

function setupEventListeners() {
    document.getElementById('logoutBtn').addEventListener('click', (e) => {
        e.preventDefault();
        logout();
    });

    document.getElementById('userDataForm').addEventListener('submit', handleUpdateUserData);
    document.getElementById('passwordUpdateForm').addEventListener('submit', handleUpdatePassword);
}

// Carrega os dados do usuário e preenche o formulário
async function loadUserData() {
    try {
        const user = await getUserData();
        document.getElementById('userName').value = user.nome;
        document.getElementById('userEmail').value = user.email;
    } catch (error) {
        showStatusMessage('userDataStatus', `Erro ao carregar dados: ${error.message}`, 'error');
    }
}

// Lida com a atualização dos dados (nome/email)
async function handleUpdateUserData(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector('button');
    const originalButtonText = button.textContent;
    const data = {
        nome: form.elements.nome.value,
        email: form.elements.email.value
    };

    setButtonLoading(button, true, 'Salvando...');
    try {
        await updateUserData(data);
        showStatusMessage('userDataStatus', 'Dados atualizados com sucesso!', 'success');
        
        // Se o email foi alterado, a API já desloga o usuário (limpando o cookie).
        // A próxima requisição autenticada falhará, forçando o logout pelo checkAuth.
        // Podemos forçar um reload para garantir a re-autenticação.
        setTimeout(() => {
             // Verificamos se a sessão ainda é válida. Se o email mudou, não será.
            checkAuth();
        }, 2000);

    } catch (error) {
        showStatusMessage('userDataStatus', error.message, 'error');
    } finally {
        setButtonLoading(button, false, originalButtonText);
    }
}

// Lida com a atualização da senha
async function handleUpdatePassword(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector('button');
    const originalButtonText = button.textContent;
    const novaSenha = form.elements.nova_senha.value;
    const confirmarSenha = form.elements.confirmNewPassword.value;

    if (novaSenha !== confirmarSenha) {
        showStatusMessage('passwordUpdateStatus', 'As novas senhas não coincidem.', 'error');
        return;
    }

    const data = {
        senha_atual: form.elements.senha_atual.value,
        nova_senha: novaSenha
    };

    setButtonLoading(button, true, 'Alterando...');
    try {
        await updateUserPassword(data);
        showStatusMessage('passwordUpdateStatus', 'Senha alterada com sucesso!', 'success');
        form.reset();
    } catch (error) {
        showStatusMessage('passwordUpdateStatus', error.message, 'error');
    } finally {
        setButtonLoading(button, false, originalButtonText);
    }
}

// Funções auxiliares de UI
function showStatusMessage(elementId, message, type = 'info') {
    const el = document.getElementById(elementId);
    el.className = `status-message ${type}`;
    el.textContent = message;
    el.style.display = 'block';

    setTimeout(() => {
        el.style.display = 'none';
    }, 5000);
}

function setButtonLoading(button, isLoading, loadingText) {
    button.disabled = isLoading;
    if (isLoading) {
        button.textContent = loadingText;
    } else {
        button.textContent = button.dataset.originalText || button.textContent;
    }
}

// Guarda o texto original do botão
document.querySelectorAll('button[type="submit"]').forEach(button => {
    button.dataset.originalText = button.textContent;
});
import { fetchApi } from './api.js';

export function logout() {
    console.log("Sessão inválida ou expirada. Realizando logout...");
    window.location.href = '/static/login.html';
}


export async function checkAuth() {
    try {
        await fetchApi('/auth/me'); 
        return true;
    } catch (error) {
        logout();
        return false;
    }
}
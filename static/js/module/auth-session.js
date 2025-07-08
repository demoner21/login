import { fetchApi } from './api.js';

export function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/static/login.html';
}


export async function checkAuth() {
    try {
        await fetchApi('/auth/me'); 
        return true;
    } catch (error) {
        return false;
    }
}
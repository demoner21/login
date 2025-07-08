import { logout } from './auth-session.js';

const BASE_URL = '/api/v1';

async function refreshToken() {
    try {
        await fetch(`${BASE_URL}/auth/refresh`, {
            method: 'POST',
            credentials: 'include'
        });
        return true
    } catch (error) {
        console.error('Falha ao renovar o token:', error);
        return false;
    }
}

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

export async function fetchApi(url, options = {}) {
    try {
        const config = { 
            ...options, 
            headers: { ...options.headers },
            credentials: 'include' 
        };
        let response = await fetch(`${BASE_URL}${url}`, config);

        if (response.status === 401) {
            if (isRefreshing) {
                // Se já há uma requisição de refresh em andamento, enfileira a nova
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then(() => {
                    // Tenta novamente a requisição original
                    return fetch(`${BASE_URL}${url}`, config);
                });
            }

            isRefreshing = true;
            
            const refreshed = await refreshToken();
            
            if (refreshed) {
                processQueue(null);
                // Tenta novamente a requisição original após o refresh
                response = await fetch(`${BASE_URL}${url}`, config);
            } else {
                processQueue(new Error('Sessão expirada.'));
                logout(); // Se o refresh falhar, desloga o usuário
                throw new Error('Sessão expirada. Você foi desconectado.');
            }
        }
        
        // Se a resposta final não for OK
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Erro desconhecido.' }));
            throw new Error(error.detail || `Falha na requisição: ${response.statusText}`);
        }

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            return response.json();
        }
        return response;

    } finally {
        isRefreshing = false;
    }
}

export async function fetchUserROIs(limit, offset, variedade, propriedade) {
    let url = `/roi/?limit=${limit}&offset=${offset}`;
    if (variedade) {
        url += `&variedade=${encodeURIComponent(variedade)}`;
    }
    if (propriedade) {
        url += `&propriedade=${encodeURIComponent(propriedade)}`;
    }
    return await fetchApi(url);
}

export async function fetchAvailableVarieties() {
    return await fetchApi('/roi/variedades-disponiveis');
}

export async function fetchAvailableProperties() {
    return await fetchApi('/roi/propriedades-disponiveis');
}

export async function fetchROIDetails(roiId) {
    return await fetchApi(`/roi/${roiId}`);
}

export async function updateUserROI(roiId, data) {
    return await fetchApi(`/roi/${roiId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
}

export async function deleteUserROI(roiId) {
    await fetchApi(`/roi/${roiId}`, {
        method: 'DELETE',
    });
}

export async function uploadShapefile(formData) {
    const response = await fetch(`${BASE_URL}/roi/upload-shapefile-splitter`, {
        method: 'POST',
        body: formData,
        credentials: 'include'
    });

    if (response.status === 401) {
        logout();
        throw new Error('Sessão expirada. Você foi desconectado.');
    }

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Erro no upload do shapefile');
    }
    return response.json();
}
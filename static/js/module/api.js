import { logout } from './auth-session.js';

const BASE_URL = '/api/v1';

export async function fetchApi(url, options = {}) {
    const headers = {
        ...options.headers,
    };

    const config = { 
        ...options, 
        headers,
        credentials: 'include' 
    };

    const response = await fetch(`${BASE_URL}${url}`, config);
    
    if (response.status === 401) {
        logout();
        throw new Error('Sessão expirada. Você foi desconectado.');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Erro desconhecido na resposta da API.' }));
        throw new Error(error.detail || `Falha na requisição: ${response.statusText}`);
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
        return response.json();
    }
    
    return response;
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
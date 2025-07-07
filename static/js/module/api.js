import { logout } from './auth-session.js';

const BASE_URL = '/api/v1';

async function fetchApi(url, options = {}) {
    const headers = {
        'Authorization': 'Bearer ' + localStorage.getItem('access_token'),
        ...options.headers,
    };

    const response = await fetch(`${BASE_URL}${url}`, { ...options, headers });

    // 1. Lógica de renovação de token (sessão deslizante)
    const refreshedToken = response.headers.get('X-Access-Token-Refreshed');
    if (refreshedToken) {
        console.log('Sessão renovada. Novo token armazenado.');
        localStorage.setItem('access_token', refreshedToken);
    }

    // 2. Tratamento de erro de autenticação (token expirado/inválido)
    if (response.status === 401) {
        logout();
        throw new Error('Sessão expirada. Você foi desconectado.');
    }

    // 3. Tratamento de outros erros da API
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Erro desconhecido na resposta da API.' }));
        throw new Error(error.detail || `Falha na requisição: ${response.statusText}`);
    }

    // 4. Retorna a resposta JSON ou a resposta bruta se não houver conteúdo
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
        headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('access_token')
        },
        body: formData
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
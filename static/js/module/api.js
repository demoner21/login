import { logout } from './auth-session.js';

const BASE_URL = '/api/v1';

async function fetchApi(url, options = {}) {
    const headers = {
        'Authorization': 'Bearer ' + localStorage.getItem('access_token'),
        ...options.headers,
    };

    const response = await fetch(`${BASE_URL}${url}`, { ...options, headers });

    if (response.status === 401) {
    // Se o token for inválido/expirado, o servidor retorna 401.
    // Forçamos o logout e interrompemos a execução.
    logout();
    // Lançamos um erro para parar a cadeia de promessas.
    throw new Error('Sessão expirada. Você foi desconectado.');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Erro desconhecido na resposta da API.' }));
        throw new Error(error.detail || `Falha na requisição: ${response.statusText}`);
    }

    return response;
}

export async function fetchUserROIs(limit, offset, variedade) {
    let url = `/roi/?limit=${limit}&offset=${offset}`;
    if (variedade) {
        // Envia o termo de busca como um parâmetro de URL
        url += `&variedade=${encodeURIComponent(variedade)}`;
    }
    const response = await fetchApi(url);

    return await response.json();
}

export async function fetchAvailableVarieties() {
    const response = await fetchApi('/roi/variedades-disponiveis');
    return await response.json();
}

export async function fetchROIDetails(roiId) {
    const response = await fetchApi(`/roi/${roiId}`);
    return await response.json();
}

export async function updateUserROI(roiId, data) {
    const response = await fetchApi(`/roi/${roiId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return await response.json();
}

export async function deleteUserROI(roiId) {
    await fetchApi(`/roi/${roiId}`, {
        method: 'DELETE',
    });
}

export async function uploadShapefile(formData) {
    const response = await fetch('/api/v1/roi/upload-shapefile-splitter', {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('access_token')
        },
        body: formData
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Erro no upload do shapefile');
    }
    return await response.json();
}
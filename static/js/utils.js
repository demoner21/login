/**
 * Utilitários Gerais - Portal Multiespectral
 * Funções auxiliares e utilitárias
 */

/**
 * Toggle entre formulários
 */
function toggleForm(formId) {
    // Remove classe active de todos os formulários
    document.querySelectorAll('.form-container').forEach(form => {
        form.classList.remove('active');
    });
    
    // Adiciona classe active ao formulário selecionado
    document.getElementById(formId).classList.add('active');
    
    // Limpa mensagens ao alternar
    if (window.authManager) {
        window.authManager.clearMessages();
    }
    
    // Focus no primeiro campo do formulário ativo
    setTimeout(() => {
        const activeForm = document.getElementById(formId);
        const firstInput = activeForm.querySelector('input:not([type="checkbox"])');
        if (firstInput) {
            firstInput.focus();
        }
    }, 100);
}

/**
 * Toggle visibilidade da senha
 */
function togglePasswordVisibility(fieldId) {
    if (window.authManager) {
        window.authManager.togglePasswordVisibility(fieldId);
    }
}

/**
 * Debounce function para otimizar performance
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func.apply(this, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(this, args);
    };
}

/**
 * Throttle function para limitar frequência de execução
 */
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Validador de CPF
 */
function isValidCPF(cpf) {
    cpf = cpf.replace(/[^\d]+/g, '');
    
    if (cpf.length !== 11 || !!cpf.match(/(\d)\1{10}/)) {
        return false;
    }
    
    const cpfArray = cpf.split('').map(el => +el);
    const rest = (count) => {
        return (cpfArray.slice(0, count-12).reduce((soma, el, index) => (soma + el * (count-index)), 0) * 10) % 11 % 10;
    };
    
    return rest(10) === cpfArray[9] && rest(11) === cpfArray[10];
}

/**
 * Formatador de CPF
 */
function formatCPF(cpf) {
    return cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
}

/**
 * Formatador de telefone
 */
function formatPhone(phone) {
    phone = phone.replace(/\D/g, '');
    
    if (phone.length === 11) {
        return phone.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    } else if (phone.length === 10) {
        return phone.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
    }
    
    return phone;
}

/**
 * Sanitiza string removendo caracteres especiais
 */
function sanitizeString(str) {
    return str.replace(/[<>\"']/g, '');
}

/**
 * Capitaliza primeira letra de cada palavra
 */
function capitalizeWords(str) {
    return str.replace(/\w\S*/g, (txt) => 
        txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
    );
}

/**
 * Gera ID único
 */
function generateUniqueId(prefix = 'id') {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Copia texto para clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // Fallback para navegadores mais antigos
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            return successful;
        } catch (err) {
            document.body.removeChild(textArea);
            return false;
        }
    }
}

/**
 * Detecta se dispositivo é móvel
 */
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

/**
 * Detecta se está online
 */
function isOnline() {
    return navigator.onLine;
}

/**
 * Formata bytes em unidades legíveis
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Converte data para formato brasileiro
 */
function formatDateBR(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

/**
 * Converte data e hora para formato brasileiro
 */
function formatDateTimeBR(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Valida se data está no futuro
 */
function isFutureDate(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    return date > new Date();
}

/**
 * Calcula diferença entre datas em dias
 */
function daysDiff(date1, date2) {
    const oneDay = 24 * 60 * 60 * 1000;
    const firstDate = new Date(date1);
    const secondDate = new Date(date2);
    
    return Math.round(Math.abs((firstDate - secondDate) / oneDay));
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    
    return text.replace(/[&<>"']/g, (m) => map[m]);
}

/**
 * Remove acentos de uma string
 */
function removeAccents(str) {
    return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

/**
 * Valida se string contém apenas números
 */
function isNumeric(str) {
    return /^\d+$/.test(str);
}

/**
 * Gera cor aleatória em hexadecimal
 */
function getRandomColor() {
    return '#' + Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0');
}

/**
 * Converte hex para RGB
 */
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

/**
 * Obtém contraste de cor (branco ou preto) baseado no background
 */
function getContrastColor(hexColor) {
    const rgb = hexToRgb(hexColor);
    if (!rgb) return '#000000';
    
    const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
    return brightness > 128 ? '#000000' : '#ffffff';
}

/**
 * Smooth scroll para elemento
 */
function scrollToElement(elementId, offset = 0) {
    const element = document.getElementById(elementId);
    if (element) {
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - offset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
    }
}

/**
 * Adiciona máscara de input
 */
function addInputMask(inputId, mask) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    input.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        let maskedValue = '';
        let maskIndex = 0;
        let valueIndex = 0;
        
        while (maskIndex < mask.length && valueIndex < value.length) {
            if (mask[maskIndex] === '#') {
                maskedValue += value[valueIndex];
                valueIndex++;
            } else {
                maskedValue += mask[maskIndex];
            }
            maskIndex++;
        }
        
        e.target.value = maskedValue;
    });
}

/**
 * Mostra notificação toast
 */
function showToast(message, type = 'info', duration = 3000) {
    // Remove toast existente
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Cria novo toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Estilos inline para funcionar sem CSS adicional
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideInRight 0.3s ease-out;
        max-width: 300px;
        word-wrap: break-word;
    `;
    
    // Cores baseadas no tipo
    const colors = {
        success: '#10b981',
        error: '#ef4444',
        warning: '#f59e0b',
        info: '#3b82f6'
    };
    
    toast.style.backgroundColor = colors[type] || colors.info;
    
    document.body.appendChild(toast);
    
    // Remove após duração especificada
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Adiciona estilos de animação para toast se não existirem
if (!document.querySelector('#toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}

// Exporta funções para uso global
window.utils = {
    debounce,
    throttle,
    isValidCPF,
    formatCPF,
    formatPhone,
    sanitizeString,
    capitalizeWords,
    generateUniqueId,
    copyToClipboard,
    isMobileDevice,
    isOnline,
    formatBytes,
    formatDateBR,
    formatDateTimeBR,
    isFutureDate,
    daysDiff,
    escapeHtml,
    removeAccents,
    isNumeric,
    getRandomColor,
    hexToRgb,
    getContrastColor,
    scrollToElement,
    addInputMask,
    showToast
};
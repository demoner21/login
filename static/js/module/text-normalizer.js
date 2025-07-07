/**
 * Módulo de normalização de texto para o frontend.
 * Corrige problemas comuns de codificação e padroniza o case (maiúsculas/minúsculas).
 */

// Mapeamento de correções comuns de caracteres (ex: problemas de encoding Latin-1/UTF-8)
const CHAR_CORRECTIONS = {
    'Ã§': 'ç', 'Ã£': 'ã', 'Ã¢': 'â', 'Ã©': 'é', 'Ãª': 'ê',
    'Ã³': 'ó', 'Ã´': 'ô', 'Ãµ': 'õ', 'Ã¡': 'á', 'Ã­': 'í',
    'Ãº': 'ú', 'ÃƒÂ§': 'ç', 'ÃƒÂ£': 'ã', 'ÃƒÂ¢': 'â',
    'ÃƒÂ©': 'é', 'ÃƒÂª': 'ê', 'ÃƒÂ­': 'í', 'ÃƒÂ³': 'ó',
    'ÃƒÂ´': 'ô', 'ÃƒÂµ': 'õ', 'ÃƒÂº': 'ú', 'Ã ': 'à'
};

// Palavras que devem permanecer em minúsculas em nomes próprios (Title Case)
const LOWERCASE_WORDS = new Set([
    'de', 'do', 'da', 'dos', 'das', 'e', 'em', 'na', 'no',
    'nas', 'nos', 'por', 'para', 'com', 'à', 'a', 'o', 'as', 'os'
]);

export function normalizeName(text, caseType = 'title') {
    if (!text || typeof text !== 'string') {
        return '';
    }

    let normalizedText = text;

    // 1. Aplica correções de caracteres
    for (const [wrong, right] of Object.entries(CHAR_CORRECTIONS)) {
        normalizedText = normalizedText.replace(new RegExp(wrong, 'g'), right);
    }

    // 2. Normalização Unicode padrão
    normalizedText = normalizedText.normalize('NFKC');

    // 3. Remove espaços extras
    normalizedText = normalizedText.replace(/\s+/g, ' ').trim();

    // 4. Aplica a formatação de case
    switch (caseType.toLowerCase()) {
        case 'lower':
            return normalizedText.toLowerCase();
        case 'upper':
            return normalizedText.toUpperCase();
        case 'title':
            return normalizedText.split(' ').map((word, index) => {
                const lowerWord = word.toLowerCase();
                if (index > 0 && LOWERCASE_WORDS.has(lowerWord)) {
                    return lowerWord;
                }
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            }).join(' ');
        default: // 'keep'
            return normalizedText;
    }
}
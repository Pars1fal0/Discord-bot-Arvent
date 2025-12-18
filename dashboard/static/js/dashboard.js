/**
 * Dashboard JavaScript
 * Common utilities and functions
 */

// ==================== Toast Notifications ====================

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - 'success' or 'error'
 * @param {number} duration - Duration in ms (default 3000)
 */
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✅' : '❌';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after duration
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ==================== API Helpers ====================

/**
 * Make an API request
 * @param {string} url - API endpoint
 * @param {object} options - Fetch options
 * @returns {Promise<object>}
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Произошла ошибка');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * GET request helper
 * @param {string} url 
 * @returns {Promise<object>}
 */
async function apiGet(url) {
    return apiRequest(url, { method: 'GET' });
}

/**
 * POST request helper
 * @param {string} url 
 * @param {object} data 
 * @returns {Promise<object>}
 */
async function apiPost(url, data) {
    return apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

// ==================== Form Helpers ====================

/**
 * Populate a select element with options
 * @param {HTMLSelectElement} select 
 * @param {Array} options - Array of {id, name} objects
 * @param {string} prefix - Prefix for option text (e.g., '#' or '@')
 */
function populateSelect(select, options, prefix = '') {
    options.forEach(option => {
        const opt = document.createElement('option');
        opt.value = option.id;
        opt.textContent = `${prefix}${option.name}`;
        if (option.category_name) {
            opt.textContent += ` (${option.category_name})`;
        }
        select.appendChild(opt);
    });
}

/**
 * Set select value if it exists
 * @param {string} selectId 
 * @param {string|number} value 
 */
function setSelectValue(selectId, value) {
    const select = document.getElementById(selectId);
    if (select && value) {
        select.value = value;
    }
}

// ==================== Utility Functions ====================

/**
 * Debounce function
 * @param {Function} func 
 * @param {number} wait 
 * @returns {Function}
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format number with locale
 * @param {number} num 
 * @returns {string}
 */
function formatNumber(num) {
    return num?.toLocaleString() || '—';
}

/**
 * Copy text to clipboard
 * @param {string} text 
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Скопировано в буфер обмена', 'success');
    } catch (err) {
        console.error('Failed to copy:', err);
        showToast('Не удалось скопировать', 'error');
    }
}

// ==================== Loading States ====================

/**
 * Show loading state on button
 * @param {HTMLButtonElement} button 
 * @param {boolean} loading 
 */
function setButtonLoading(button, loading) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = '<span class="loading-spinner"></span> Загрузка...';
    } else {
        button.disabled = false;
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
        }
    }
}

// ==================== Event Listeners ====================

// Handle Enter key in tag inputs
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.id === 'new-allowed-domain') {
        e.preventDefault();
        if (typeof addAllowedDomain === 'function') {
            addAllowedDomain();
        }
    }
    
    if (e.key === 'Enter' && e.target.id === 'new-blocked-domain') {
        e.preventDefault();
        if (typeof addBlockedDomain === 'function') {
            addBlockedDomain();
        }
    }
});

// Log when dashboard JS is loaded
console.log('🎛️ Dashboard JS loaded');

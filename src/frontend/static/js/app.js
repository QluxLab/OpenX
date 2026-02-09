// OpenX Frontend JavaScript

const API_BASE = '/api';

// Get CSRF token from cookie
function getCsrfToken() {
    return getCookie('csrf_token');
}

// Helper function for API calls
async function apiCall(endpoint, options = {}) {
    const sk = getCookie('secret_key');
    const csrfToken = getCsrfToken();

    const headers = {
        'Content-Type': 'application/json',
        ...(sk && { 'X-Secret-Key': sk }),
        ...(csrfToken && options.method && options.method !== 'GET' && { 'X-CSRF-Token': csrfToken }),
        ...options.headers
    };

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// Cookie helpers
function setCookie(name, value, days = 365) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Strict`;
}

function getCookie(name) {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [key, val] = cookie.trim().split('=');
        if (key === name) return decodeURIComponent(val);
    }
    return null;
}

function deleteCookie(name) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
}

// Auth functions
async function register(username) {
    try {
        const data = await apiCall('/auth/new', {
            method: 'POST',
            body: JSON.stringify({ username })
        });

        return data;
    } catch (error) {
        throw error;
    }
}

async function recoverKey(sk, rk) {
    try {
        const data = await apiCall('/auth/recovery', {
            method: 'POST',
            body: JSON.stringify({ sk, rk })
        });

        return data;
    } catch (error) {
        throw error;
    }
}

async function verifyLogin(sk) {
    try {
        const data = await apiCall('/auth/verify', {
            method: 'POST',
            body: JSON.stringify({ sk })
        });
        return data;
    } catch (error) {
        throw error;
    }
}

function logout() {
    deleteCookie('secret_key');
    window.location.href = '/';
}

// Post functions
async function createPost(postData) {
    return apiCall('/user/posts/', {
        method: 'POST',
        body: JSON.stringify(postData)
    });
}

async function createBranchPost(branch, postData) {
    return apiCall(`/branch/${branch}/posts`, {
        method: 'POST',
        body: JSON.stringify(postData)
    });
}

async function deletePost(postId) {
    return apiCall(`/user/posts/${postId}/`, {
        method: 'DELETE'
    });
}

async function updatePost(postId, postData) {
    return apiCall(`/user/posts/${postId}/`, {
        method: 'PATCH',
        body: JSON.stringify(postData)
    });
}

// Branch functions
async function createBranch(name, description) {
    return apiCall('/branch/create', {
        method: 'POST',
        body: JSON.stringify({ name, description })
    });
}

// Media upload
async function uploadMedia(file) {
    const formData = new FormData();
    formData.append('file', file);

    const sk = getCookie('secret_key');
    const csrfToken = getCsrfToken();

    const headers = {
        ...(sk && { 'X-Secret-Key': sk }),
        ...(csrfToken && { 'X-CSRF-Token': csrfToken })
    };

    const response = await fetch(`${API_BASE}/media/upload`, {
        method: 'POST',
        headers,
        body: formData
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
}

// UI Helpers
function showError(element, message) {
    element.textContent = message;
    element.classList.remove('form-success');
    element.classList.add('form-error');
    element.style.display = 'block';
}

function showSuccess(element, message) {
    element.textContent = message;
    element.classList.remove('form-error');
    element.classList.add('form-success');
    element.style.display = 'block';
}

function hideMessage(element) {
    element.style.display = 'none';
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return date.toLocaleDateString();
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

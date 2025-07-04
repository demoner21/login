export function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/static/login.html';
}


export function checkAuth() {
    if (!localStorage.getItem('access_token')) {
        logout();
        return false;
    }
    return true;
}
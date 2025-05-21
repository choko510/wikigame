// static/js/common_utils.js
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Trigger fade in animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100); // Small delay to ensure transition is applied

    // Hide and remove after duration
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 500); // Wait for fade out transition
    }, duration);
}

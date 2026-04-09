document.addEventListener('DOMContentLoaded', function () {
    const menuToggleBtn = document.getElementById('menuToggleBtn');
    const sidebar = document.querySelector('.sidebar');

    if (menuToggleBtn && sidebar) {
        menuToggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('active');
        });

        document.addEventListener('click', function (event) {
            const isClickInsideSidebar = sidebar.contains(event.target);
            const isClickOnMenuButton = menuToggleBtn.contains(event.target);

            if (!isClickInsideSidebar && !isClickOnMenuButton && window.innerWidth <= 768) {
                sidebar.classList.remove('active');
            }
        });
    }

    setupThemeToggle();
    setupGlobalDeleteConfirmation();
    setupChatUnreadBadge();
});

function setupThemeToggle() {
    const root = document.documentElement;
    const toggleBtn = document.getElementById('themeToggleBtn');
    const toggleLabel = document.getElementById('themeToggleLabel');

    const storedTheme = localStorage.getItem('app-theme');
    const preferredTheme = storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : 'dark';
    applyTheme(preferredTheme, toggleBtn, toggleLabel);

    if (!toggleBtn) {
        return;
    }

    toggleBtn.addEventListener('click', function () {
        const currentTheme = root.dataset.theme === 'light' ? 'light' : 'dark';
        const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(nextTheme, toggleBtn, toggleLabel);
        localStorage.setItem('app-theme', nextTheme);
    });
}

function applyTheme(theme, toggleBtn, toggleLabel) {
    document.documentElement.dataset.theme = theme;

    if (!toggleBtn || !toggleLabel) {
        return;
    }

    const icon = toggleBtn.querySelector('i');

    if (theme === 'light') {
        toggleLabel.textContent = 'Темная тема';
        if (icon) {
            icon.className = 'bi bi-moon-stars-fill';
        }
    } else {
        toggleLabel.textContent = 'Светлая тема';
        if (icon) {
            icon.className = 'bi bi-sun-fill';
        }
    }
}

function showGlobalNotification(text, type = 'info') {
    const container = document.getElementById('persistent-notification');
    const textEl = document.getElementById('persistent-notification-text');

    if (!container || !textEl) {
        console.warn('persistent-notification not found');
        return;
    }

    textEl.textContent = text;

    if (type === 'success') {
        container.style.backgroundColor = '#1e3a2e';
        container.style.borderLeftColor = '#22c55e';
    } else if (type === 'error') {
        container.style.backgroundColor = '#475569';
        container.style.borderLeftColor = '#ef4444';
    } else {
        container.style.backgroundColor = '#1e3a2e';
        container.style.borderLeftColor = '#22c55e';
    }

    container.style.display = 'block';
}

function hidePersistentNotification() {
    const container = document.getElementById('persistent-notification');
    if (container) {
        container.style.display = 'none';
    }
}

function setupGlobalDeleteConfirmation() {
    const modalEl = document.getElementById('globalDeleteConfirmModal');
    const textEl = document.getElementById('globalDeleteConfirmText');
    const detailsEl = document.getElementById('globalDeleteConfirmDetails');
    const okBtn = document.getElementById('globalDeleteConfirmOk');

    if (!modalEl || !textEl || !okBtn || typeof bootstrap === 'undefined') {
        return;
    }

    const modal = new bootstrap.Modal(modalEl);
    let pendingForm = null;

    document.querySelectorAll('form[action*="/delete/"]').forEach((form) => {
        form.addEventListener('submit', function (event) {
            if (form.dataset.confirmedDelete === '1') {
                return;
            }
            event.preventDefault();

            pendingForm = form;
            textEl.textContent = form.dataset.confirmMessage || 'Вы точно хотите удалить этот элемент?';
            if (detailsEl) {
                detailsEl.textContent = form.dataset.confirmDetails ||
                    'После удаления исчезнут связанные записи, история согласования и другие привязанные данные.';
            }
            modal.show();
        });
    });

    okBtn.addEventListener('click', function () {
        if (!pendingForm) {
            return;
        }
        pendingForm.dataset.confirmedDelete = '1';
        modal.hide();
        pendingForm.submit();
    });

    modalEl.addEventListener('hidden.bs.modal', function () {
        pendingForm = null;
    });
}

let chatUnreadPollingHandle = null;
let chatUnreadLastCount = null;

function setupChatUnreadBadge() {
    const badge = document.getElementById('chatNavUnreadBadge');
    if (!badge) {
        return;
    }

    if (chatUnreadPollingHandle) {
        clearInterval(chatUnreadPollingHandle);
        chatUnreadPollingHandle = null;
    }

    updateChatUnreadBadge();
    chatUnreadPollingHandle = setInterval(updateChatUnreadBadge, 10000);
}

async function updateChatUnreadBadge() {
    const badge = document.getElementById('chatNavUnreadBadge');
    if (!badge) {
        return;
    }

    try {
        const response = await fetch('/api/chat/unread-count/');
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            return;
        }

        const count = Number(data.unread_count || 0);
        const prevCount = Number(chatUnreadLastCount ?? 0);
        const isIncrease = chatUnreadLastCount !== null && count > prevCount;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.classList.remove('d-none');
            if (isIncrease) {
                badge.classList.remove('is-bump');
                void badge.offsetWidth;
                badge.classList.add('is-bump');
            }
        } else {
            badge.textContent = '0';
            badge.classList.add('d-none');
        }

        chatUnreadLastCount = count;
    } catch (_) {
        // ignore temporary network issues
    }
}

window.updateChatUnreadBadge = updateChatUnreadBadge;

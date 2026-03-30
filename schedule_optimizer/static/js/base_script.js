document.addEventListener('DOMContentLoaded', function () {
    // Проверяем, существует ли кнопка меню
    const menuToggleBtn = document.getElementById('menuToggleBtn');
    const sidebar = document.querySelector('.sidebar');

    if (menuToggleBtn && sidebar) {
        // Toggle sidebar visibility on mobile
        menuToggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('active');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function (event) {
            const isClickInsideSidebar = sidebar.contains(event.target);
            const isClickOnMenuButton = menuToggleBtn.contains(event.target);

            if (!isClickInsideSidebar && !isClickOnMenuButton && window.innerWidth <= 768) {
                sidebar.classList.remove('active');
            }
        });
    }

    setupGlobalDeleteConfirmation();
});


// === УВЕДОМЛЕНИЕ В ШАПКЕ (как на дашборде) ===

function showGlobalNotification(text, type = 'info') {
    const container = document.getElementById('persistent-notification');
    const textEl = document.getElementById('persistent-notification-text');

    if (!container || !textEl) {
        console.warn('persistent-notification не найден.');
        return;
    }

    textEl.textContent = text;

    // Цвета
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

    // Показываем
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

    // Все формы удаления автоматически получат красивое подтверждение.
    document.querySelectorAll('form[action*="/delete/"]').forEach((form) => {
        form.addEventListener('submit', function (event) {
            if (form.dataset.confirmedDelete === '1') return;
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
        if (!pendingForm) return;
        pendingForm.dataset.confirmedDelete = '1';
        modal.hide();
        pendingForm.submit();
    });

    modalEl.addEventListener('hidden.bs.modal', function () {
        pendingForm = null;
    });
}

console.log('base_script.js загружен');

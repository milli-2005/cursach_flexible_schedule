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

    // Дополнительный код для других страниц можно добавить здесь
});


// === УВЕДОМЛЕНИЕ В ШАПКЕ (как на дашборде) ===

function showGlobalNotification(text, type = 'info') {
    const container = document.getElementById('persistent-notification');
    const textEl = document.getElementById('persistent-notification-text');

    if (!container || !textEl) {
        console.warn('⚠️ persistent-notification не найден.');
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
    container.style.display = 'block'; // ← главное!
}

function hidePersistentNotification() {
    const container = document.getElementById('persistent-notification');
    if (container) {
        container.style.display = 'none';
    }
}

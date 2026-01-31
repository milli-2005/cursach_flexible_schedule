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


// === ГЛОБАЛЬНЫЙ УВЕДОМИТЕЛЬ ===
function showGlobalNotification(text, type = 'info') {
    const bar = document.getElementById('global-notification-bar');
    const textEl = document.getElementById('global-notification-text');

    // Стили
    bar.className = 'fixed-top alert alert-dismissible fade show mb-0 border-0 rounded-0 text-center';
    bar.style.display = 'block';

    switch (type) {
        case 'success':
            bar.style.backgroundColor = '#28a745'; // зелёный
            break;
        case 'error':
            bar.style.backgroundColor = '#dc3545'; // красный
            break;
        case 'warning':
            bar.style.backgroundColor = '#ffc107'; // жёлтый
            break;
        default:
            bar.style.backgroundColor = '#17a2b8'; // синий
    }

    textEl.textContent = text;
    bar.classList.add('show');

    // Авто-скрытие через 3 сек
    setTimeout(() => {
        hideGlobalNotification();
    }, 3000);
}

function hideGlobalNotification() {
    const bar = document.getElementById('global-notification-bar');
    bar.classList.remove('show');
    setTimeout(() => {
        bar.style.display = 'none';
    }, 300);
}

// === ПЕРЕОПРЕДЕЛЕНИЕ alert() ===
if (typeof window !== 'undefined') {
    const originalAlert = window.alert;
    window.alert = function(message) {
        showGlobalNotification(String(message), 'info');
        // Не вызываем originalAlert — мы его полностью заменяем
    };
}

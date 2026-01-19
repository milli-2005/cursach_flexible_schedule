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
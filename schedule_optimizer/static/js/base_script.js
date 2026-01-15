document.addEventListener('DOMContentLoaded', function () {
    const menuToggleBtn = document.getElementById('menuToggleBtn');
    const sidebar = document.querySelector('.sidebar');

    // Toggle sidebar visibility on mobile
    if (menuToggleBtn && sidebar) {
        menuToggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('active');
        });
    }

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function (event) {
        const isClickInsideSidebar = sidebar.contains(event.target);
        const isClickOnMenuButton = menuToggleBtn.contains(event.target);

        if (!isClickInsideSidebar && !isClickOnMenuButton && window.innerWidth <= 768) {
            sidebar.classList.remove('active');
        }
    });
});
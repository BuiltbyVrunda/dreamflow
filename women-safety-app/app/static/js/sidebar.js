// Sidebar Toggle Functionality
document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sylvieSidebar');
    const mainContent = document.getElementById('mainContent');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('active');
            mainContent.classList.toggle('shifted');
        });

        // Close sidebar when clicking outside
        document.addEventListener('click', function (event) {
            if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) {
                sidebar.classList.remove('active');
                mainContent.classList.remove('shifted');
            }
        });
    }
});

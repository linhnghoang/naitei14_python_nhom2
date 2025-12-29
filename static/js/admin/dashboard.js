/**
 * Admin Dashboard JavaScript
 * Handles chart rendering, statistics loading, and modal functionality
 */

(function() {
    'use strict';

    // Configuration - these will be set by the template
    let config = {
        statsApiUrl: '',
        activityApiUrl: ''
    };

    // Chart instances
    let booksPerCategoryChart = null;
    let loansOverTimeChart = null;
    let loanStatusChart = null;
    let languageChart = null;

    // Modal elements
    let modal = null;
    let modalCanvas = null;
    let modalCtx = null;
    let modalChartInstance = null;
    let modalTitleEl = null;

    /**
     * Initialize the dashboard with API URLs
     */
    function init(statsUrl, activityUrl) {
        config.statsApiUrl = statsUrl;
        config.activityApiUrl = activityUrl;

        // Register zoom plugin if available
        registerZoomPlugin();

        // Load initial data
        loadDashboardStats();
        loadRecentActivity();

        // Setup statistics controls
        setupStatsControls();

        // Load initial charts
        loadBookStats();
    }

    /**
     * Register Chart.js zoom plugin
     */
    function registerZoomPlugin() {
        const zoomPlugin = window['chartjs-plugin-zoom'] ||
                          (window.ChartZoom && window.ChartZoom.default);
        if (zoomPlugin && Chart && Chart.register) {
            try {
                Chart.register(zoomPlugin);
            } catch (e) {
                console.warn('Zoom plugin register failed:', e);
            }
        }
    }

    /**
     * Fetch JSON with error handling
     */
    function fetchJSON(url) {
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        }).then(response => {
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok || !contentType.includes('application/json')) {
                return response.text().then(text => {
                    throw new Error(`Unexpected response (${response.status}): ${text.substring(0, 200)}...`);
                });
            }
            return response.json();
        });
    }

    /**
     * Load dashboard statistics
     */
    function loadDashboardStats() {
        fetchJSON(config.statsApiUrl)
            .then(data => {
                updateElement('books-count', data.basic.total_books);
                updateElement('users-count', data.basic.total_users);
                updateElement('pending-requests', data.requests.pending);
                updateElement('overdue-loans', data.loans.overdue);
            })
            .catch(error => {
                console.error('Error loading stats:', error);
                ['books-count', 'users-count', 'pending-requests', 'overdue-loans']
                    .forEach(id => updateElement(id, '-'));
            });
    }

    /**
     * Update element text content
     */
    function updateElement(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = typeof value === 'number' ? value.toLocaleString() : value;
        }
    }

    /**
     * Load recent activity
     */
    function loadRecentActivity() {
        fetchJSON(config.activityApiUrl)
            .then(data => {
                const activityList = document.getElementById('recent-activity-list');
                if (!activityList) return;

                if (data.activities && data.activities.length > 0) {
                    activityList.innerHTML = data.activities.map(activity => `
                        <div class="activity-item">
                            <div>
                                <strong>${escapeHtml(activity.message)}</strong>
                                <br><small>${escapeHtml(activity.details)}</small>
                            </div>
                            <div class="activity-time">${escapeHtml(activity.ago)}</div>
                        </div>
                    `).join('');
                } else {
                    activityList.innerHTML = '<p>No recent activity</p>';
                }
            })
            .catch(error => {
                console.error('Error loading activity:', error);
                const activityList = document.getElementById('recent-activity-list');
                if (activityList) {
                    activityList.innerHTML = '<p>Error loading recent activity</p>';
                }
            });
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Setup statistics period controls
     */
    function setupStatsControls() {
        const periodEl = document.getElementById('stats-period');
        const yearEl = document.getElementById('stats-year');
        const monthEl = document.getElementById('stats-month');
        const labelMonth = document.getElementById('label-month');

        if (!periodEl || !yearEl || !monthEl) return;

        const now = new Date();
        yearEl.value = now.getFullYear();
        monthEl.value = now.getMonth() + 1;

        function toggleMonthVisibility() {
            const isYear = periodEl.value === 'year';
            monthEl.style.display = isYear ? 'none' : 'inline-block';
            if (labelMonth) {
                labelMonth.style.display = isYear ? 'none' : 'inline-block';
            }
        }

        periodEl.addEventListener('change', () => {
            toggleMonthVisibility();
            loadBookStats();
        });

        yearEl.addEventListener('change', loadBookStats);
        yearEl.addEventListener('input', loadBookStats);
        monthEl.addEventListener('change', loadBookStats);
        monthEl.addEventListener('input', loadBookStats);

        toggleMonthVisibility();
    }

    /**
     * Load book statistics and render charts
     */
    function loadBookStats() {
        const periodEl = document.getElementById('stats-period');
        const yearEl = document.getElementById('stats-year');
        const monthEl = document.getElementById('stats-month');

        if (!periodEl || !yearEl) return;

        const period = periodEl.value;
        const y = yearEl.value;
        const m = monthEl ? monthEl.value : 1;

        const params = new URLSearchParams({ period, year: y });
        if (period !== 'year') {
            params.set('month', m);
        }

        fetch(`${config.statsApiUrl}?${params.toString()}`, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        })
            .then(r => r.json())
            .then(renderCharts)
            .catch(err => console.error('Error loading book stats:', err));
    }

    /**
     * Build color array for charts
     */
    function buildBarColors(n) {
        const base = [
            '#007cba', '#00a8e8', '#17a2b8', '#28a745', '#20c997',
            '#6f42c1', '#6610f2', '#e83e8c', '#fd7e14', '#ffc107'
        ];
        const colors = [];
        for (let i = 0; i < n; i++) {
            colors.push(base[i % base.length]);
        }
        return colors;
    }

    /**
     * Render all charts with data
     */
    function renderCharts(data) {
        renderBooksPerCategoryChart(data);
        renderLoansOverTimeChart(data);
        renderLoanStatusChart(data);
        renderLanguageChart(data);
    }

    /**
     * Render books per category doughnut chart
     */
    function renderBooksPerCategoryChart(data) {
        const bpc = (data.category_book_counts || []).slice(0, 20);
        const labels = bpc.map(x => x.name);
        const values = bpc.map(x => x.total_books);
        const colors = buildBarColors(bpc.length);

        const ctx = document.getElementById('booksPerCategoryChart');
        if (!ctx) return;

        if (booksPerCategoryChart) booksPerCategoryChart.destroy();

        booksPerCategoryChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sách',
                    data: values,
                    backgroundColor: colors
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } }
            }
        });

        ctx.addEventListener('click', () =>
            openModalForChart(booksPerCategoryChart, 'Số lượng sách theo thể loại'));
    }

    /**
     * Render loans over time line chart
     */
    function renderLoansOverTimeChart(data) {
        const ts = data.time_series || { labels: [], values: [] };
        const ctx = document.getElementById('loansOverTimeChart');
        if (!ctx) return;

        if (loansOverTimeChart) loansOverTimeChart.destroy();

        loansOverTimeChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: ts.labels,
                datasets: [{
                    label: 'Lượt mượn',
                    data: ts.values,
                    borderColor: '#007cba',
                    backgroundColor: 'rgba(0,124,186,0.1)',
                    fill: true,
                    tension: 0.2
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, precision: 0 } }
            }
        });

        ctx.addEventListener('click', () =>
            openModalForChart(loansOverTimeChart, 'Xu hướng mượn theo thời gian'));
    }

    /**
     * Render loan status doughnut chart
     */
    function renderLoanStatusChart(data) {
        const sd = data.status_distribution || [];
        const labels = sd.map(x => x.status);
        const values = sd.map(x => x.total);
        const colors = buildBarColors(sd.length);

        const ctx = document.getElementById('loanStatusChart');
        if (!ctx) return;

        if (loanStatusChart) loanStatusChart.destroy();

        loanStatusChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Yêu cầu',
                    data: values,
                    backgroundColor: colors
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } }
            }
        });

        ctx.addEventListener('click', () =>
            openModalForChart(loanStatusChart, 'Trạng thái yêu cầu mượn sách'));
    }

    /**
     * Render language distribution bar chart
     */
    function renderLanguageChart(data) {
        const ld = (data.language_distribution || []).slice(0, 12);
        const labels = ld.map(x => x.language);
        const values = ld.map(x => x.total);
        const colors = buildBarColors(ld.length);

        const ctx = document.getElementById('languageChart');
        if (!ctx) return;

        if (languageChart) languageChart.destroy();

        languageChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Số lượng sách',
                    data: values,
                    backgroundColor: colors
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, precision: 0 } }
            }
        });

        ctx.addEventListener('click', () =>
            openModalForChart(languageChart, 'Ngôn ngữ sách trong thư viện'));
    }

    /**
     * Ensure modal exists in DOM
     */
    function ensureModal() {
        if (modal) return;

        modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="chart-modal-title">
                <div class="modal-header">
                    <h3 id="chart-modal-title">Biểu đồ</h3>
                    <div class="modal-actions">
                        <button type="button" class="btn secondary" id="chart-reset-zoom">
                            <i class="fa-solid fa-magnifying-glass-minus"></i> Reset zoom
                        </button>
                        <button type="button" class="btn" id="chart-close">
                            <i class="fa-solid fa-xmark"></i> Đóng
                        </button>
                    </div>
                </div>
                <div style="width: 100%; height: 70vh;">
                    <canvas id="modalChart" style="width:100%; height:100%"></canvas>
                </div>
            </div>`;

        document.body.appendChild(modal);

        modalCanvas = modal.querySelector('#modalChart');
        modalCtx = modalCanvas.getContext('2d');
        modalTitleEl = modal.querySelector('#chart-modal-title');

        const modalResetBtn = modal.querySelector('#chart-reset-zoom');
        const modalCloseBtn = modal.querySelector('#chart-close');

        const closeModal = () => {
            modal.style.display = 'none';
            if (modalChartInstance) {
                modalChartInstance.destroy();
                modalChartInstance = null;
            }
        };

        modalCloseBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        modalResetBtn.addEventListener('click', () => {
            if (modalChartInstance && modalChartInstance.resetZoom) {
                modalChartInstance.resetZoom();
            }
        });
    }

    /**
     * Open modal with expanded chart
     */
    function openModalForChart(sourceChart, titleText) {
        ensureModal();

        modalTitleEl.textContent = titleText || 'Biểu đồ';

        // Deep clone data to avoid mutations
        const dataClone = JSON.parse(JSON.stringify(sourceChart.config.data));
        const srcOpts = sourceChart.config.options || {};
        const options = JSON.parse(JSON.stringify(srcOpts));

        // Enable zoom/pan in modal
        options.plugins = options.plugins || {};
        options.plugins.legend = options.plugins.legend || { position: 'top' };
        options.plugins.zoom = {
            zoom: {
                wheel: { enabled: true },
                pinch: { enabled: true },
                drag: { enabled: true },
                mode: 'xy',
            },
            pan: {
                enabled: true,
                mode: 'xy',
                modifierKey: 'shift'
            }
        };
        options.maintainAspectRatio = false;

        if (modalChartInstance) modalChartInstance.destroy();

        modalChartInstance = new Chart(modalCtx, {
            type: sourceChart.config.type,
            data: dataClone,
            options: options
        });

        modal.style.display = 'flex';
    }

    // Expose init function globally
    window.AdminDashboard = { init: init };
})();

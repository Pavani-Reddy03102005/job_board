/* Charts for the Dashboard and Analytics pages.
   Chart.js is loaded once in base.html; the data comes from the page's
   <script id="chart-data"> element (Django json_script). Charts whose
   canvas is not on the current page are simply skipped. */
(function () {
    'use strict';

    var dataEl = document.getElementById('chart-data');
    if (!dataEl) { return; }

    if (typeof Chart === 'undefined') {
        console.error('Chart.js did not load - charts are disabled.');
        return;
    }

    var D = JSON.parse(dataEl.textContent);

    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Poppins', sans-serif";

    var GRID = 'rgba(148, 163, 184, 0.12)';
    var TOOLTIP = {
        backgroundColor: '#0f172a',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        padding: 12,
        titleColor: '#ffffff',
        bodyColor: '#cbd5e1'
    };

    function withCallbacks(callbacks) {
        var t = {};
        for (var k in TOOLTIP) { t[k] = TOOLTIP[k]; }
        t.callbacks = callbacks;
        return t;
    }

    // Returns the canvas when it exists and has data; otherwise shows the
    // empty message (if any) and returns null.
    function prepare(canvasId, emptyId, hasData) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) { return null; }
        if (!hasData) {
            canvas.parentElement.style.display = 'none';
            var empty = document.getElementById(emptyId);
            if (empty) { empty.hidden = false; }
            return null;
        }
        return canvas;
    }

    function scoreColor(score) {
        if (score >= 80) { return '#22c55e'; }
        if (score >= 60) { return '#f59e0b'; }
        return '#ef4444';
    }

    function percent(v) { return v + '%'; }

    // 1. ATS score trend (dashboard)
    var trendCanvas = prepare('trendChart', 'trendEmpty', D.trend.scores.length > 0);
    if (trendCanvas) {
        var ctx = trendCanvas.getContext('2d');
        var fill = ctx.createLinearGradient(0, 0, 0, 340);
        fill.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
        fill.addColorStop(1, 'rgba(139, 92, 246, 0.02)');

        new Chart(trendCanvas, {
            type: 'line',
            data: {
                labels: D.trend.labels,
                datasets: [{
                    label: 'ATS Score',
                    data: D.trend.scores,
                    borderColor: '#38bdf8',
                    backgroundColor: fill,
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#8b5cf6',
                    pointBorderColor: '#ffffff',
                    pointRadius: 5,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: withCallbacks({
                        title: function (items) { return D.trend.names[items[0].dataIndex]; },
                        label: function (c) { return 'ATS Score: ' + c.parsed.y + '%'; }
                    })
                },
                scales: {
                    y: { min: 0, suggestedMax: 100, grid: { color: GRID }, ticks: { callback: percent } },
                    x: { grid: { color: GRID }, title: { display: true, text: 'Upload date' } }
                }
            }
        });
    }

    // 2. Score distribution doughnut (analytics)
    var distTotal = D.distribution.counts.reduce(function (a, b) { return a + b; }, 0);
    var distCanvas = prepare('distChart', 'distEmpty', distTotal > 0);
    if (distCanvas) {
        new Chart(distCanvas, {
            type: 'doughnut',
            data: {
                labels: D.distribution.labels,
                datasets: [{
                    data: D.distribution.counts,
                    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                    borderColor: '#1e293b',
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { padding: 18 } },
                    tooltip: withCallbacks({
                        label: function (c) {
                            var pct = Math.round(c.parsed * 100 / distTotal);
                            return ' ' + c.parsed + ' resume(s) - ' + pct + '%';
                        }
                    })
                }
            }
        });
    }

    // 3. Upload trends (analytics)
    var monthly = D.uploads.granularity === 'month';
    var upCanvas = prepare('uploadChart', 'uploadEmpty', D.uploads.counts.length > 0);
    if (upCanvas) {
        var subtitle = document.getElementById('uploadSubtitle');
        if (subtitle) { subtitle.textContent = monthly ? 'Uploads per month' : 'Uploads per day'; }

        new Chart(upCanvas, {
            type: 'bar',
            data: {
                labels: D.uploads.labels,
                datasets: [{
                    label: 'Uploads',
                    data: D.uploads.counts,
                    backgroundColor: '#38bdf8',
                    borderRadius: 8,
                    maxBarThickness: 48
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: withCallbacks({
                        label: function (c) { return ' ' + c.parsed.y + ' resume(s) uploaded'; }
                    })
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { color: GRID },
                        title: { display: true, text: 'Resumes uploaded' }
                    },
                    x: {
                        grid: { display: false },
                        title: { display: true, text: monthly ? 'Month' : 'Date' }
                    }
                }
            }
        });
    }

    // 4. ATS score performance (analytics)
    var perfCanvas = prepare('perfChart', 'perfEmpty', D.performance.scores.length > 0);
    if (perfCanvas) {
        new Chart(perfCanvas, {
            type: 'bar',
            data: {
                labels: D.performance.labels,
                datasets: [{
                    label: 'ATS Score',
                    data: D.performance.scores,
                    backgroundColor: D.performance.scores.map(scoreColor),
                    borderRadius: 8,
                    maxBarThickness: 56
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: withCallbacks({
                        title: function (items) { return D.performance.full_names[items[0].dataIndex]; },
                        label: function (c) { return 'ATS Score: ' + c.parsed.y + '%'; }
                    })
                },
                scales: {
                    y: { min: 0, suggestedMax: 100, grid: { color: GRID }, ticks: { callback: percent } },
                    x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 0 } }
                }
            }
        });
    }

    // 5. Skills distribution (analytics)
    var skillsCanvas = prepare('skillsChart', 'skillsEmpty', D.skills.labels.length > 0);
    if (skillsCanvas) {
        new Chart(skillsCanvas, {
            type: 'bar',
            data: {
                labels: D.skills.labels,
                datasets: [{
                    label: 'Resumes containing skill',
                    data: D.skills.counts,
                    backgroundColor: '#8b5cf6',
                    borderRadius: 8,
                    maxBarThickness: 28
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: withCallbacks({
                        label: function (c) { return ' Found in ' + c.parsed.x + ' resume(s)'; }
                    })
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { color: GRID },
                        title: { display: true, text: 'Number of resumes' }
                    },
                    y: { grid: { display: false } }
                }
            }
        });
    }
})();
import { fetchStats, fetchLogs, fetchChart } from "./admin-api.js"
import {
	renderStats,
	renderStatsSkeleton,
	renderLogs,
	renderLogsSkeleton,
	renderPagination,
	renderBarChart,
	renderPieChart,
	destroyCharts,
} from "./admin-ui.js"

// ─── المان‌های DOM ────────────────────────────────────────────────
const statsEl = document.getElementById("stats-grid")
const logsEl = document.getElementById("logs-body")
const pagEl = document.getElementById("pagination")
const barCanvas = document.getElementById("bar-chart")
const pieCanvas = document.getElementById("pie-chart")

// ─── state ───────────────────────────────────────────────────────
let currentOffset = 0
let currentDays = 1
let _isFirstLoad = true
const LIMIT = 20

// ─── فیلتر زمانی ─────────────────────────────────────────────────
document.querySelectorAll(".time-filter-btn").forEach((btn) => {
	btn.addEventListener("click", () => {
		document
			.querySelectorAll(".time-filter-btn")
			.forEach((b) => b.classList.remove("active"))
		btn.classList.add("active")
		currentDays = parseInt(btn.dataset.days)
		currentOffset = 0
		_isFirstLoad = true
		loadDashboard(0)
	})
})

// ─── بارگذاری داشبورد ────────────────────────────────────────────
async function loadDashboard(offset = 0) {
	if (_isFirstLoad) {
		renderStatsSkeleton(statsEl)
		renderLogsSkeleton(logsEl)
		pagEl.innerHTML = ""
	}

	try {
		const [stats, logsData, chartData] = await Promise.all([
			fetchStats(currentDays),
			fetchLogs(LIMIT, offset, currentDays),
			fetchChart(currentDays),
		])

		if (!_isFirstLoad) _disableStaggerAnims()

		renderStats(stats, statsEl)
		renderBarChart(chartData, barCanvas)
		renderPieChart(stats.intent_breakdown, pieCanvas)
		renderLogs(logsData.logs, logsEl)
		renderPagination(logsData.total, LIMIT, offset, pagEl, loadDashboard)
		currentOffset = offset
		_isFirstLoad = false
	} catch (err) {
		statsEl.innerHTML = ""
		logsEl.innerHTML = `<tr><td colspan="8" class="empty-state error-state">❌ ${err.message}</td></tr>`
		pagEl.innerHTML = ""
		destroyCharts()
	}
}

// ─── helpers ─────────────────────────────────────────────────────
function _disableStaggerAnims() {
	document
		.querySelectorAll(".stat-card, .chart-card, .logs-card")
		.forEach((el) => el.classList.add("no-anim"))
}

// ─── راه‌اندازی ───────────────────────────────────────────────────
loadDashboard(0)

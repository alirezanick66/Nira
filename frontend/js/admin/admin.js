import { fetchStats, fetchLogs, fetchChart } from "./admin-api.js"
import {
	renderStats,
	renderLogs,
	renderPagination,
	renderBarChart,
	renderPieChart,
} from "./admin-ui.js"

// ─── المان‌های DOM ────────────────────────────────────────────────
const statsEl = document.getElementById("stats-grid")
const logsEl = document.getElementById("logs-body")
const pagEl = document.getElementById("pagination")
const refreshBtn = document.getElementById("refresh-btn")
const barCanvas = document.getElementById("bar-chart")
const pieCanvas = document.getElementById("pie-chart")

// ─── state ───────────────────────────────────────────────────────
let currentOffset = 0
let currentDays = 1
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
		loadDashboard(0)
	})
})

// ─── بارگذاری کامل داشبورد ───────────────────────────────────────
async function loadDashboard(offset = 0) {
	_setLoading(true)
	try {
		const [stats, logsData, chartData] = await Promise.all([
			fetchStats(currentDays),
			fetchLogs(LIMIT, offset, currentDays),
			fetchChart(currentDays),
		])

		renderStats(stats, statsEl)
		renderBarChart(chartData, barCanvas)
		renderPieChart(stats.intent_breakdown, pieCanvas)
		renderLogs(logsData.logs, logsEl)
		renderPagination(logsData.total, LIMIT, offset, pagEl, loadDashboard)
		currentOffset = offset
	} catch (err) {
		statsEl.innerHTML = ""
		logsEl.innerHTML = `<tr><td colspan="9" class="empty-state error-state">❌ ${err.message}</td></tr>`
	} finally {
		_setLoading(false)
	}
}

function _setLoading(on) {
	refreshBtn.classList.toggle("loading", on)
	refreshBtn.disabled = on
}

// ─── راه‌اندازی ───────────────────────────────────────────────────
refreshBtn.addEventListener("click", () => loadDashboard(currentOffset))
loadDashboard(0)

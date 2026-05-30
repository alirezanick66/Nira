import { fetchStats, fetchLogs, fetchChart } from "./admin-api.js"
import {
	renderStats,
	renderStatsSkeleton,
	renderLogs,
	renderLogsSkeleton,
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
const arToggle = document.getElementById("auto-refresh-toggle")
const arDot = document.getElementById("refresh-dot")
const arTimer = document.getElementById("refresh-timer")

// ─── state ───────────────────────────────────────────────────────
let currentOffset = 0
let currentDays = 1
let _autoRefreshId = null
let _countdownId = null
let _secondsLeft = 60
let _isFirstLoad = true
const LIMIT = 20
const REFRESH_SEC = 60

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

// ─── auto-refresh toggle ─────────────────────────────────────────
arToggle.addEventListener("change", () => {
	if (arToggle.checked) _startAutoRefresh()
	else _stopAutoRefresh()
})

function _startAutoRefresh() {
	_stopAutoRefresh()
	arDot.classList.add("active")
	_secondsLeft = REFRESH_SEC
	_updateTimerLabel()

	_countdownId = setInterval(() => {
		_secondsLeft--
		_updateTimerLabel()
		if (_secondsLeft <= 0) {
			_secondsLeft = REFRESH_SEC
			loadDashboard(currentOffset)
		}
	}, 1000)
}

function _stopAutoRefresh() {
	clearInterval(_autoRefreshId)
	clearInterval(_countdownId)
	_autoRefreshId = null
	_countdownId = null
	arDot.classList.remove("active")
	arTimer.textContent = ""
}

function _updateTimerLabel() {
	arTimer.textContent = arToggle.checked ? `${_secondsLeft}s` : ""
}

// ─── بارگذاری داشبورد ────────────────────────────────────────────
async function loadDashboard(offset = 0) {
	// skeleton فقط در اولین لود هر بازه نشون داده میشه
	if (_isFirstLoad) {
		renderStatsSkeleton(statsEl)
		renderLogsSkeleton(logsEl)
		pagEl.innerHTML = ""
	}

	_setLoading(true)

	try {
		const [stats, logsData, chartData] = await Promise.all([
			fetchStats(currentDays),
			fetchLogs(LIMIT, offset, currentDays),
			fetchChart(currentDays),
		])

		// اگه اولین لود بود، انیمیشن stagger فعاله؛ بعدی‌ها بدون انیمیشن
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
		if (_barChart) {
			_barChart.destroy()
			_barChart = null
		}
		if (_pieChart) {
			_pieChart.destroy()
			_pieChart = null
		}
	} finally {
		_setLoading(false)
	}
}

// ─── helpers ─────────────────────────────────────────────────────

function _setLoading(on) {
	refreshBtn.classList.toggle("loading", on)
	refreshBtn.disabled = on
}

/** حذف انیمیشن stagger برای refresh های بعدی (UX کمتر پرت‌کننده) */
function _disableStaggerAnims() {
	document
		.querySelectorAll(".stat-card, .chart-card, .logs-card")
		.forEach((el) => el.classList.add("no-anim"))
}

// ─── راه‌اندازی ───────────────────────────────────────────────────
refreshBtn.addEventListener("click", () => {
	_isFirstLoad = false
	loadDashboard(currentOffset)
	if (arToggle.checked) {
		_secondsLeft = REFRESH_SEC
		_updateTimerLabel()
	}
})

loadDashboard(0)

import { fetchStats, fetchLogs } from "./admin-api.js"
import { renderStats, renderLogs, renderPagination } from "./admin-ui.js"

const statsEl = document.getElementById("stats-grid")
const logsEl = document.getElementById("logs-body")
const pagEl = document.getElementById("pagination")
const refreshBtn = document.getElementById("refresh-btn")

let currentOffset = 0
const LIMIT = 20

async function loadDashboard(offset = 0) {
	statsEl.innerHTML = `<div class="loading-spinner">⏳ بارگذاری آمار...</div>`
	logsEl.innerHTML = `<tr><td colspan="8" class="loading-spinner">دریافت لاگ‌ها...</td></tr>`
	try {
		const stats = await fetchStats()
		renderStats(stats, statsEl)

		const data = await fetchLogs(LIMIT, offset)
		renderLogs(data.logs, logsEl)
		renderPagination(data.logs.length, LIMIT, offset, pagEl, loadDashboard)
		currentOffset = offset
	} catch (err) {
		logsEl.innerHTML = `<tr><td colspan="8" class="empty-state" style="color:var(--danger)">❌ ${err.message}</td></tr>`
	}
}

refreshBtn.onclick = () => loadDashboard(currentOffset)
loadDashboard(0)

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
		const [stats, data] = await Promise.all([
			fetchStats(),
			fetchLogs(LIMIT, offset),
		])

		renderStats(stats, statsEl)
		renderLogs(data.logs, logsEl)

		// ‫پاس دادن total واقعی (نه data.logs.length) برای pagination صحیح
		renderPagination(data.total, LIMIT, offset, pagEl, loadDashboard)
		currentOffset = offset
	} catch (err) {
		statsEl.innerHTML = ""
		logsEl.innerHTML = `<tr><td colspan="8" class="empty-state" style="color:var(--danger)">❌ ${err.message}</td></tr>`
	}
}

refreshBtn.onclick = () => loadDashboard(currentOffset)
loadDashboard(0)

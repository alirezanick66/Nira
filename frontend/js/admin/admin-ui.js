/**
 * لایه رندر داشبورد آنالیتیکس
 * مسئول: رندر stats، چارت‌ها، جدول لاگ‌ها، pagination و skeleton loaders
 */

const INTENT_LABELS = {
	search_refine: "جستجو / اصلاح",
	greeting_unrelated: "احوال‌پرسی",
	clarification: "نیاز به شفاف‌سازی",
}

const INTENT_COLORS = {
	search_refine: "#f5a623",
	greeting_unrelated: "#94a3b8",
	clarification: "#fb923c",
}

let _barChart = null
let _pieChart = null

//────────────────────────────────────────── Public methods ──────────────────────────────────────────

/**
 * رندر skeleton placeholder برای stats cards
 * @param {HTMLElement} container
 * @param {number} count
 */
export function renderStatsSkeleton(container, count = 6) {
	container.innerHTML = Array.from({ length: count })
		.map(
			() => `
		<div class="stat-card-skeleton">
			<span class="skeleton sk-icon"></span>
			<div class="sk-body">
				<span class="skeleton sk-label"></span>
				<span class="skeleton sk-value"></span>
				<span class="skeleton sk-sub"></span>
			</div>
		</div>`,
		)
		.join("")
}

/**
 * رندر skeleton placeholder برای جدول لاگ‌ها
 * @param {HTMLElement} tbody
 * @param {number} rows
 */
export function renderLogsSkeleton(tbody, rows = 8) {
	const widths = [
		"w-md",
		"w-lg",
		"w-sm",
		"w-md",
		"w-xs",
		"w-sm",
		"w-sm",
		"w-xs",
		"w-md",
	]
	tbody.innerHTML = Array.from({ length: rows })
		.map(
			() => `
		<tr class="sk-row">
			${widths.map((w) => `<td><span class="skeleton sk-cell ${w}"></span></td>`).join("")}
		</tr>`,
		)
		.join("")
}

export function renderStats(stats, container) {
	const items = [
		{
			label: "کل کوئری‌ها",
			value: (stats.total_queries ?? 0).toLocaleString("fa-IR"),
			sub: "در بازه انتخابی",
			icon: "ti-chart-bar",
			accent: false,
		},
		{
			label: "میانگین تأخیر",
			value: `${stats.avg_latency_ms ?? 0}<span class="stat-unit">ms</span>`,
			sub: "زمان پاسخ‌دهی",
			icon: "ti-clock",
			accent: false,
		},
		{
			label: "مصرف توکن",
			value: _formatTokens(stats.total_tokens ?? 0),
			sub: "ورودی + خروجی",
			icon: "ti-cpu",
			accent: false,
		},
		{
			label: "نرخ خطا",
			value: `${stats.error_rate_pct ?? "0.0"}%`,
			sub: "پاسخ‌های ناموفق",
			icon: "ti-alert-triangle",
			accent: parseFloat(stats.error_rate_pct) > 5,
			accentColor: "#ef4444",
		},
		{
			label: "صفر نتیجه",
			value: `${stats.zero_results_rate_pct ?? "0.0"}%`,
			sub: `${(stats.zero_results_count ?? 0).toLocaleString("fa-IR")} کوئری`,
			icon: "ti-search-off",
			accent: parseFloat(stats.zero_results_rate_pct) > 10,
			accentColor: "#f59e0b",
		},
		{
			label: "میانگین نتایج",
			value: stats.avg_result_count ?? 0,
			sub: "محصول در هر جستجو",
			icon: "ti-package",
			accent: false,
		},
	]

	container.innerHTML = items
		.map(
			(i) => `
		<div class="stat-card${i.accent ? " stat-card--alert" : ""}" style="${i.accent ? `--alert-clr:${i.accentColor}` : ""}">
			<div class="stat-icon-wrap">
				<i class="ti ${i.icon}" aria-hidden="true"></i>
			</div>
			<div class="stat-body">
				<div class="stat-label">${i.label}</div>
				<div class="stat-value">${i.value}</div>
				<div class="stat-sub">${i.sub}</div>
			</div>
		</div>`,
		)
		.join("")
}

export function renderBarChart(data, canvas) {
	if (_barChart) {
		_barChart.destroy()
		_barChart = null
	}

	const gridColor = "rgba(0,0,0,0.06)"
	const textColor = "#64748b"

	_barChart = new Chart(canvas, {
		type: "bar",
		data: {
			labels: data.labels,
			datasets: [
				{
					label: "تعداد کوئری",
					data: data.counts,
					backgroundColor: (ctx) => {
						const max = Math.max(...data.counts, 1)
						const alpha =
							0.35 + (data.counts[ctx.dataIndex] / max) * 0.65
						return `rgba(245,166,35,${alpha.toFixed(2)})`
					},
					borderColor: "#f5a623",
					borderWidth: 1.5,
					borderRadius: 6,
					borderSkipped: false,
				},
			],
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: { display: false },
				tooltip: {
					rtl: true,
					bodyFont: { family: "Vazirmatn" },
					callbacks: {
						label: (ctx) =>
							` ${ctx.parsed.y.toLocaleString("fa-IR")} کوئری`,
					},
				},
			},
			scales: {
				x: {
					grid: { color: gridColor },
					ticks: {
						color: textColor,
						font: { family: "Vazirmatn", size: 11 },
						maxTicksLimit: 12,
					},
				},
				y: {
					grid: { color: gridColor },
					ticks: {
						color: textColor,
						font: { family: "Vazirmatn", size: 11 },
						precision: 0,
					},
					beginAtZero: true,
				},
			},
		},
	})
}

export function renderPieChart(breakdown, canvas) {
	if (_pieChart) {
		_pieChart.destroy()
		_pieChart = null
	}

	const keys = Object.keys(INTENT_LABELS)
	const values = keys.map((k) => breakdown[k] ?? 0)
	const total = values.reduce((a, b) => a + b, 0)

	if (total === 0) return

	_pieChart = new Chart(canvas, {
		type: "doughnut",
		data: {
			labels: keys.map((k) => INTENT_LABELS[k]),
			datasets: [
				{
					data: values,
					backgroundColor: keys.map((k) => INTENT_COLORS[k]),
					borderWidth: 0,
					hoverOffset: 6,
				},
			],
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			cutout: "68%",
			plugins: {
				legend: {
					position: "bottom",
					rtl: true,
					labels: {
						font: { family: "Vazirmatn", size: 12 },
						color: "#64748b",
						padding: 14,
						usePointStyle: true,
						pointStyleWidth: 10,
					},
				},
				tooltip: {
					rtl: true,
					bodyFont: { family: "Vazirmatn" },
					callbacks: {
						label: (ctx) => {
							const pct = ((ctx.parsed / total) * 100).toFixed(1)
							return ` ${ctx.parsed.toLocaleString("fa-IR")} (${pct}%)`
						},
					},
				},
			},
		},
	})
}

export function renderLogs(logs, tbody) {
	if (!logs?.length) {
		tbody.innerHTML = `<tr><td colspan="9" class="empty-state">📭 هیچ داده‌ای در این بازه ثبت نشده است.</td></tr>`
		return
	}
	tbody.innerHTML = logs
		.map((l) => {
			const time = new Date(l.created_at).toLocaleString("fa-IR", {
				hour12: false,
			})
			const statusClass = _statusBadgeClass(l.response_status)
			const intentClass =
				l.intent === "general_chat" ? "badge-warm" : "badge-primary"
			const filters = l.applied_filters
				? JSON.stringify(l.applied_filters).slice(0, 35) + "…"
				: "—"
			const tokens = (l.prompt_tokens || 0) + (l.completion_tokens || 0)
			const sessionShort = l.session_id ? l.session_id.slice(0, 8) : "—"
			return `<tr>
			<td><span class="mono dim">${time}</span></td>
			<td class="query-cell">${_esc(l.query.slice(0, 45))}${l.query.length > 45 ? "…" : ""}</td>
			<td><span class="badge ${intentClass}">${l.intent}</span></td>
			<td><span class="mono">${l.model_used || "fast_path"}</span></td>
			<td><span class="mono">${tokens.toLocaleString("fa-IR")}</span></td>
			<td><span class="latency${l.latency_ms > 3000 ? " latency--slow" : ""}">${l.latency_ms} ms</span></td>
			<td><span class="badge ${statusClass}">${l.response_status}</span></td>
			<td><span class="mono dim" title="${l.session_id || ""}">${sessionShort}</span></td>
			<td><span class="mono dim" title='${_esc(JSON.stringify(l.applied_filters || {}))}'>${filters}</span></td>
		</tr>`
		})
		.join("")
}

export function renderPagination(total, limit, offset, container, onChange) {
	const hasPrev = offset > 0
	const hasNext = offset + limit < total
	if (!hasPrev && !hasNext) {
		container.innerHTML = ""
		return
	}
	container.innerHTML = `
		<button class="pg-btn" id="pg-prev" ${!hasPrev ? "disabled" : ""}>← قبلی</button>
		<span class="pg-info">${(offset + 1).toLocaleString("fa-IR")}–${Math.min(offset + limit, total).toLocaleString("fa-IR")} از ${total.toLocaleString("fa-IR")}</span>
		<button class="pg-btn" id="pg-next" ${!hasNext ? "disabled" : ""}>بعدی →</button>
	`
	if (hasPrev)
		container.querySelector("#pg-prev").onclick = () =>
			onChange(offset - limit)
	if (hasNext)
		container.querySelector("#pg-next").onclick = () =>
			onChange(offset + limit)
}

//────────────────────────────────────────── Private Methods ──────────────────────────────────────────

function _statusBadgeClass(status) {
	const map = {
		success: "badge-success",
		error: "badge-danger",
		empty: "badge-warn",
		clarification: "badge-info",
	}
	return map[status] || "badge-neutral"
}

function _formatTokens(n) {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
	if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
	return n.toLocaleString("fa-IR")
}

function _esc(str) {
	return str
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
}

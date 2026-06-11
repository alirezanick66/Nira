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
// ─── تنظیم فونت پیش‌فرض برای تمام چارت‌ها ───
if (typeof Chart !== "undefined") {
	Chart.defaults.font.family = "Mikhak"
	Chart.defaults.font.size = 12 // در صورت نیاز به تنظیم سایز استاندارد چارت‌ها
}
let _barChart = null
let _pieChart = null

//────────────────────────────────────────── Public methods ──────────────────────────────────────────

/**
 * رندر skeleton placeholder برای stats cards
 * @param {HTMLElement} container
 * @param {number} count
 */
export function renderStatsSkeleton(container, count = 5) {
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
			value: _formatLatency(stats.avg_latency_ms ?? 0),
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
		tbody.innerHTML = `<tr><td colspan="8" class="empty-state">📭 هیچ داده‌ای در این بازه ثبت نشده است.</td></tr>`
		return
	}
	tbody.innerHTML = logs
		.map((l) => {
			const d = new Date(l.created_at)
			const dateStr = d.toLocaleDateString("fa-IR")
			const timeStr = d.toLocaleTimeString("fa-IR", {
				hour12: false,
				hour: "2-digit",
				minute: "2-digit",
			})
			const statusClass = _statusBadgeClass(l.response_status)
			const intentClass =
				l.intent === "general_chat" ? "badge-warm" : "badge-primary"
			const filters = _parseFilters(l.applied_filters)
			const tokens = (l.prompt_tokens || 0) + (l.completion_tokens || 0)

			return `<tr>
			<td><span class="mono" dir="ltr">${dateStr} - ${timeStr}</span></td>
			<td class="query-cell">${(l.query?.length ?? 0) > 45 ? `<span class="query-text" data-full="${_esc(l.query ?? "")}">${_esc((l.query ?? "").slice(0, 45))}…</span>` : _esc(l.query ?? "")}</td>
			<td><span class="badge ${intentClass}">${_formatIntent(l.intent)}</span></td>
			<td>${_formatModel(l.model_used)}</td>
			<td><span class="mono">${tokens}</span></td>
			<td><span class="latency" dir="ltr">${_formatLatency(l.latency_ms ?? 0)}</span></td>
			<td><span class="badge ${statusClass}">${_statusLabel(l.response_status)}</span></td>
			<td class="filters-cell">${filters}</td>
		</tr>`
		})
		.join("")
}
function _formatIntent(intent) {
	const map = {
		search_refine: "جستجو / اصلاح",
		greeting_unrelated: "احوال‌پرسی",
		clarification: "نیاز به شفاف‌سازی",
		general_chat: "گفتگوی عمومی",
	}
	return map[intent] || intent
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
/**
 * نابودسازی نمونه‌های Chart.js برای جلوگیری از memory leak هنگام re-render
 * باید قبل از هر بار رسم مجدد یا هنگام خطا فراخوانده شود.
 */
export function destroyCharts() {
	if (_barChart) {
		_barChart.destroy()
		_barChart = null
	}
	if (_pieChart) {
		_pieChart.destroy()
		_pieChart = null
	}
}
//────────────────────────────────────────── Private Methods ──────────────────────────────────────────
function _formatLatency(ms) {
	if (ms >= 1000) return `${(ms / 1000).toFixed(1)}`
	return `${Math.round(ms)}`
}
function _statusLabel(status) {
	const map = {
		success: "موفق",
		error: "خطا",
		empty: "خالی",
		clarification: "نیاز به شفاف‌سازی",
	}
	return map[status] || status
}
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

/**
 * فیلتر JSON خام را به تگ‌های فارسی خوانا تبدیل می‌کند.
 * @param {Object|null} filters
 * @returns {string} HTML تگ‌های فیلتر
 */
function _parseFilters(filters) {
	if (!filters || !Object.keys(filters).length)
		return "<span class='filter-empty'>—</span>"

	// ─── نگاشت کلیدها به فارسی ───────────────────────────────────
	const KEY_LABELS = {
		price: { label: "قیمت", icon: "💰", unit: "M", isPrice: true },
		ram_gb: { label: "رم", icon: "🔧", unit: "GB" },
		storage_gb: { label: "حافظه", icon: "💾", unit: "GB" },
		camera_mp: { label: "دوربین", icon: "📷", unit: "MP" },
		battery_mah: { label: "باتری", icon: "🔋", unit: "mAh" },
		brand: { label: "برند", icon: "🏷️", unit: "" },
		brand_not: { label: "نه‌برند", icon: "🚫", unit: "" },
		screen_size: { label: "صفحه", icon: "📱", unit: "اینچ" },
		weight_g: { label: "وزن", icon: "⚖️", unit: "g" },
		camera_quality: { label: "کیفیت دوربین", icon: "📷", unit: "" },
		category: { label: "دسته‌بندی", icon: "📂", unit: "" },
	}

	// ─── نگاشت اپراتورها به فارسی ────────────────────────────────
	const OP_LABELS = {
		"<=": "حداکثر",
		">=": "حداقل",
		"==": "",
		in: "",
		not_in: "نه",
	}

	const tags = []

	for (const [key, value] of Object.entries(filters)) {
		const meta = KEY_LABELS[key] || { label: key, icon: "🔹", unit: "" }

		// مقدار ساده (string/number) — مثل brand: "samsung"
		if (typeof value !== "object" || Array.isArray(value)) {
			const displayVal = Array.isArray(value) ? value.join("، ") : value
			tags.push(_makeFilterTag(meta, "", displayVal))
			continue
		}

		// مقدار آبجکت با اپراتور — مثل price: {"<=": 30000000}
		for (const [op, val] of Object.entries(value)) {
			const opLabel = OP_LABELS[op] ?? op
			const displayVal = _formatFilterValue(val, meta)
			tags.push(_makeFilterTag(meta, opLabel, displayVal))
		}
	}

	return tags.join("")
}

/**
 * یک تگ فیلتر HTML می‌سازد.
 * @param {{label:string, icon:string, unit:string}} meta
 * @param {string} opLabel
 * @param {string} displayVal
 * @returns {string}
 */
function _makeFilterTag(meta, opLabel, displayVal) {
	const text = opLabel
		? `${meta.icon} ${meta.label}: ${opLabel} ${displayVal}`
		: `${meta.icon} ${meta.label}: ${displayVal}`
	return `<span class="filter-tag">${_esc(text)}</span>`
}

/**
 * مقدار فیلتر را با توجه به نوع کلید فرمت می‌کند.
 * @param {*} val
 * @param {{unit:string, isPrice?:boolean}} meta
 * @returns {string}
 */
function _formatFilterValue(val, meta) {
	if (meta.isPrice && typeof val === "number") {
		const millions = val / 1_000_000
		// اگر عدد صحیح بود بدون اعشار، وگرنه یه رقم اعشار
		const formatted = Number.isInteger(millions)
			? millions.toLocaleString("fa-IR")
			: millions.toFixed(1)
		return `${formatted}M تومان`
	}
	if (Array.isArray(val)) return val.join("، ")
	if (meta.unit) return `${val} ${meta.unit}`
	return String(val)
}
/**
 * نام خام مدل را به برچسب خوانا تبدیل می‌کند.
 * @param {string|null} model
 * @returns {string} HTML badge
 */
function _formatModel(model) {
	if (!model || model === "unknown")
		return '<span class="mono dim" style="background:transparent; padding:0;">—</span>'
	const MODEL_LABELS = {
		fast_path: { label: "Fast Path", cls: "badge-success" },
		"llama-3.3-70b-versatile": {
			label: "Llama 3.3 70B",
			cls: "badge-primary",
		},
		"llama-3.1-8b-instant": { label: "Llama 3.1 8B", cls: "badge-info" },
		"gemini-2.0-flash": { label: "Gemini 2.0 Flash", cls: "badge-warn" },
		"gemini-1.5-flash": { label: "Gemini 1.5 Flash", cls: "badge-warn" },
		"gemini-2.5-flash-preview-05-20": {
			label: "Gemini 2.5 Flash",
			cls: "badge-warn",
		},
	}

	const raw = model || "fast_path"
	const meta = MODEL_LABELS[raw] ?? { label: raw, cls: "badge-neutral" }
	return `<span class="badge ${meta.cls}">${meta.label}</span>`
}

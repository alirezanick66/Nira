/**
 * لایه رندر داشبورد آنالیتیکس
 * مسئول: رندر stats، چارت‌ها، جدول لاگ‌ها، pagination و skeleton loaders
 */

const INTENT_LABELS = {
	search_refine: "جستجو / اصلاح",
	greeting_count: "احوال‌پرسی",
	general_chat_count: "گفتگوی عمومی",
	clarification: "نیاز به شفاف‌سازی",
	compare_count: "مقایسه",
}

const INTENT_COLORS = {
	search_refine: "#0d9488", // سبز-آبی تیره (Teal)
	compare_count: "#059669", // سبز جنگلی ملایم
	clarification: "#ea580c", // نارنجی آجری کدر
	general_chat_count: "#6d28d9", // بنفش دارک
	greeting_count: "#94a3b8", // خاکستری روشن ملایم
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
						maxTicksLimit: 12,
					},
				},
				y: {
					grid: { color: gridColor },
					ticks: {
						color: textColor,
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
						color: "#64748b",
						padding: 14,
						usePointStyle: true,
						pointStyleWidth: 10,
					},
				},
				tooltip: {
					rtl: true,
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
			// ✅ منطق کوتاه‌کردن و Tooltip برای پاسخ LLM
			const expText = l.llm_explanation || "—"

			return `<tr>
    <td><span class="mono" dir="ltr">${dateStr} - ${timeStr}</span></td>
    <td class="query-cell">
        ${
			(l.query?.length ?? 0) > 45
				? `<span class="query-tooltip-anchor" data-full="${_esc(l.query ?? "")}"><span class="query-text-ellipsis">${_esc((l.query ?? "").slice(0, 45))}…</span></span>`
				: _esc(l.query ?? "")
		}
    </td>
    <td class="llm-response-cell">
        ${
			expText.length > 45
				? `<span class="query-tooltip-anchor" data-full="${_esc(expText)}"><span class="query-text-ellipsis">${_esc(expText.slice(0, 45))}…</span></span>`
				: _esc(expText)
		}
    </td>
    <td><span class="badge ${intentClass}">${_formatIntent(l.intent)}</span></td>
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
		search: "جستجو",
		refine: "اصلاح نتایج",
		search_refine: "جستجو / اصلاح",
		general_chat: "گفتگوی عمومی",
		greeting: "احوال‌پرسی",
		clarification: "نیاز به شفاف‌سازی",
		compare: "مقایسه",
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
	if (ms >= 1000) {
		return (ms / 1000).toFixed(1)
	}
	const sec = (ms / 1000).toFixed(1)
	// اگر مقدار آنقدر کم بود که 0.0 شد، آن را به 0 ساده تبدیل کن
	return sec === "0.0" ? "0" : sec
}
function _statusLabel(status) {
	const map = {
		success: "موفق",
		error: "خطا",
		empty: "خالی",
		clarification: "نیاز به شفاف‌سازی",
		partial: " نسبی",
	}
	return map[status] || status
}
function _statusBadgeClass(status) {
	const map = {
		success: "badge-success",
		error: "badge-danger",
		empty: "badge-warn",
		clarification: "badge-info",
		partial: "badge-warn",
	}
	return map[status] || "badge-neutral"
}

function _formatTokens(n) {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
	if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
	return n.toLocaleString("fa-IR")
}

function _esc(str) {
	if (typeof str !== "string") {
		str = String(str ?? "")
	}
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
		price: { label: "قیمت", unit: "M", isPrice: true },
		ram_gb: { label: "رم", unit: "GB" },
		storage_gb: { label: "حافظه", unit: "GB" },
		camera_mp: { label: "دوربین", unit: "MP" },
		battery_mah: { label: "باتری", unit: "mAh" },
		brand: { label: "برند", unit: "" },
		brand_not: { label: "نه‌برند", unit: "" },
		screen_size: { label: "صفحه", unit: "اینچ" },
		weight_g: { label: "وزن", unit: "g" },
		camera_quality: { label: "کیفیت دوربین", unit: "" },
		category: { label: "دسته‌بندی", unit: "" },
	}

	const tags = []

	for (const [key, value] of Object.entries(filters)) {
		const meta = KEY_LABELS[key] || { label: key, unit: "" }

		// مقدار ساده (string/number/array) — مثل brand: "samsung"
		if (typeof value !== "object" || Array.isArray(value)) {
			const displayVal = Array.isArray(value) ? value.join("، ") : value
			tags.push(_makeFilterTag(meta, displayVal))
			continue
		}

		// مقدار آبجکت با اپراتور — تجمیع min/max
		const ops = Object.keys(value)
		const hasMin = ops.includes(">=")
		const hasMax = ops.includes("<=")

		if (hasMin && hasMax) {
			const minVal = _formatFilterValue(value[">="], meta)
			const maxVal = _formatFilterValue(value["<="], meta)
			tags.push(_makeFilterTag(meta, `${minVal} – ${maxVal}`))
		} else if (hasMin) {
			const minVal = _formatFilterValue(value[">="], meta)
			tags.push(_makeFilterTag(meta, `از ${minVal}`))
		} else if (hasMax) {
			const maxVal = _formatFilterValue(value["<="], meta)
			tags.push(_makeFilterTag(meta, `تا ${maxVal}`))
		} else {
			for (const [op, val] of Object.entries(value)) {
				const displayVal = _formatFilterValue(val, meta)
				tags.push(_makeFilterTag(meta, displayVal))
			}
		}
	}

	return `<div class="filter-tags-wrap">${tags.join("")}</div>`
}

/**
 * یک تگ فیلتر HTML می‌سازد.
 * @param {{label:string, icon:string, unit:string}} meta
 * @param {string} opLabel
 * @param {string} displayVal
 * @returns {string}
 */
function _makeFilterTag(meta, displayVal) {
	return `<span class="filter-tag">${_esc(meta.label)}: ${_esc(displayVal)}</span>`
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

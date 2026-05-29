export function renderStats(stats, container) {
	const items = [
		{
			label: "⏱️ میانگین تأخیر",
			value: `${stats.avg_latency_ms ?? 0} ms`,
			sub: "زمان پاسخ‌دهی",
		},
		{
			label: "🔢 مصرف کل توکن",
			value: (stats.total_tokens ?? 0).toLocaleString("fa-IR"),
			sub: "ورودی + خروجی",
		},
		{
			label: "📊 تعداد کل کوئری",
			value: (stats.total_queries ?? 0).toLocaleString("fa-IR"),
			sub: "در دوره فعال",
		},
		{
			label: "⚠️ نرخ خطا",
			value: `${stats.error_rate_pct ?? "0.0"}%`,
			sub: "پاسخ‌های ناموفق",
		},
	]
	container.innerHTML = items
		.map(
			(i) => `
		<div class="stat-card">
			<div class="stat-label">${i.label}</div>
			<div class="stat-value">${i.value}</div>
			<div class="stat-sub">${i.sub}</div>
		</div>
	`,
		)
		.join("")
}

export function renderLogs(logs, tbody) {
	if (!logs?.length) {
		tbody.innerHTML = `<tr><td colspan="8" class="empty-state">📭 هیچ داده‌ای ثبت نشده است.</td></tr>`
		return
	}
	tbody.innerHTML = logs
		.map((l) => {
			const time = new Date(l.created_at).toLocaleString("fa-IR", {
				hour12: false,
			})
			const badgeClass =
				l.response_status === "error"
					? "badge-danger"
					: l.intent === "general_chat"
						? "badge-warning"
						: "badge-success"
			const filters = l.applied_filters
				? JSON.stringify(l.applied_filters).slice(0, 35) + "…"
				: "—"
			const tokens = (l.prompt_tokens || 0) + (l.completion_tokens || 0)
			return `<tr>
			<td><span class="mono">${time}</span></td>
			<td>${l.query.slice(0, 45)}${l.query.length > 45 ? "…" : ""}</td>
			<td><span class="badge ${badgeClass}">${l.intent}</span></td>
			<td><span class="mono">${l.model_used || "fast_path"}</span></td>
			<td><span class="mono">${tokens.toLocaleString("fa-IR")}</span></td>
			<td>${l.latency_ms} ms</td>
			<td><span class="badge ${l.response_status === "error" ? "badge-danger" : "badge-info"}">${l.response_status}</span></td>
			<td><span class="mono" title='${JSON.stringify(l.applied_filters || {})}'>${filters}</span></td>
		</tr>`
		})
		.join("")
}

export function renderPagination(total, limit, offset, container, onChange) {
	if (total < limit) {
		container.innerHTML = ""
		return
	}
	container.innerHTML = `
		<button class="admin-btn ${offset > 0 ? "" : "disabled"}" ${offset <= 0 ? "disabled" : ""}>← قبلی</button>
		<button class="admin-btn">بعدی →</button>
	`
	container
		.querySelectorAll("button")
		.forEach(
			(btn) =>
				(btn.style.cursor = btn.disabled ? "not-allowed" : "pointer"),
		)
	container.querySelectorAll("button")[0].onclick = () =>
		onChange(offset - limit)
	container.querySelectorAll("button")[1].onclick = () =>
		onChange(offset + limit)
}

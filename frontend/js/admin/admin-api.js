const API_BASE = "/api/v1/admin"
const DEMO_API_KEY = "abc12332424sdf5224" // کلید دمو مطابق api.js

async function _fetch(path, params = {}) {
	const url = new URL(`${API_BASE}${path}`, window.location.origin)
	Object.entries(params).forEach(
		([k, v]) => v != null && url.searchParams.set(k, v),
	)
	const res = await fetch(url, { headers: { "X-API-Key": DEMO_API_KEY } })
	if (!res.ok) throw new Error(`خطای شبکه: ${res.status} ${res.statusText}`)
	return res.json()
}

export async function fetchStats() {
	return _fetch("/stats")
}
export async function fetchLogs(limit = 20, offset = 0) {
	return _fetch("/logs", { limit, offset })
}

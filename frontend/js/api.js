/**
 * لایه API — مدیریت اتصال SSE به بک‌اند
 * این ماژول هیچ وابستگی مستقیم به DOM یا ui.js ندارد.
 * تمام رویدادها از طریق callback به لایه بالاتر منتقل می‌شوند.
 */

/** @type {EventSource|null} اتصال SSE جاری */
let _currentEs = null

/** @type {ReturnType<typeof setTimeout>|null} تایمر timeout درخواست */
let _timeoutId = null

/** @type {boolean} قفل همزمانی — جلوگیری از درخواست موازی */
let _isSending = false

/** مدت زمان timeout درخواست (میلی‌ثانیه) */
const REQUEST_TIMEOUT_MS = 60_000

// ─── نگاشت مراحل pipeline ────────────────────────────────────────

/** @type {Record<string, string>} */
const STEP_MESSAGES = {
	extract: "در حال پردازش پیام شما...",
	searching: "در حال جستجوی محصولات...",
	reranking: "در حال ارزیابی محصولات...",
	generating: "در حال آماده‌سازی پاسخ...",
}

// ─── cleanup داخلی ───────────────────────────────────────────────

/**
 * اتصال SSE و تایمر جاری را می‌بندد و state را ریست می‌کند.
 */
function _cleanup() {
	if (_currentEs) {
		_currentEs.close()
		_currentEs = null
	}
	if (_timeoutId) {
		clearTimeout(_timeoutId)
		_timeoutId = null
	}
	_isSending = false
}

// ─── شروع جستجو ──────────────────────────────────────────────────

/**
 * @typedef {Object} SearchCallbacks
 * @property {function(string): void} onStatus  - پیام وضعیت مرحله جاری
 * @property {function(Object): void} onResult  - داده کامل پاسخ موفق
 * @property {function(string): void} onError   - پیام خطا
 * @property {function(): void}       onTimeout -‫ فراخوانده شدن در صورت timeout
 */

/**
 * ‫کوئری کاربر را از طریق SSE به بک‌اند ارسال می‌کند.
 * @param {string}          query
 * @param {string}          sessionId
 * @param {SearchCallbacks} callbacks
 * @returns {boolean} آیا درخواست شروع شد یا خیر
 */
export function startSearch(query, sessionId, callbacks) {
	if (_isSending) return false

	// بستن اتصال احتمالی قبلی
	_cleanup()
	_isSending = true

	const { onStatus, onResult, onError, onTimeout } = callbacks

	//ارسال درخواست با پارامترهای لازم
	const params = new URLSearchParams({
		query,
		top_k: "2",
		session_id: sessionId,
		api_key: "abc12332424sdf5224", //‫ کلید API ثابت برای نسخه دمو (در نسخه واقعی باید مدیریت شود)
	})
	const es = new EventSource(`/api/v1/search/stream?${params.toString()}`)
	_currentEs = es

	// ── timeout ─────────────────────────────────────────────────
	_timeoutId = setTimeout(() => {
		_cleanup()
		onTimeout?.()
	}, REQUEST_TIMEOUT_MS)

	// ── رویداد وضعیت مرحله ──────────────────────────────────────
	es.addEventListener("status", (e) => {
		try {
			const { step, message } = JSON.parse(e.data)
			onStatus(STEP_MESSAGES[step] ?? step)
		} catch {
			console.warn("Invalid status event:", e.data)
		}
	})

	// ── رویداد نتیجه موفق ───────────────────────────────────────
	es.addEventListener("result", (e) => {
		_cleanup()

		let data
		try {
			data = JSON.parse(e.data)
		} catch {
			onError("پاسخ دریافتی نامعتبر است.")
			return
		}

		onResult(data)
	})

	// ── رویداد خطا ──────────────────────────────────────────────
	es.addEventListener("error", (e) => {
		_cleanup()

		let msg = "خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید."
		if (e.data) {
			try {
				const parsed = JSON.parse(e.data)
				if (parsed.message) msg = parsed.message
			} catch {
				/* داده‌ای برای parse وجود ندارد */
			}
		}
		onError(msg)
	})

	return true
}

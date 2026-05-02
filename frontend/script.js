/**
 * Entry Point — اتصال رویدادهای UI به لایه‌های api و ui
 * این فایل فقط orchestration انجام می‌دهد و منطق تجاری ندارد.
 */

import { getSessionId, setSessionId } from "./js/session.js"
import {
	switchToChatMode,
	showStatus,
	removeStatus,
	addMessage,
	renderProducts,
	renderQuickActions,
	setActionButtonsDisabled,
} from "./js/ui.js"
import { startSearch } from "./js/api.js"

// ─── گزارش خطاهای runtime به سرور ───────────────────────────────
window.onerror = function (message, source, lineno) {
	fetch("/api/log-error", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ message, source, lineno }),
	}).catch((e) => console.error("Failed to send log", e))
	return true
}

// ─── المان‌های UI ─────────────────────────────────────────────────
const inputEl = document.getElementById("query-input")

// ─── هسته اصلی ───────────────────────────────────────────────────

/**
 * کوئری کاربر را پردازش و به api.js تحویل می‌دهد.
 * @param {string} [overrideQuery] - کوئری از دکمه‌های اکشن (اختیاری)
 */
function handleSend(overrideQuery) {
	const query = overrideQuery ?? inputEl.value.trim()
	if (!query) return

	switchToChatMode()
	inputEl.value = ""
	inputEl.style.height = "auto"
	inputEl.disabled = true
	setActionButtonsDisabled(true)

	addMessage("user", query)

	const started = startSearch(query, getSessionId(), {
		onStatus(text) {
			showStatus(text)
		},

		onResult(data) {
			removeStatus()

			const aiTextEl = addMessage("ai")
			aiTextEl.textContent =
				data.llm_explanation || data.message || "پاسخی دریافت نشد."

			if (data.results?.length) renderProducts(data.results)

			// callback برای دکمه‌های اکشن — query رو مستقیم به handleSend میده
			renderQuickActions((q) => handleSend(q))

			if (data.session_id) setSessionId(data.session_id)

			_resetInput()
		},

		onError(msg) {
			removeStatus()
			addMessage("ai", `❌ ${msg}`)
			_resetInput()
		},

		onTimeout() {
			removeStatus()
			addMessage(
				"ai",
				"❌ زمان درخواست به پایان رسید. لطفاً دوباره تلاش کنید.",
			)
			_resetInput()
		},
	})

	// اگر درخواست به دلیل isSending شروع نشد، ورودی رو آزاد کن
	if (!started) {
		inputEl.disabled = false
		setActionButtonsDisabled(false)
	}
}

/** ورودی را فعال و فوکوس می‌کند. */
function _resetInput() {
	inputEl.disabled = false
	setActionButtonsDisabled(false)
	inputEl.focus()
}

// ─── رویداد Enter ────────────────────────────────────────────────
inputEl.addEventListener("keydown", (e) => {
	if (e.key === "Enter" && !e.shiftKey) {
		e.preventDefault()
		handleSend()
	}
})

// ─── auto-resize textarea ─────────────────────────────────────────
inputEl.addEventListener("input", () => {
	inputEl.style.height = "auto"
	inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + "px"
})

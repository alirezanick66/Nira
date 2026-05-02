window.onerror = function (message, source, lineno, colno, error) {
	fetch("/api/log-error", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ message, source, lineno }),
	}).catch((e) => console.error("Failed to send log", e))
	return true
}

const chatEl = document.getElementById("chat")
const inputEl = document.getElementById("query-input")

// ─── مدیریت Session ──────────────────────────────────────────────
let sessionId = localStorage.getItem("nira_session") || crypto.randomUUID()
localStorage.setItem("nira_session", sessionId)

// ─── نگاشت مراحل pipeline به پیام‌های فارسی ─────────────────────
const STEP_MESSAGES = {
	nlu: "در حال پردازش پیام شما...",
	searching: "در حال جستجو در محصولات...",
	reranking: "در حال ارزیابی و رتبه‌بندی نتایج...",
	generating: "در حال آماده‌سازی پاسخ...",
}

// ─── تغییر حالت welcome → chat ───────────────────────────────────

/**
 * اولین باری که کاربر سوال می‌فرستد، layout به حالت chat تبدیل می‌شود.
 */
function switchToChatMode() {
	const body = document.body
	if (body.classList.contains("chat-mode")) return
	body.classList.remove("welcome-mode")
	body.classList.add("chat-mode")
}

// ─── وضعیت زنده ──────────────────────────────────────────────────

/** @type {HTMLElement|null} */
let activeStatusEl = null

/**
 * یک المان status جدید می‌سازد یا متن موجود را به‌روز می‌کند.
 * @param {string} text
 */
function showStatus(text) {
	if (!activeStatusEl) {
		activeStatusEl = document.createElement("div")
		activeStatusEl.className = "status active"
		chatEl.appendChild(activeStatusEl)
	}
	activeStatusEl.textContent = text
	chatEl.scrollTop = chatEl.scrollHeight
}

/** المان status را حذف می‌کند. */
function removeStatus() {
	if (activeStatusEl) {
		activeStatusEl.remove()
		activeStatusEl = null
	}
}

// ─── رندر کارت‌های محصول ─────────────────────────────────────────

/**
 * حداکثر ۲ کارت محصول را رندر می‌کند.
 * @param {Array<Object>} products
 */
function renderProducts(products) {
	if (!products?.length) return
	const wrapper = document.createElement("div")
	wrapper.className = "products"
	products.slice(0, 2).forEach((p) => {
		// اضافه کردن مقدار پیش‌فرض برای فیلدهای ممکن است undefined باشند
		const title = p.title || "بدون عنوان"
		const imageUrl =
			p.image_url || "https://placehold.co/300x300?text=No+Image"
		const price = Number(p.price).toLocaleString("fa-IR") || "۰"
		const priceRange = p.price_range || "متغیر"
		const camera = p.camera_quality || "نامشخص"
		const tags = p.tags?.length ? p.tags : ["موبایل"]
		wrapper.innerHTML += `
      <div class="product-card">
        <img
          src="${imageUrl}"
          alt="${title}"
          class="product-img"
        />
        <div class="product-info">
          <div class="product-title">${title}</div>
          <div class="product-price">${price} تومان</div>
          <div class="product-meta">${priceRange} | دوربین: ${camera}</div>
          <div class="tags">${tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>
        </div>
      </div>`
	})
	chatEl.appendChild(wrapper)
	chatEl.scrollTop = chatEl.scrollHeight
}

// ─── دکمه‌های اکشن سریع ──────────────────────────────────────────

/** دکمه‌های پیشنهادی بعد از هر پاسخ را رندر می‌کند. (قبلی‌ها حذف می‌شوند) */
function renderQuickActions() {
	// حذف دکمه‌های قبلی
	document.querySelectorAll(".quick-actions").forEach((el) => el.remove())

	const wrapper = document.createElement("div")
	wrapper.className = "quick-actions"
	const actions = [
		{ q: "یه چیز ارزون‌تر نشون بده", label: "💸 ارزان‌تر" },
		{ q: "یه چیز گرون‌تر و بهتر نشون بده", label: "💎 گران‌تر" },
		{ q: "گزینهٔ بعدی رو ببین", label: "🔀 گزینهٔ بعدی" },
	]
	actions.forEach((a) => {
		const btn = document.createElement("button")
		btn.className = "action-btn"
		btn.textContent = a.label
		btn.onclick = () => {
			inputEl.value = a.q
			handleSend()
		}
		wrapper.appendChild(btn)
	})
	chatEl.appendChild(wrapper)
	chatEl.scrollTop = chatEl.scrollHeight
}

// ─── افزودن پیام ─────────────────────────────────────────────────

/**
 * یک حباب پیام به چت اضافه می‌کند.
 * @param {"user"|"ai"} role
 * @param {string}      content
 * @returns {HTMLElement} span متنی درون حباب
 */
function addMessage(role, content = "") {
	const msg = document.createElement("div")
	msg.className = `message ${role}`
	const bubble = document.createElement("div")
	bubble.className = "bubble"
	const textSpan = document.createElement("span")
	textSpan.className = "text"
	textSpan.textContent = content
	bubble.appendChild(textSpan)
	msg.appendChild(bubble)
	chatEl.appendChild(msg)
	chatEl.scrollTop = chatEl.scrollHeight
	return textSpan
}

// ─── هسته اصلی ───────────────────────────────────────────────────

let isSending = false // قفل همزمانی درخواست‌ها
let currentEventSource = null // برای بستن اتصال قبلی
let sendTimeout = null // تایمر قطع اتصال در صورت عدم دریافت نتیجه

/**
 * کوئری کاربر را از طریق SSE به بک‌اند ارسال کرده،
 * وضعیت زنده نمایش می‌دهد و پاسخ نهایی را رندر می‌کند.
 */
async function handleSend() {
	// جلوگیری از درخواست همزمان
	if (isSending) return

	const query = inputEl.value.trim()
	if (!query) return

	// بستن اتصال قبلی اگر وجود داشته باشد
	if (currentEventSource) {
		currentEventSource.close()
		currentEventSource = null
	}
	if (sendTimeout) {
		clearTimeout(sendTimeout)
		sendTimeout = null
	}

	isSending = true
	switchToChatMode()

	inputEl.value = ""
	inputEl.style.height = "auto"
	inputEl.disabled = true

	// غیرفعال کردن دکمه‌های اکشن موجود در حین ارسال
	document
		.querySelectorAll(".action-btn")
		.forEach((btn) => (btn.disabled = true))

	addMessage("user", query)

	const params = new URLSearchParams({
		query,
		top_k: "2",
		session_id: sessionId,
	})
	const es = new EventSource(`/api/v1/search/stream?${params.toString()}`)
	currentEventSource = es

	// تایم‌اوت ۳۰ ثانیه: اگر در این مدت هیچ رویدادی نیامد، اتصال بسته شود
	sendTimeout = setTimeout(() => {
		if (currentEventSource) {
			currentEventSource.close()
			currentEventSource = null
			removeStatus()
			if (isSending) {
				addMessage(
					"ai",
					"❌ زمان درخواست به پایان رسید. لطفاً دوباره تلاش کنید.",
				)
				isSending = false
				inputEl.disabled = false
				inputEl.focus()
				document
					.querySelectorAll(".action-btn")
					.forEach((btn) => (btn.disabled = false))
			}
		}
	}, 30000)

	es.addEventListener("status", (e) => {
		try {
			const { step, message } = JSON.parse(e.data)
			showStatus(STEP_MESSAGES[step] ?? message)
		} catch (err) {
			console.warn("Invalid status event data", e.data)
		}
	})

	es.addEventListener("result", (e) => {
		// بستن اتصال و پاک کردن تایمر
		es.close()
		if (currentEventSource === es) currentEventSource = null
		if (sendTimeout) clearTimeout(sendTimeout)
		removeStatus()

		let data
		try {
			data = JSON.parse(e.data)
		} catch (err) {
			addMessage("ai", "❌ پاسخ دریافتی نامعتبر است.")
			isSending = false
			inputEl.disabled = false
			inputEl.focus()
			document
				.querySelectorAll(".action-btn")
				.forEach((btn) => (btn.disabled = false))
			return
		}

		const aiTextEl = addMessage("ai")
		const aiMessage =
			data.llm_explanation || data.message || "پاسخی دریافت نشد."
		aiTextEl.textContent = aiMessage
		chatEl.scrollTop = chatEl.scrollHeight

		if (data.results?.length) renderProducts(data.results)
		renderQuickActions() // این تابع دکمه‌های قبلی را حذف می‌کند و دکمه‌های جدید می‌سازد

		if (data.session_id) {
			sessionId = data.session_id
			localStorage.setItem("nira_session", sessionId)
		}

		isSending = false
		inputEl.disabled = false
		inputEl.focus()
		document
			.querySelectorAll(".action-btn")
			.forEach((btn) => (btn.disabled = false))
	})

	es.addEventListener("error", (e) => {
		es.close()
		if (currentEventSource === es) currentEventSource = null
		if (sendTimeout) clearTimeout(sendTimeout)
		removeStatus()

		let errorMsg = "❌ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید."
		if (e.data) {
			try {
				const { message } = JSON.parse(e.data)
				if (message) errorMsg = `❌ ${message}`
			} catch (_) {
				/* ignore */
			}
		}
		addMessage("ai", errorMsg)

		isSending = false
		inputEl.disabled = false
		inputEl.focus()
		document
			.querySelectorAll(".action-btn")
			.forEach((btn) => (btn.disabled = false))
	})
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

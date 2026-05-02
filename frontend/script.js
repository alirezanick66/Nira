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

// ─── Typewriter ───────────────────────────────────────────────────

/**
 * متن را کاراکتر به کاراکتر داخل المان تایپ می‌کند.
 * @param {HTMLElement} element
 * @param {string}      text
 * @param {number}      speed
 * @returns {Promise<void>}
 */
async function typeWriter(element, text, speed = 18) {
	return new Promise((resolve) => {
		let i = 0
		const cursor = document.createElement("span")
		cursor.className = "cursor"
		element.parentNode.insertBefore(cursor, element.nextSibling)

		const interval = setInterval(() => {
			if (i < text.length) {
				element.textContent += text.charAt(i)
				i++
				chatEl.scrollTop = chatEl.scrollHeight
			} else {
				clearInterval(interval)
				cursor.remove()
				resolve()
			}
		}, speed)
	})
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
		wrapper.innerHTML += `
      <div class="product-card">
        <img
          src="${p.image_url || "https://placehold.co/300x300?text=No+Image"}"
          alt="${p.title}"
          class="product-img"
        />
        <div class="product-info">
          <div class="product-title">${p.title}</div>
          <div class="product-price">${Number(p.price).toLocaleString("fa-IR")} تومان</div>
          <div class="product-meta">${p.price_range} | دوربین: ${p.camera_quality}</div>
          <div class="tags">${p.tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>
        </div>
      </div>`
	})
	chatEl.appendChild(wrapper)
	chatEl.scrollTop = chatEl.scrollHeight
}

// ─── دکمه‌های اکشن سریع ──────────────────────────────────────────

/** دکمه‌های پیشنهادی بعد از هر پاسخ را رندر می‌کند. */
function renderQuickActions() {
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

/**
 * کوئری کاربر را از طریق SSE به بک‌اند ارسال کرده،
 * وضعیت زنده نمایش می‌دهد و پاسخ نهایی را رندر می‌کند.
 */
async function handleSend() {
	const query = inputEl.value.trim()
	if (!query) return

	// اولین ارسال: تغییر layout
	switchToChatMode()

	inputEl.value = ""
	inputEl.style.height = "auto"
	inputEl.disabled = true
	addMessage("user", query)

	const params = new URLSearchParams({
		query,
		top_k: "2",
		session_id: sessionId,
	})
	const es = new EventSource(`/api/v1/search/stream?${params.toString()}`)

	es.addEventListener("status", (e) => {
		const { step, message } = JSON.parse(e.data)
		showStatus(STEP_MESSAGES[step] ?? message)
	})

	es.addEventListener("result", async (e) => {
		es.close()
		removeStatus()

		const data = JSON.parse(e.data)
		const aiTextEl = addMessage("ai")
		const text = data.llm_explanation || data.message || ""
		await typeWriter(aiTextEl, text)

		if (data.results?.length) renderProducts(data.results)
		renderQuickActions()

		if (data.session_id) {
			sessionId = data.session_id
			localStorage.setItem("nira_session", sessionId)
		}

		inputEl.disabled = false
		inputEl.focus()
	})

	es.addEventListener("error", (e) => {
		es.close()
		removeStatus()

		if (e.data) {
			const { message } = JSON.parse(e.data)
			addMessage("ai", `❌ ${message}`)
		} else {
			addMessage(
				"ai",
				"❌ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.",
			)
		}

		inputEl.disabled = false
		inputEl.focus()
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

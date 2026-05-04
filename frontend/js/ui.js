/**
 * لایه UI — رندر پیام‌ها، وضعیت، کارت‌ها و دکمه‌های اکشن
 * این ماژول هیچ وابستگی به api.js یا session.js ندارد.
 */

const chatEl = document.getElementById("chat")

// ─── اسکرول به انتها ─────────────────────────────────────────────

/**
 * بعد از paint مرورگر به انتهای چت اسکرول می‌کند.
 * استفاده از rAF تضمین می‌کند ارتفاع نهایی DOM محاسبه شده باشد.
 */
function _scrollToBottom() {
	requestAnimationFrame(() => {
		chatEl.scrollTop = chatEl.scrollHeight
	})
}

// ─── وضعیت زنده ──────────────────────────────────────────────────

/** @type {HTMLElement|null} المان status فعال در DOM */
let _activeStatusEl = null

/**
 * یک المان status جدید می‌سازد یا متن المان موجود را به‌روز می‌کند.
 * @param {string} text
 */
export function showStatus(text) {
	if (!_activeStatusEl) {
		_activeStatusEl = document.createElement("div")
		_activeStatusEl.className = "status active"
		chatEl.appendChild(_activeStatusEl)
	}
	_activeStatusEl.textContent = text
	_scrollToBottom()
}

/** المان status فعال را از DOM حذف می‌کند. */
export function removeStatus() {
	if (_activeStatusEl) {
		_activeStatusEl.remove()
		_activeStatusEl = null
	}
}

// ─── تغییر حالت welcome → chat ───────────────────────────────────

/**
 * اولین باری که کاربر سوال می‌فرستد، layout به حالت chat تبدیل می‌شود.
 */
export function switchToChatMode() {
	const body = document.body
	if (body.classList.contains("chat-mode")) return
	body.classList.remove("welcome-mode")
	body.classList.add("chat-mode")
}

// ─── افزودن پیام ─────────────────────────────────────────────────

/**
 * یک حباب پیام به چت اضافه می‌کند.
 * @param {"user"|"ai"} role
 * @param {string}      content
 * @returns {HTMLElement} span متنی درون حباب
 */
export function addMessage(role, content = "") {
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
	_scrollToBottom()
	return textSpan
}

// ─── رندر کارت‌های محصول ─────────────────────────────────────────

/**
 * حداکثر ۲ کارت محصول را رندر می‌کند.
 * @param {Array<Object>} products
 */
export function renderProducts(products) {
	if (!products?.length) return
	const wrapper = document.createElement("div")
	wrapper.className = "products"

	products.slice(0, 2).forEach((p) => {
		const title = p.title || "بدون عنوان"
		const imageUrl =
			p.image_url || "https://placehold.co/300x300?text=No+Image"
		const price = Number(p.price).toLocaleString("fa-IR") || "۰"
		const priceRange = p.price_range || "متغیر"
		const camera = p.camera_quality || "نامشخص"
		const tags = p.tags?.length ? p.tags : ["موبایل"]

		wrapper.innerHTML += `
      <div class="product-card">
        <img src="${imageUrl}" alt="${title}" class="product-img" />
        <div class="product-info">
          <div class="product-title">${title}</div>
          <div class="product-price">${price} تومان</div>
          <div class="product-meta">${priceRange} | دوربین: ${camera}</div>
          <div class="tags">${tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>
        </div>
      </div>`
	})

	chatEl.appendChild(wrapper)
	// دو rAF تو در تو: اول layout، بعد scroll — برای کارت‌هایی که با animation-delay رندر می‌شن
	requestAnimationFrame(() => {
		requestAnimationFrame(() => {
			chatEl.scrollTop = chatEl.scrollHeight
		})
	})
}

// ─── دکمه‌های اکشن سریع ──────────────────────────────────────────

/**
 * دکمه‌های پیشنهادی را رندر می‌کند.
 * نمونه‌های قبلی پیش از رندر حذف می‌شوند.
 * @param {function(string): void} onAction - callback با متن کوئری انتخاب‌شده
 */
export function renderQuickActions(onAction) {
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
		btn.onclick = () => onAction(a.q)
		wrapper.appendChild(btn)
	})

	chatEl.appendChild(wrapper)
	requestAnimationFrame(() => {
		requestAnimationFrame(() => {
			chatEl.scrollTop = chatEl.scrollHeight
		})
	})
}

// ─── فعال/غیرفعال کردن دکمه‌های اکشن ───────────────────────────

/**
 * تمام دکمه‌های اکشن موجود را فعال یا غیرفعال می‌کند.
 * @param {boolean} disabled
 */
export function setActionButtonsDisabled(disabled) {
	document
		.querySelectorAll(".action-btn")
		.forEach((btn) => (btn.disabled = disabled))
}

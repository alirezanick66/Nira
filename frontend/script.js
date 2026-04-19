window.onerror = function (message, source, lineno, colno, error) {
	fetch("/api/log-error", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			message: message,
			source: source,
			lineno: lineno,
		}),
	}).catch((e) => console.error("Failed to send log", e))
	return true
}
const chatEl = document.getElementById("chat")
const inputEl = document.getElementById("query-input")
const sendBtn = document.getElementById("send-btn")
const statusEl = document.createElement("div")
statusEl.className = "status"

// مدیریت Session
let sessionId = localStorage.getItem("nira_session") || crypto.randomUUID()
localStorage.setItem("nira_session", sessionId)

// توابع کمکی

function showStatus(text) {
	statusEl.textContent = text
	statusEl.className = "status active"
}
function hideStatus() {
	statusEl.className = "status"
}

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

function renderProducts(products) {
	if (!products.length) return
	const wrapper = document.createElement("div")
	wrapper.className = "products"
	products.slice(0, 2).forEach((p) => {
		wrapper.innerHTML += `
          <div class="product-card">
            <img src="${p.image_url || "https://placehold.co/300x300?text=No+Image"}" alt="${p.title}" class="product-img">
            <div class="product-info">
              <div class="product-title">${p.title}</div>
              <div class="product-price">${Number(p.price).toLocaleString("fa-IR")} تومان</div>
              <div style="font-size:0.8rem; color:var(--color-text-muted); margin-bottom:0.5rem">${p.price_range} | دوربین: ${p.camera_quality}</div>
              <div class="tags">${p.tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>
            </div>
          </div>`
	})
	chatEl.appendChild(wrapper)
	chatEl.scrollTop = chatEl.scrollHeight
}

function renderQuickActions(suggestion) {
	const wrapper = document.createElement("div")
	wrapper.className = "quick-actions"
	const actions = [
		{ q: "یه چیز ارزون‌تر نشون بده", label: "💸 ارزان‌تر" },
		{
			q: "یه چیز گرون‌تر و بهتر نشون بده",
			label: "💎 گران‌تر",
		},
		{ q: "گزینهٔ بعدی رو ببین", label: "🔀 گزینهٔ بعدی" },
	]
	actions.forEach((a) => {
		const btn = document.createElement("button")
		btn.className = "action-btn"
		btn.textContent = a.label
		btn.onclick = () => {
			inputEl.value = a.q
			handleSend(true)
		}
		wrapper.appendChild(btn)
	})
	chatEl.appendChild(wrapper)
	chatEl.scrollTop = chatEl.scrollHeight
}

function addMessage(role, content, isHtml = false) {
	const msg = document.createElement("div")
	msg.className = `message ${role}`
	const bubble = document.createElement("div")
	bubble.className = "bubble"

	// ✅ همیشه span متنی را می‌سازد تا typeWriter بدون خطا اجرا شود
	const textSpan = document.createElement("span")
	textSpan.className = "text"
	if (isHtml) textSpan.innerHTML = content
	else textSpan.textContent = content

	bubble.appendChild(textSpan)
	msg.appendChild(bubble)
	chatEl.appendChild(msg)
	chatEl.scrollTop = chatEl.scrollHeight
	return textSpan // ✅ مستقیماً المان متنی را برمی‌گرداند
}

async function handleSend(isQuick = false) {
	const query = inputEl.value.trim()
	if (!query) return

	inputEl.value = ""
	sendBtn.disabled = true
	addMessage("user", query)

	try {
		showStatus("⏳ در حال تحلیل NLU و استخراج فیلترها...")
		const res = await fetch("/api/v1/search", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ query, session_id: sessionId, top_k: 2 }),
		})

		if (!res.ok) throw new Error("خطای سرور")

		showStatus("🔍 بازیابی و مرتب‌سازی نتایج...")
		const data = await res.json()
		hideStatus()

		// ✅ حذف querySelector و دریافت مستقیم المان از addMessage
		const aiTextEl = addMessage("ai", "")
		await typeWriter(aiTextEl, data.llm_explanation || data.message)

		if (data.results?.length) renderProducts(data.results)
		renderQuickActions(data.next_suggestion)
	} catch (err) {
		hideStatus()
		addMessage("ai", `❌ خطا در ارتباط: ${err.message}`)
	} finally {
		sendBtn.disabled = false
		inputEl.focus()
	}
}

sendBtn.addEventListener("click", () => handleSend(false))
inputEl.addEventListener("keypress", (e) => {
	if (e.key === "Enter" && !e.shiftKey) handleSend(false)
})

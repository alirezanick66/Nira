/**
 * مدیریت Session کاربر
 * شناسه نشست را از localStorage بارگذاری یا تولید می‌کند.
 */

let _sessionId = localStorage.getItem("nira_session") || crypto.randomUUID()
localStorage.setItem("nira_session", _sessionId)

/**
 * شناسه نشست جاری را برمی‌گرداند.
 * @returns {string}
 */
export function getSessionId() {
	return _sessionId
}

/**
 * شناسه نشست را به‌روز می‌کند و در localStorage ذخیره می‌کند.
 * @param {string} id
 */
export function setSessionId(id) {
	_sessionId = id
	localStorage.setItem("nira_session", id)
}

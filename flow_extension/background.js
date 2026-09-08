// Background service worker: получает токен Flow и мгновенно отправляет в login.bat
let lastSentToken = "";

async function extractAndSendToken() {
  try {
    const cookie = await chrome.cookies.get({
      url: "https://labs.google",
      name: "__Secure-next-auth.session-token"
    });
    if (cookie && cookie.value && cookie.value.length > 20) {
      if (cookie.value === lastSentToken) {
        return;
      }
      // Отправляем токен на локальный сервер login.bat
      const resp = await fetch("http://127.0.0.1:9876/save_cookie", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: cookie.value })
      });
      if (resp.ok) {
        lastSentToken = cookie.value;
        chrome.action.setBadgeText({ text: "✔" });
        chrome.action.setBadgeBackgroundColor({ color: "#16a34a" });
      }
    }
  } catch (e) {}
}

// Слушаем сообщения от контентного скрипта
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "flow_page_loaded") {
    extractAndSendToken();
  }
});

// Слушаем изменение куков в labs.google
chrome.cookies.onChanged.addListener((changeInfo) => {
  if (changeInfo.cookie.name === "__Secure-next-auth.session-token") {
    if (!changeInfo.removed) {
      extractAndSendToken();
    }
  }
});

// Также проверяем при запуске
extractAndSendToken();

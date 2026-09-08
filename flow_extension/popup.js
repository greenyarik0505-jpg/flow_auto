document.getElementById("copyBtn").addEventListener("click", async () => {
  const statusEl = document.getElementById("status");
  statusEl.innerText = "Поиск токена...";
  statusEl.style.color = "#2563eb";
  try {
    const cookie = await chrome.cookies.get({
      url: "https://labs.google",
      name: "__Secure-next-auth.session-token"
    });
    if (cookie && cookie.value) {
      await navigator.clipboard.writeText(cookie.value);
      try {
        await fetch("http://127.0.0.1:9876/save_cookie", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: cookie.value })
        });
      } catch (e) {}
      statusEl.innerText = "✔ ТОКЕН СКОПИРОВАН И ОТПРАВЛЕН В LOGIN.BAT!";
      statusEl.style.color = "#16a34a";
    } else {
      statusEl.innerText = "[-] Токен не найден. Войдите в Google Flow на этой вкладке.";
      statusEl.style.color = "#dc2626";
    }
  } catch (err) {
    statusEl.innerText = "Ошибка: " + err.message;
    statusEl.style.color = "#dc2626";
  }
});

// Авто-клик при открытии попапа для удобства
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("copyBtn").click();
});

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
      statusEl.innerText = "✔ ТОКЕН СКОПИРОВАН! Теперь перейдите в консоль login.bat и нажмите Enter.";
      statusEl.style.color = "#16a34a";
    } else {
      statusEl.innerText = "[-] Кука Flow не найдена. Откройте flow.google.com и убедитесь, что вошли в аккаунт.";
      statusEl.style.color = "#dc2626";
    }
  } catch (err) {
    statusEl.innerText = "Ошибка: " + err.message;
    statusEl.style.color = "#dc2626";
  }
});
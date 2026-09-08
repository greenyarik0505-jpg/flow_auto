// Content script: оповещает фоновый процесс о загрузке страницы Google Flow
function notifyFlowLoaded() {
  try {
    chrome.runtime.sendMessage({ action: "flow_page_loaded", url: window.location.href });
  } catch (e) {}
}

// Запуск при загрузке и периодическая проверка
notifyFlowLoaded();
setInterval(notifyFlowLoaded, 3000);

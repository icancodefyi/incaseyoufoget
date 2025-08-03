chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url.startsWith('http')) {
    const payload = {
      type: "url_visit",
      title: tab.title,
      url: tab.url,
      timestamp: new Date().toISOString()
    };

    fetch("http://127.0.0.1:8000/log", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }
});

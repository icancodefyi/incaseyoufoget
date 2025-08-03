document.addEventListener("copy", () => {
  const copiedText = window.getSelection().toString();

  if (copiedText.length > 5) {
    const payload = {
      type: "copy_event",
      url: window.location.href,
      text: copiedText,
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

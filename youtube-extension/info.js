chrome.runtime.sendMessage({type:"status"}).then(state => {
  document.querySelector("#status").textContent = state.connected
    ? (!state.compatible ? "Update the desktop app to 1.2.0 for website blocking." :
       `Connected · ${state.blockedDomains.length} domains blocked. YouTube study check ${state.prompt ? 'on' : 'off'}.`)
    : "Desktop app not connected · Browser website rules cleared. YouTube study check stays on.";
}).catch(() => { document.querySelector("#status").textContent = "Extension unavailable. Try reloading it."; });

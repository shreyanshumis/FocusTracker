const yes = document.querySelector("#yes");
const statusText = document.querySelector("#status");
const destination = location.hash.slice(1);
async function proceed(confirmed) {
  yes.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({type: "continue", url: destination, confirmed});
    if (result.error) throw Error(result.error);
    if (result.needsConfirmation) yes.disabled = false;
  } catch {
    statusText.textContent = "Could not open the link. Reload this page and try again.";
    yes.disabled = false;
  }
}
yes.addEventListener("click", () => proceed(true));
document.querySelector("#no").addEventListener("click", () => { location.replace("about:blank"); });
(async () => {
  try {
    const state = await chrome.runtime.sendMessage({type: "status"});
    if (!state.prompt) { statusText.textContent = "YouTube is available. Opening your link…"; await proceed(false); return; }
    statusText.textContent = state.connected ? "Focus time is active. Your choice applies to this page opening." :
      "The desktop app is not connected. The study check stays on until it reconnects.";
    yes.disabled = false;
  } catch { statusText.textContent = "Connection unavailable. Reload to try again."; }
})();

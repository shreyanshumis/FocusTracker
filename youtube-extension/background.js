const domains = ["youtube.com", "youtu.be", "youtube-nocookie.com"];
function youtubeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password &&
      domains.some(d => url.hostname === d || url.hostname.endsWith("." + d));
  } catch { return false; }
}
async function installRule() {
  await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds: [1], addRules: [{
    id: 1, priority: 1,
    action: {type: "redirect", redirect: {
      regexSubstitution: chrome.runtime.getURL("gate.html") + "#\\1"
    }},
    condition: {
      regexFilter: "^(https?://([a-zA-Z0-9-]+\\.)*(youtube\\.com|youtu\\.be|youtube-nocookie\\.com)(:[0-9]+)?/.*)$",
      resourceTypes: ["main_frame"]
    }
  }]});
}
async function status() {
  try {
    const response = await fetch("http://127.0.0.1:47653/status", {
      cache: "no-store", signal: AbortSignal.timeout(1800),
      headers: {"X-Focus-Harbor-Client": "companion-1.2"}
    });
    if (!response.ok) throw Error("Connection failed");
    const state = await response.json();
    if (state.app !== "FocusHarbor" || typeof state.youtubePrompt !== "boolean") throw Error("Unexpected response");
    return {connected: true, prompt: state.youtubePrompt, compatible: state.version >= 2,
      blockedDomains: cleanDomains(state.blockedDomains)};
  } catch {
    // Stay useful when the desktop app is closed; never pretend it is connected.
    return {connected: false, prompt: true, compatible: false, blockedDomains: []};
  }
}
function cleanDomains(values) {
  if (!Array.isArray(values)) return [];
  return [...new Set(values.filter(value => typeof value === "string" && value.length <= 253 &&
    /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]+$/.test(value) &&
    !youtubeUrl("https://" + value + "/")))].slice(0, 500).sort();
}
function isBlockedUrl(value, blockedDomains) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !youtubeUrl(value) &&
      blockedDomains.some(domain => url.hostname === domain || url.hostname.endsWith("." + domain));
  } catch { return false; }
}
let syncQueue = Promise.resolve();
let appliedDomains = null;
function syncPolicy() {
  syncQueue = syncQueue.catch(() => {}).then(async () => {
    const state = await status();
    const signature = JSON.stringify(state.blockedDomains);
    if (signature !== appliedDomains) {
      const addRules = state.blockedDomains.length ? [{
        id: 2, priority: 20,
        action: {type: "redirect", redirect: {extensionPath: "/blocked.html"}},
        condition: {requestDomains: state.blockedDomains, resourceTypes: ["main_frame"]}
      }, {
        id: 3, priority: 20, action: {type: "block"},
        condition: {requestDomains: state.blockedDomains, excludedResourceTypes: ["main_frame"]}
      }] : [];
      await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds: [2, 3], addRules});
      appliedDomains = signature;
    }
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      if (Number.isInteger(tab.id) && isBlockedUrl(tab.url, state.blockedDomains)) {
        // Recheck because a user can navigate away during the asynchronous scan.
        try {
          const current = await chrome.tabs.get(tab.id);
          if (isBlockedUrl(current.url, state.blockedDomains)) {
            await chrome.tabs.update(tab.id, {url: chrome.runtime.getURL("blocked.html")});
          }
        } catch { /* A tab closed while scanning. */ }
      }
    }
    return state;
  });
  return syncQueue;
}
async function initialize() {
  await installRule();
  await chrome.alarms.create("policy-sync", {periodInMinutes: 0.5});
  await syncPolicy();
}
async function clearPass(tabId) {
  await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: [1000 + tabId]});
  await chrome.alarms.clear("pass:" + tabId);
}
async function continueToYouTube(tabId, url) {
  if (!Number.isInteger(tabId) || tabId < 0 || !youtubeUrl(url)) throw Error("Invalid YouTube destination");
  const id = 1000 + tabId;
  await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: [id], addRules: [{
    id, priority: 10, action: {type: "allow"},
    condition: {tabIds: [tabId], requestDomains: domains, resourceTypes: ["main_frame"]}
  }]});
  // Fallback removal if navigation fails without a completion event.
  await chrome.alarms.create("pass:" + tabId, {delayInMinutes: 1});
  try { await chrome.tabs.update(tabId, {url}); }
  catch (error) { await clearPass(tabId); throw error; }
}
chrome.runtime.onInstalled.addListener(() => { initialize().catch(console.error); });
chrome.runtime.onStartup.addListener(() => { initialize().catch(console.error); });
chrome.tabs.onActivated.addListener(() => { syncPolicy().catch(console.error); });
chrome.tabs.onUpdated.addListener((_id, change) => {
  if (change.url && /^https?:/.test(change.url)) syncPolicy().catch(console.error);
});
chrome.webNavigation.onCompleted.addListener(details => {
  if (details.frameId === 0 && youtubeUrl(details.url)) clearPass(details.tabId).catch(console.error);
});
chrome.webNavigation.onErrorOccurred.addListener(details => {
  if (details.frameId === 0 && youtubeUrl(details.url)) clearPass(details.tabId).catch(console.error);
});
chrome.tabs.onRemoved.addListener(tabId => { clearPass(tabId).catch(console.error); });
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "policy-sync") syncPolicy().catch(console.error);
  if (alarm.name.startsWith("pass:")) clearPass(Number(alarm.name.slice(5))).catch(console.error);
});
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL(""))) return;
  (async () => {
    if (message.type === "status") return await syncPolicy();
    if (message.type === "continue" && sender.url.startsWith(chrome.runtime.getURL("gate.html") + "#")) {
      if (message.url !== sender.url.slice(sender.url.indexOf("#") + 1)) throw Error("Destination mismatch");
      if (!message.confirmed && (await status()).prompt) return {needsConfirmation: true};
      await continueToYouTube(sender.tab.id, message.url);
      return {ok: true};
    }
    return {error: "Unknown request"};
  })().then(reply).catch(error => reply({error: error.message}));
  return true;
});

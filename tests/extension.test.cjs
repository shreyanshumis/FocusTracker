const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../youtube-extension/background.js'), 'utf8');
function harness() {
  const calls = [], events = {};
  const event = name => ({addListener: f => events[name] = f});
  const context = vm.createContext({URL, AbortSignal, console, fetch: async () => ({ok:true,json:async()=>({app:'FocusHarbor',youtubePrompt:true})}), chrome: {
    runtime: {id:'test',getURL:p=>'chrome-extension://test/'+p,onInstalled:event('install'),onStartup:event('startup'),onMessage:event('message')},
    declarativeNetRequest:{updateDynamicRules:async r=>calls.push(['dynamic',r]),updateSessionRules:async r=>calls.push(['session',r])},
    tabs:{update:async(...r)=>calls.push(['tab',...r]),query:async()=>[],get:async()=>({}),
      onRemoved:event('removed'),onActivated:event('activated'),onUpdated:event('updated')},
    webNavigation:{onCompleted:event('completed'),onErrorOccurred:event('failed')},
    alarms:{create:async()=>{},clear:async()=>{},onAlarm:event('alarm')}
  }});
  vm.runInContext(source,context);
  return {context,calls,events};
}
test('YouTube destinations exclude lookalikes and credential-bearing URLs',()=>{
  const {context}=harness();
  for(const url of ['https://youtube.com/watch?v=x','https://www.youtube.com/','https://youtu.be/x']) assert.equal(vm.runInContext(`youtubeUrl(${JSON.stringify(url)})`,context),true);
  for(const url of ['https://youtube.com.evil.com/','https://notyoutube.com/','javascript:alert(1)','https://u:p@youtube.com/']) assert.equal(vm.runInContext(`youtubeUrl(${JSON.stringify(url)})`,context),false);
});
test('Redirect captures complete YouTube link and limits itself to top-level pages',async()=>{
  const {context,calls}=harness(); await vm.runInContext('installRule()',context);
  const rule=calls[0][1].addRules[0], regex=new RegExp(rule.condition.regexFilter);
  const url='https://www.youtube.com/watch?v=abc&list=xyz';
  assert.equal(regex.exec(url)[1],url);
  assert.equal(regex.test('https://youtube.com.evil.com/'),false);
  assert.equal(rule.action.redirect.regexSubstitution,'chrome-extension://test/gate.html#\\1');
  assert.equal(rule.condition.resourceTypes.join(','),'main_frame');
});
test('Study confirmation only allows one tab and completes at the original URL',async()=>{
  const {context,calls}=harness(); await vm.runInContext('continueToYouTube(42,"https://youtu.be/example")',context);
  assert.equal(calls[0][1].addRules[0].condition.tabIds[0],42);
  assert.equal(calls[1][1],42); assert.equal(calls[1][2].url,'https://youtu.be/example');
});
test('Gate completion does not erase a newly granted navigation pass',async()=>{
  const {calls,events}=harness(); events.completed({frameId:0,tabId:42,url:'chrome-extension://test/gate.html'});
  assert.equal(calls.length,0);
  events.completed({frameId:0,tabId:42,url:'https://www.youtube.com/watch?v=x'});
  assert.equal(calls[0][1].removeRuleIds[0],1042);
});
test('Disconnected app keeps a clearly marked study prompt',async()=>{
  const {context}=harness(); context.fetch=async()=>{throw Error('offline')};
  const state=await vm.runInContext('status()',context);
  assert.equal(state.connected,false); assert.equal(state.prompt,true);
});
test('Website senders cannot request a bypass',()=>{
  const {events,calls}=harness(); events.message({type:'continue',confirmed:true},{id:'test',url:'https://youtube.com/',tab:{id:1}},()=>{});
  assert.equal(calls.length,0);
});
test('Automatic continuation cannot bypass an active focus period',async()=>{
  const {events,calls}=harness();
  const result=await new Promise(resolve=>events.message({type:'continue',url:'https://youtube.com/',confirmed:false},
    {id:'test',url:'chrome-extension://test/gate.html#https://youtube.com/',tab:{id:4}},resolve));
  assert.equal(result.needsConfirmation,true); assert.equal(calls.length,0);
});
test('Unblocked policy opens the original link without asking',async()=>{
  const {context,events,calls}=harness();
  context.fetch=async()=>({ok:true,json:async()=>({app:'FocusHarbor',youtubePrompt:false})});
  const result=await new Promise(resolve=>events.message({type:'continue',url:'https://youtube.com/',confirmed:false},
    {id:'test',url:'chrome-extension://test/gate.html#https://youtube.com/',tab:{id:4}},resolve));
  assert.equal(result.ok,true); assert.equal(calls.find(c=>c[0]==='tab')[2].url,'https://youtube.com/');
});
test('Browser policy replaces an already-open game tab without DNS or reloading',async()=>{
  const {context,calls}=harness();
  context.fetch=async()=>({ok:true,json:async()=>({app:'FocusHarbor',version:2,youtubePrompt:true,blockedDomains:['conflictnations.com']})});
  context.chrome.tabs.query=async()=>[{id:7,url:'https://www.conflictnations.com/play.php?gameID=1'}, {id:8,url:'https://example.com/'}];
  context.chrome.tabs.get=async()=>({id:7,url:'https://www.conflictnations.com/play.php?gameID=1'});
  await vm.runInContext('syncPolicy()',context);
  const rules=calls.find(c=>c[0]==='dynamic')[1].addRules;
  assert.equal(rules[0].condition.requestDomains[0],'conflictnations.com');
  assert.equal(rules[0].action.redirect.extensionPath,'/blocked.html');
  assert.equal(rules[1].action.type,'block');
  assert.equal(calls.filter(c=>c[0]==='tab').length,1);
  assert.equal(calls.find(c=>c[0]==='tab')[1],7);
});
test('Does not redirect a tab that navigated away during the scan',async()=>{
  const {context,calls}=harness();
  context.fetch=async()=>({ok:true,json:async()=>({app:'FocusHarbor',version:2,youtubePrompt:false,blockedDomains:['conflictnations.com']})});
  context.chrome.tabs.query=async()=>[{id:7,url:'https://www.conflictnations.com/'}];
  context.chrome.tabs.get=async()=>({id:7,url:'https://example.com/'});
  await vm.runInContext('syncPolicy()',context);
  assert.equal(calls.filter(c=>c[0]==='tab').length,0);
});
test('Unblock or stopped app removes browser rules',async()=>{
  const {context,calls}=harness(); context.fetch=async()=>{throw Error('offline')};
  await vm.runInContext('syncPolicy()',context);
  assert.equal(calls[0][1].addRules.length,0);
  assert.equal(calls[0][1].removeRuleIds.join(','),'2,3');
});
test('Domain matching includes subdomains without matching lookalike suffixes or YouTube',()=>{
  const {context}=harness();
  assert.equal(vm.runInContext('isBlockedUrl("https://www.conflictnations.com/play.php", ["conflictnations.com"])',context),true);
  assert.equal(vm.runInContext('isBlockedUrl("https://conflictnations.com.evil.com/", ["conflictnations.com"])',context),false);
  assert.equal(vm.runInContext('isBlockedUrl("https://youtube.com/", ["youtube.com"])',context),false);
});

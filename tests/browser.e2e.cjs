// Isolated Chromium integration test. Never uses a user's browser profile or hosts file.
// Set FOCUS_PLAYWRIGHT to playwright-core and FOCUS_CHROMIUM to its Chromium executable.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.FOCUS_PLAYWRIGHT || 'playwright-core');

(async () => {
  let policy = {app:'FocusHarbor',version:2,youtubePrompt:false,blockedDomains:[]};
  const server = http.createServer((req,res) => {
    if (req.url === '/status') {
      res.writeHead(200, {'Content-Type':'application/json','Cache-Control':'no-store'});
      res.end(JSON.stringify(policy));
    } else {
      res.writeHead(200, {'Content-Type':'text/html'});
      res.end('<html><title>Game fixture</title><body><h1>Game is running</h1></body></html>');
    }
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port;
  const base=require('node:os').tmpdir();
  const runDir=fs.mkdtempSync(path.join(base,'browser-test-'));
  const extension=path.join(runDir,'extension');
  fs.cpSync(path.resolve(__dirname,'../youtube-extension'),extension,{recursive:true});
  const workerFile=path.join(extension,'background.js');
  fs.writeFileSync(workerFile,fs.readFileSync(workerFile,'utf8').replace('127.0.0.1:47653','127.0.0.1:'+port));
  let context;
  try {
    context=await chromium.launchPersistentContext(path.join(runDir,'profile'),{
      executablePath:process.env.FOCUS_CHROMIUM, channel:'chromium', headless:true,
      args:[`--disable-extensions-except=${extension}`,`--load-extension=${extension}`,
        '--host-resolver-rules=MAP focus-game.test 127.0.0.1','--no-proxy-server'],
    });
    const worker=context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    await worker.evaluate(async()=>{ await initialize(); });
    const id=new URL(worker.url()).host;
    const page=await context.newPage();
    const game=`http://focus-game.test:${port}/play.php?gameID=1`;
    await page.goto(game);
    assert.equal(await page.locator('h1').innerText(),'Game is running');
    policy={...policy,blockedDomains:['focus-game.test']};
    await worker.evaluate(async()=>{ await syncPolicy(); });
    await page.waitForURL(`chrome-extension://${id}/blocked.html`);
    assert.match(await page.locator('h1').innerText(),/on pause/);
    console.log('PASS: already-open game replaced by blocked screen.');
    await page.goto(game).catch(()=>{});
    await page.waitForURL(`chrome-extension://${id}/blocked.html`);
    console.log('PASS: fresh navigation intercepted by real browser request rules.');
    policy={...policy,blockedDomains:[]};
    await worker.evaluate(async()=>{ await syncPolicy(); });
    await page.goto(game);
    assert.equal(await page.locator('h1').innerText(),'Game is running');
    console.log('PASS: unblocking restores access.');
    policy={...policy,blockedDomains:['focus-game.test']};
    // Exercise the real alarm, not a direct test call, for an existing game tab.
    await page.waitForURL(`chrome-extension://${id}/blocked.html`,{timeout:45000});
    console.log('PASS: periodic browser alarm applies new focus state to an open tab.');
    policy={...policy,blockedDomains:[],youtubePrompt:true};
    await worker.evaluate(async()=>{ await syncPolicy(); });
    await context.route('https://www.youtube.com/**',route=>route.fulfill({contentType:'text/html',body:'<h1>Study video fixture</h1>'}));
    await page.goto('https://www.youtube.com/watch?v=study-test').catch(()=>{});
    await page.waitForURL(url=>url.protocol==='chrome-extension:' && url.pathname==='/gate.html');
    await page.getByRole('button',{name:'Yes, it’s for studies'}).click();
    await page.waitForURL('https://www.youtube.com/watch?v=study-test');
    assert.equal(await page.locator('h1').innerText(),'Study video fixture');
    console.log('PASS: YouTube prompt grants the original study link.');
    await page.goto('https://www.youtube.com/watch?v=another-test').catch(()=>{});
    await page.waitForURL(url=>url.protocol==='chrome-extension:' && url.pathname==='/gate.html');
    await page.getByRole('button',{name:'No, back to focus'}).click();
    await page.waitForURL('about:blank');
    console.log('PASS: declining YouTube leaves it closed.');
    console.log('Browser integration checks passed.');
  } finally {
    if (context) await context.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});

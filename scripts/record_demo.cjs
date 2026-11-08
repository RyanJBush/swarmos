/* Optional presentation tooling: npm install playwright, then install Chromium.
   Usage: node scripts/record_demo.cjs PATH_TO_PYTHON
   Produces an evidence-backed, captioned browser recording with 150 seconds of scene holds. */
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = process.cwd(), python = path.resolve(process.argv[2]);
const media = path.join(root, 'docs', 'media');
fs.mkdirSync(media, {recursive:true});
const project = `recorded-demo-${Date.now()}`;
const run = (...args) => execFileSync(python, ['-m','swarmos',...args], {cwd:root,encoding:'utf8',timeout:90000});
const firstText = run('demo','--project',project,'--memory','on','--output','evidence/recording');
const secondText = run('demo','--project',project,'--memory','on','--output','evidence/recording');
const firstId = firstText.match(/Run ID: ([\w-]+)/)[1], secondId = secondText.match(/Run ID: ([\w-]+)/)[1];
const evaluationText = run('evaluate','--trials','3','--output','evidence/recording');
const reportPath = evaluationText.split('Report: ')[1].trim();
const report = JSON.parse(fs.readFileSync(reportPath,'utf8'));
const first = JSON.parse(fs.readFileSync(path.join(root,'evidence/recording',firstId,'run-summary.json'),'utf8'));
const second = JSON.parse(fs.readFileSync(path.join(root,'evidence/recording',secondId,'run-summary.json'),'utf8'));
const verification = run('verify','--run-id',secondId,'--output','evidence/recording');
const evidence = {recorded_at:new Date().toISOString(),first_run:{run_id:firstId,completed:first.completed,memory_hit:first.memory_hit},second_run:{run_id:secondId,completed:second.completed,memory_hit:second.memory_hit},evaluation:report.summary,baseline_exit_code:report.unpatched_baseline.returncode,verification:verification.trim()};
fs.writeFileSync(path.join(media,'demo-evidence.json'),JSON.stringify(evidence,null,2)+'\n');
const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pageHtml = (kicker,title,text,body) => `<!doctype html><html><meta charset="utf-8"><style>body{margin:0;background:#101522;color:#e7edf8;font:24px system-ui;padding:64px}small{color:#8ee8ce;font-size:18px;letter-spacing:2px}h1{font-size:52px;margin:22px 0}p{color:#b9c8df;line-height:1.55;max-width:1200px}pre{font:22px/1.6 Consolas,monospace;padding:30px;background:#192238;white-space:pre-wrap;border-radius:16px}footer{position:fixed;bottom:24px;font-size:16px;color:#96a9c8}</style><small>${esc(kicker)}</small><h1>${esc(title)}</h1><p>${esc(text)}</p>${body}<footer>SwarmOS • Captured execution evidence • Fixed deterministic patch • No LLM or OS sandbox</footer></html>`;
(async()=>{
const browser = await chromium.launch({headless:true});
const still = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
await still.goto(pathToFileURL(path.join(root,'evidence/recording',secondId,'timeline.html')).href);
await still.screenshot({path:path.join(media,'timeline.png'),fullPage:true});
await still.close();
const context = await browser.newContext({viewport:{width:1440,height:900},recordVideo:{dir:path.join(root,'evidence/recording/video'),size:{width:1440,height:900}}});
const page = await context.newPage();
const scene = async (name,html,seconds)=>{await page.setContent(html); console.log(name); await page.screenshot({path:path.join(root,'evidence/recording',name.slice(0,2)+'.png')}); await page.waitForTimeout(seconds*1000);};
await scene('01 introduction',pageHtml('ENGINEERING PORTFOLIO / 01','SwarmOS: evidence before approval','A bounded Planner → Implementer → Reviewer workflow. This recording uses real local executions, not simulated test results.','<pre>One disposable repository\nOne fixed patch attempt\nTrusted acceptance test\nDurable SQLite evidence</pre>'),15);
await scene('02 first run',pageHtml('ACTUAL COMMAND OUTPUT / 02','First run: memory starts empty','The workflow still requires a real Git diff and passing acceptance evidence.','<pre>'+esc(firstText)+'</pre>'),20);
await page.goto(pathToFileURL(path.join(root,'evidence/recording',secondId,'timeline.html')).href);console.log('03 actual timeline');await page.waitForTimeout(15000);await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await page.waitForTimeout(15000);
await scene('04 repeated run',pageHtml('ACTUAL COMMAND OUTPUT / 04','Second run: advisory memory hit','The same project recalls a verified fact. It still performs all five operations and the acceptance test.','<pre>'+esc(secondText)+'</pre>'),20);
await scene('05 evaluation',pageHtml('ACTUAL PAIRED EVALUATION / 05','Memory on versus memory off','Three measured runs per arm; separate warmups. Unpatched baseline fails. This is one fixed task, not a general coding benchmark.','<pre>'+esc(Object.entries(report.summary).map(([mode,m])=>`MEMORY ${mode.toUpperCase()}\nSuccesses: ${m.successes}/${m.runs} | Memory hits: ${m.memory_hits}\nMean steps: ${m.mean_steps} | Patch attempts: ${m.patch_attempts}\nMedian execution: ${m.median_execution_ms} ms`).join('\n\n'))+'</pre>'),25);
await scene('06 verification',pageHtml('EVIDENCE INTEGRITY / 06','The database is authoritative','Exports are repairable copies. Verification compares exported bytes and hashes with the durable SQLite payload.','<pre>'+esc(verification)+'\nRun: '+esc(secondId)+'\n\nNo skipped review gates.\nNo arbitrary shell or patch tools.</pre>'),20);
await scene('07 boundaries',pageHtml('SCOPE AND NEXT STEPS / 07','A defensible bounded workflow MVP','The MCP interface exposes only inspect_run. External proposal files require exact SHA-256 approval.','<pre>Verified: transactions, traces, memory isolation, CI\n\nFixed patch, not autonomous code generation\nApplication policy, not an OS sandbox\nMemory retrieval, not proven quality improvement</pre>'),20);
const video=page.video();await context.close();await video.saveAs(path.join(media,'swarmos-demo.webm'));await browser.close();console.log('Saved docs/media/swarmos-demo.webm');
})().catch(e=>{console.error(e);process.exit(1)});

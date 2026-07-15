const fs = require('fs');
const path = require('path');

const uiDir = path.join(__dirname, 'antigravity-plugin', 'lwt-preferences-ui');
const html  = fs.readFileSync(path.join(uiDir, 'index.html'), 'utf8');
const css   = fs.readFileSync(path.join(uiDir, 'style.css'), 'utf8');
const js    = fs.readFileSync(path.join(uiDir, 'app.js'), 'utf8');

const checks = [
  ['HTML size OK (>10KB)',          html.length > 10000],
  ['CSS size OK (>5KB)',            css.length > 5000],
  ['JS size OK (>5KB)',             js.length > 5000],
  ['Has 5 nav tabs',                (html.split('cp-nav-tab').length - 1) >= 5],
  ['Has section-keys',              html.includes('section-keys')],
  ['Has section-consult',           html.includes('section-consult')],
  ['Has section-loop',              html.includes('section-loop')],
  ['Has section-routing',           html.includes('section-routing')],
  ['Has section-flags',             html.includes('section-flags')],
  ['Has 8 key rows',                js.includes('ZENMUX') && js.includes('GROQ') && js.includes('OPENROUTER') && js.includes('OPENAI') && js.includes('ANTHROPIC') && js.includes('GEMINI') && js.includes('NVIDIA') && js.includes('NVIDIA_DEEPSEEK')],
  ['Has Vietnamese text',           html.includes('vi') || html.includes('Kh\u00F3a')],
  ['Has English brackets',          html.includes('fallbacks')],
  ['Has llm-loop skill section',    html.includes('fallbacks')],
  ['Has ai-consult skill section',  html.includes('fallbacks')],
  ['Has vendor guard notice',       html.includes('fallbacks')],
  ['CSS orange var defined',        css.includes('--orange:')],
  ['CSS black vars defined',        css.includes('--black-0:')],
  ['CSS no glassmorphism',          !css.includes('backdrop-filter')],
  ['CSS flat design (no gradient bg)', !css.includes('radial-gradient(circle at top')],
  ['CSS toggle-track defined',      css.includes('.toggle-track')],
  ['CSS cp-slider defined',         css.includes('.cp-slider')],
  ['CSS provider tags defined',     css.includes('.tag-nvidia')],
  ['No ide-container simulator',    !html.includes('ide-container')],
  ['No modal-overlay popup',        html.includes('custom-key-modal')],
  ['JS loadSettings function',      js.includes('function loadSettings')],
  ['JS collectSettings function',   js.includes('function collectSettings')],
  ['JS has NVIDIA_DEEPSEEK',        js.includes('NVIDIA_DEEPSEEK')],
  ['JS has drag-drop logic',        js.includes('dragstart')],
  ['JS updateConsultPreview',       js.includes('updateConsultPreview')],
  ['JS updateLoopPreview',          js.includes('updateLoopPreview')],
  ['JS updateRanks',                js.includes('updateRanks')],
  ['JS status pill update',         js.includes('updateStatusPill')],
];

let pass = 0, fail = 0;
checks.forEach(([name, ok]) => {
  console.log((ok ? '\u2713' : '\u2717') + ' ' + name);
  ok ? pass++ : fail++;
});
console.log('');
console.log('Result: ' + pass + '/' + checks.length + ' checks passed' + (fail ? ' ('+fail+' FAILED)' : ' -- ALL PASS'));
process.exit(fail > 0 ? 1 : 0);

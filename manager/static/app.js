'use strict';
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
let status = null;
let currentTab = 'overview';
let pairTimer = null;
let lastPair = null;

function toast(msg, ms = 3000) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove('show'), ms);
}

async function api(path, opts = {}) {
  const init = {method: opts.method || 'GET', headers: {'X-Lang': LANG}};
  if (opts.body instanceof FormData) init.body = opts.body;
  else if (opts.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  const r = await fetch(path, init);
  if (r.status === 401) { location.href = '/login'; throw new Error('401'); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

async function act(btn, fn, okMsg) {
  if (btn) btn.disabled = true;
  try {
    const res = await fn();
    if (okMsg) toast(okMsg);
    await refresh();
    return res;
  } catch (e) {
    toast(e.message, 6000);
    return null;
  } finally {
    if (btn) btn.disabled = false;
  }
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmtTime = (ts) => ts ? new Date(ts * 1000).toLocaleString(LANG === 'en' ? 'en-US' : 'zh-CN') : T('ov.never');
const stateText = (s) => T(`state.${s || 'UNKNOWN'}`);

// ------------------------------------------------------------- 语言
$('#langBox').innerHTML = langSwitcherHtml();
$('#langSel').addEventListener('change', (e) => {
  setLang(e.target.value);
  api('/api/settings/language', {method: 'PUT', body: {language: LANG}}).catch(() => {});
  rerender();
});

function rerender() {
  applyI18n();
  if (!status) return;
  renderOverview();
  renderAndroid();
  if (currentTab === 'login') { if (lastPair && pairTimer) renderPair(lastPair); else loadPair(); }
  if (currentTab === 'config' && cfgSchema) loadConfig();
  if (currentTab === 'update') loadUpdate();
  syncVnc();
}

// ------------------------------------------------------------- 标签页
$$('#nav button').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
document.addEventListener('click', (e) => {
  const go = e.target.closest('[data-go]');
  if (go) showTab(go.dataset.go);
});
function showTab(name) {
  currentTab = name;
  $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${name}`));
  if (name === 'config') loadConfig();
  if (name === 'logs') loadLogs();
  if (name === 'settings') fillSettings();
  if (name === 'login') loadPair();
  if (name === 'update') loadUpdate(true);
  syncVnc();
  if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
}

// ------------------------------------------------------------- VNC
const VNC_URL = '/novnc/vnc.html?autoconnect=1&resize=scale&reconnect=1&reconnect_delay=2000&show_dot=1&path=websockify';
function syncVnc(force) {
  const running = status && status.android.state === 'RUNNING';
  for (const id of ['vncAndroid', 'vncLogin']) {
    const box = document.getElementById(id);
    const want = running && ((id === 'vncAndroid' && currentTab === 'android') || (id === 'vncLogin' && currentTab === 'login'));
    const has = box.querySelector('iframe');
    if (want && (!has || force)) {
      box.innerHTML = `<iframe src="${VNC_URL}" allow="clipboard-read; clipboard-write"></iframe>`;
    } else if (!want) {
      const msg = running ? '' : T('an.notRunning');
      if (has || box.dataset.lang !== LANG || !box.innerHTML) {
        box.innerHTML = `<div class="vnc-empty">${msg}</div>`;
        box.dataset.lang = LANG;
      }
    }
  }
}
$$('[data-reconnect]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); syncVnc(true); }));

// ------------------------------------------------------------- 状态
async function refresh() {
  try {
    status = await api('/api/status');
  } catch (e) { return; }
  renderOverview();
  renderAndroid();
  if (currentTab === 'login' && !pairTimer && !(lastPair && lastPair.status === 'error') && loginSig() !== lastLoginSig) renderLogin();
  syncVnc();
}

let lastLoginSig = '';
function loginSig() {
  const s = status;
  return [LANG, s.whatsapp.paired, s.whatsapp.expired, s.whatsapp.jid, s.android.booted, s.android.state, s.kvm.available].join('|');
}

function card(label, dot, value, sub) {
  return `<div class="card stat" style="margin:0"><div class="label">${label}</div>
    <div class="value"><span class="dot ${dot}"></span>${value}</div><div class="sub">${sub}</div></div>`;
}

function renderOverview() {
  const s = status;
  const a = s.android;
  const androidDot = a.state === 'RUNNING' ? (a.booted ? 'ok' : 'warn') : (a.state === 'FATAL' || a.state === 'BACKOFF' ? 'bad' : '');
  const androidTxt = a.state === 'RUNNING' ? (a.booted ? T('ov.booted') : T('ov.booting')) : stateText(a.state);
  const days = s.phone.days_offline;
  const phoneDot = days == null ? '' : days < 7 ? 'ok' : days < 12 ? 'warn' : 'bad';
  const bridgeDot = s.bridge.state === 'RUNNING' ? 'ok' : (s.bridge.state === 'FATAL' || s.bridge.state === 'BACKOFF') ? 'bad' : '';
  const wa = s.whatsapp;
  const waVal = wa.paired ? T('ov.linked') : wa.expired ? T('ov.expired') : T('ov.unlinked');
  const waSub = wa.paired ? `${esc(wa.push_name || '')} ${esc(wa.jid || '')}` : wa.expired ? T('ov.expiredSub') : T('ov.needLink');
  $('#stats').innerHTML = [
    card(T('ov.bridge'), bridgeDot, stateText(s.bridge.state),
      s.config.ready ? (s.bridge.enabled ? T('ov.autorun') : T('ov.manualStop')) : T('ov.cfgMissing', {x: s.config.missing.map(loc).join(', ')})),
    card(T('ov.wa'), wa.paired ? 'ok' : 'bad', waVal, waSub),
    card(T('ov.android'), androidDot, androidTxt, s.kvm.available ? (a.keepalive_session ? T('ov.keepaliveRun') : T('ov.canClose')) : T('ov.noKvm')),
    card(T('ov.lastOnline'), phoneDot, days == null ? T('ov.never') : days < 1 ? T('ov.today') : T('ov.daysAgo', {n: Math.floor(days)}),
      (s.phone.last_online ? fmtTime(s.phone.last_online) : '') + (days != null && days > 10 ? T('ov.openSoon') : '')),
  ].join('');

  const steps = [
    {k: 's1', done: s.config.ready, go: 'config'},
    {k: 's2', done: !!(a.whatsapp_installed || wa.paired), go: 'android'},
    {k: 's3', done: wa.paired || (!!s.phone.last_online && !!a.whatsapp_installed), go: 'android'},
    {k: 's4', done: wa.paired, go: 'login'},
    {k: 's5', done: s.bridge.state === 'RUNNING', action: true},
    {k: 's6', done: wa.paired && a.state !== 'RUNNING', go: 'settings'},
  ];
  $('#steps').innerHTML = steps.map((st, i) => `<li class="${st.done ? 'done' : ''}"><span class="n">${st.done ? '✓' : i + 1}</span>
    <div><div class="t">${T(`ov.${st.k}`)}</div><div class="d">${T(`ov.${st.k}d`)}</div></div>
    <div class="act">${st.action ? bridgeButtons() : `<button class="btn" data-go="${st.go}">${T(`ov.${st.k}b`)}</button>`}</div></li>`).join('');
  $$('#steps [data-bridge]').forEach((b) => b.addEventListener('click', () =>
    act(b, () => api(`/api/bridge/${b.dataset.bridge}`, {method: 'POST'}), T('msg.done'))));
}

function bridgeButtons() {
  return status.bridge.state === 'RUNNING'
    ? `<button class="btn" data-bridge="restart">${T('btn.restart')}</button> <button class="btn danger" data-bridge="stop">${T('btn.stop')}</button>`
    : `<button class="btn primary" data-bridge="start">${T('btn.start')}</button>`;
}

// ------------------------------------------------------------- 安卓
function renderAndroid() {
  const a = status.android;
  $('#androidState').textContent = '· ' + (a.state === 'RUNNING' ? (a.booted ? T('ov.booted') : T('ov.booting')) : stateText(a.state));
  $('#androidStart').disabled = a.state === 'RUNNING' || a.state === 'STARTING' || !status.kvm.available;
  $('#androidStop').disabled = a.state !== 'RUNNING' && a.state !== 'STARTING' && a.state !== 'BACKOFF';
  $('#kvmWarn').innerHTML = status.kvm.available ? '' : `<div class="notice bad">${T('an.noKvm')}</div>`;
  if (!a.booted) $('#waAppState').textContent = T('an.appNeedBoot');
  else if (a.whatsapp_installed) {
    $('#waAppState').textContent = T('an.appInstalled', {v: a.whatsapp_version || ''}) + (a.whatsapp_updated ? ' · ' + T('an.appUpdated', {d: a.whatsapp_updated}) : '');
  } else $('#waAppState').textContent = T('an.appNotInstalled');
  const busy = status.job && status.job.status === 'running';
  $('#installWa').textContent = a.whatsapp_installed ? T('an.update') : T('an.install');
  $('#installWa').disabled = !a.booted || busy;
  $('#reinstallWa').hidden = !a.whatsapp_installed;
  $('#reinstallWa').disabled = !a.booted || busy;
  const j = status.job;
  $('#jobState').innerHTML = j ? `<span class="dot ${j.status === 'done' ? 'ok' : j.status === 'error' ? 'bad' : 'warn'}"></span>${esc(j.name)}: ${esc(loc(j.message))}` : '';
}

$('#androidStart').addEventListener('click', (e) => act(e.target, () => api('/api/android/start', {method: 'POST'}), T('an.starting')));
$('#androidStop').addEventListener('click', (e) => {
  if (confirm(T('an.confirmStop'))) act(e.target, () => api('/api/android/stop', {method: 'POST'}), T('an.stopped'));
});
$('#installWa').addEventListener('click', (e) => act(e.target, () => api('/api/android/install-whatsapp', {method: 'POST'}), T('an.jobStarted')));
$('#reinstallWa').addEventListener('click', (e) => act(e.target, () => api('/api/android/install-whatsapp?force=true', {method: 'POST'}), T('an.jobStarted')));
$('#apkFile').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append('file', f);
  toast(T('an.uploading'));
  await act(null, () => api('/api/android/upload-apk', {method: 'POST', body: fd}), T('an.uploaded'));
  e.target.value = '';
});
$$('[data-key]').forEach((b) => b.addEventListener('click', () => act(b, () => api(`/api/android/key/${b.dataset.key}`, {method: 'POST'}))));
$('#sendTextBtn').addEventListener('click', async (e) => {
  const res = await act(e.target, () => api('/api/android/text', {method: 'POST', body: {text: $('#sendText').value}}), T('an.textSent'));
  if (res) $('#sendText').value = '';
});

// ------------------------------------------------------------- WhatsApp 关联
async function loadPair() {
  clearInterval(pairTimer);
  pairTimer = null;
  const p = await api('/api/wa/pair').catch(() => null);
  lastPair = p;
  if (p && (p.running || ['success', 'error'].includes(p.status))) {
    renderPair(p);
    if (p.running) pairTimer = setInterval(pollPair, 2000);
  } else renderLogin();
}

async function pollPair() {
  const p = await api('/api/wa/pair').catch(() => null);
  if (!p) return;
  lastPair = p;
  renderPair(p);
  if (!p.running) {
    clearInterval(pairTimer);
    pairTimer = null;
    refresh();
  }
}

function renderLogin() {
  const s = status;
  const el = $('#loginPanel');
  if (!s) return;
  lastLoginSig = loginSig();
  if (s.whatsapp.paired) {
    el.innerHTML = `<h2>${T('wa.linkedTitle')}</h2>
      <p>${T('wa.account')}<b>${esc(s.whatsapp.push_name || '')}</b> <span class="muted">${esc(s.whatsapp.jid || '')}</span></p>
      <p class="muted">${T('wa.linkedDesc')}</p>
      <div class="row"><button class="btn danger" id="waLogout">${T('wa.logout')}</button>
      <button class="btn" id="waLocal">${T('wa.localOnly')}</button></div>
      <p class="muted" style="font-size:12px">${T('wa.logoutTip')}</p>`;
    $('#waLogout').addEventListener('click', async (e) => {
      if (!confirm(T('wa.confirmLogout'))) return;
      const r = await act(e.target, () => api('/api/wa/logout', {method: 'POST', body: {}}));
      if (r) { toast(r.note || T('wa.loggedOut')); renderLogin(); }
    });
    $('#waLocal').addEventListener('click', async (e) => {
      if (!confirm(T('wa.confirmLocal'))) return;
      const r = await act(e.target, () => api('/api/wa/logout', {method: 'POST', body: {local_only: true}}));
      if (r) { toast(r.note || T('wa.cleared')); renderLogin(); }
    });
    return;
  }
  // 保留用户已输入的号码和选择，避免定时刷新清空
  const prevPhone = $('#pairPhone') ? $('#pairPhone').value : '';
  const prevMode = $('[name=pmode]:checked') ? $('[name=pmode]:checked').value : 'code';
  const booted = s.android.booted;
  const canStart = s.kvm.available && s.android.state !== 'RUNNING' && s.android.state !== 'STARTING';
  el.innerHTML = `<h2>${T('wa.title')}</h2>
    ${s.whatsapp.expired ? `<div class="notice bad">${T('wa.expired')}</div>` : ''}
    ${booted ? '' : `<div class="notice">${T('wa.needBoot')}
       ${canStart ? `<div style="margin-top:8px"><button class="btn primary" id="pairBoot">${T('wa.startAndroid')}</button></div>` : ''}</div>`}
    <div class="field bool" style="margin:8px 0"><label><input type="radio" name="pmode" value="code"> ${T('wa.modeCode')}</label></div>
    <div id="phoneRow"><input type="text" id="pairPhone" placeholder="${esc(T('wa.phonePh'))}"></div>
    <div class="field bool" style="margin:8px 0"><label><input type="radio" name="pmode" value="qr"> ${T('wa.modeQr')}</label></div>
    <p class="muted" style="font-size:12px;margin:0 0 0 26px">${T('wa.qrNote')}</p>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="pairStart">${T('wa.start')}</button></div>
    <p class="muted" style="font-size:12px">${T('wa.pauseNote')}</p>`;
  $('#pairPhone').value = prevPhone;
  $(`[name=pmode][value=${prevMode}]`).checked = true;
  $('#phoneRow').hidden = prevMode !== 'code';
  $$('[name=pmode]').forEach((r) => r.addEventListener('change', () => { $('#phoneRow').hidden = $('[name=pmode]:checked').value !== 'code'; }));
  const boot = $('#pairBoot');
  if (boot) boot.addEventListener('click', () => act(boot, () => api('/api/android/start', {method: 'POST'}), T('an.starting')));
  $('#pairStart').addEventListener('click', async (e) => {
    const mode = $('[name=pmode]:checked').value;
    const res = await act(e.target, () => api('/api/wa/pair', {method: 'POST', body: {mode, phone: $('#pairPhone').value}}));
    if (res) loadPair();
  });
}

function renderPair(p) {
  const el = $('#loginPanel');
  let body = '';
  if (p.status === 'starting') body = `<p>${T('wa.connecting')}</p>`;
  if (p.status === 'waiting' && p.code) {
    body = `<p>${T('wa.code')}</p><div class="paircode">${esc(p.code)}</div>
      <ol class="howto"><li>${T('wa.c1')}</li><li>${T('wa.c2')}</li><li>${T('wa.c3')}</li></ol>`;
  } else if (p.status === 'waiting' && p.qr_svg) {
    body = `<img class="qr" src="${p.qr_svg}" alt="QR"><p class="muted" style="text-align:center">${T('wa.qrLeft', {n: p.qr_remaining})}</p>
      <ol class="howto"><li>${T('wa.q1')}</li><li>${T('wa.q2')}</li></ol>`;
  }
  if (p.status === 'finishing') body = `<p>${T('wa.finishing')}</p>`;
  if (p.status === 'success') body = `<p>${T('wa.success', {jid: esc(p.jid || '')})}</p><p class="muted">${T('wa.successDesc')}</p>`;
  if (p.status === 'error') body = `<div class="notice bad">${esc(loc(p.error))}</div><p class="muted">${T('wa.errHint')}</p>`;
  el.innerHTML = `<h2>${T('wa.pairTitle')}</h2>${body}<div class="row" style="margin-top:12px">${p.running
    ? `<button class="btn danger" id="pairCancel">${T('btn.cancel')}</button>` : `<button class="btn" id="pairBack">${T('btn.back')}</button>`}</div>`;
  const c = $('#pairCancel');
  if (c) c.addEventListener('click', async () => { await act(c, () => api('/api/wa/pair/cancel', {method: 'POST'})); loadPair(); });
  const b = $('#pairBack');
  if (b) b.addEventListener('click', async () => { await api('/api/wa/pair/cancel', {method: 'POST'}); lastPair = null; await refresh(); loadPair(); });
}

// ------------------------------------------------------------- 配置
let cfgSchema = null;
const fLabel = (f) => (LANG === 'en' ? f.label_en : f.label) || f.label;
const fHelp = (f) => (LANG === 'en' ? f.help_en : f.help) || '';

async function loadConfig() {
  const {schema, values} = await api('/api/config');
  cfgSchema = schema;
  $('#toggleRaw').textContent = $('#rawCard').hidden ? T('cfg.raw') : T('cfg.form');
  $('#cfgForm').innerHTML = schema.map((sec) => `<div class="card"><h2>${esc(LANG === 'en' ? sec.title_en : sec.title)}</h2>${sec.fields.map((f) => fieldHtml(f, values[f.key])).join('')}</div>`).join('')
    + `<div class="card sticky-actions"><div class="row"><button class="btn primary" type="submit" data-restart="1">${T('cfg.saveRestart')}</button>
       <button class="btn" type="submit" data-restart="0">${T('cfg.saveOnly')}</button></div></div>`;
}

function fieldHtml(f, v) {
  const id = `f_${f.key.replace(/\./g, '__')}`;
  const help = fHelp(f) ? `<div class="help">${esc(fHelp(f))}</div>` : '';
  const req = f.required ? ' <span class="req">*</span>' : '';
  if (f.type === 'bool') return `<div class="field bool"><label><input type="checkbox" id="${id}" ${v ? 'checked' : ''}> ${esc(fLabel(f))}</label>${help}</div>`;
  let input;
  if (f.type === 'select') {
    input = `<select id="${id}">${f.options.map(([val, zh, en]) => `<option value="${esc(val)}" ${val === v ? 'selected' : ''}>${esc(LANG === 'en' ? en : zh)}</option>`).join('')}</select>`;
  } else if (f.type === 'list' || f.type === 'intlist') input = `<textarea id="${id}" rows="3">${esc((v || []).join('\n'))}</textarea>`;
  else if (f.type === 'int') input = `<input type="text" inputmode="numeric" id="${id}" value="${esc(v ?? '')}">`;
  else input = `<input type="${f.type === 'password' ? 'password' : 'text'}" id="${id}" value="${esc(v ?? '')}" autocomplete="off">`;
  return `<div class="field"><label for="${id}">${esc(fLabel(f))}${req}</label><div>${input}${help}</div></div>`;
}

$('#cfgForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const restart = e.submitter && e.submitter.dataset.restart === '1';
  const values = {};
  for (const sec of cfgSchema) for (const f of sec.fields) {
    const el = document.getElementById(`f_${f.key.replace(/\./g, '__')}`);
    values[f.key] = f.type === 'bool' ? el.checked : el.value;
  }
  const res = await act(e.submitter, () => api('/api/config', {method: 'PUT', body: {values, restart}}), T('msg.saved'));
  if (res && restart && !res.restarted && status.whatsapp.paired) {
    act(null, () => api('/api/bridge/start', {method: 'POST'}), T('cfg.bridgeStarted'));
  }
});

$('#toggleRaw').addEventListener('click', async () => {
  const rawCard = $('#rawCard');
  rawCard.hidden = !rawCard.hidden;
  $('#cfgForm').hidden = !rawCard.hidden;
  $('#toggleRaw').textContent = rawCard.hidden ? T('cfg.raw') : T('cfg.form');
  if (!rawCard.hidden) $('#rawYaml').value = (await api('/api/config/raw')).yaml;
  else loadConfig();
});
$('#saveRaw').addEventListener('click', (e) => act(e.target, () => api('/api/config/raw', {method: 'PUT', body: {yaml: $('#rawYaml').value}}), T('msg.saved')));

// ------------------------------------------------------------- 保活设置
function fillSettings() {
  if (!status) return;
  const {keepalive: ka, reminder: rm} = status.settings;
  const f = $('#setForm');
  f.ka_enabled.checked = ka.enabled;
  f.ka_days.value = ka.interval_days;
  f.ka_minutes.value = ka.duration_minutes;
  f.ka_update.checked = ka.auto_update !== false;
  f.rm_enabled.checked = rm.enabled;
  f.rm_days.value = rm.days;
}
$('#setForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const f = e.target;
  act(e.submitter, () => api('/api/settings', {method: 'PUT', body: {
    keepalive: {enabled: f.ka_enabled.checked, interval_days: +f.ka_days.value, duration_minutes: +f.ka_minutes.value, auto_update: f.ka_update.checked},
    reminder: {enabled: f.rm_enabled.checked, days: +f.rm_days.value},
  }}), T('msg.saved'));
});
$('#testReminder').addEventListener('click', (e) => act(e.target, () => api('/api/settings/test-reminder', {method: 'POST'}), T('set.testSent')));

// ------------------------------------------------------------- 版本更新
let updTimer = null;
function verLine(v) {
  if (!v || !Object.keys(v).length) return T('up.none');
  if (v.builtin === true && !v.source) return T('up.builtin');
  const src = v.source ? T(`up.src.${v.source}`) : '';
  const parts = [v.version && `v${String(v.version).replace(/^v/, '')}`, v.ref && v.source !== 'image' ? v.ref : '', v.commit].filter(Boolean);
  return `${esc(parts.join(' · ') || '?')}<div class="sub">${esc(src)}${v.installed_at ? ' · ' + T('up.installedAt', {d: fmtTime(v.installed_at)}) : ''}</div>`;
}

async function loadUpdate(withReleases) {
  let data;
  try { data = await api('/api/update/status'); } catch (e) { return; }
  const c = data.current;
  $('#upCurrent').innerHTML = [
    `<div class="card stat" style="margin:0"><div class="label">${T('up.current')}</div><div class="value">${verLine(c)}</div></div>`,
    `<div class="card stat" style="margin:0"><div class="label">${T('up.builtin')}</div><div class="value">${verLine(c.builtin)}</div></div>`,
    `<div class="card stat" style="margin:0"><div class="label">${T('up.prev')}</div><div class="value">${c.prev ? verLine(c.prev) : T('up.none')}</div>
      ${c.prev ? `<div style="margin-top:8px"><button class="btn" id="upRollback">${T('up.rollback')}</button></div>` : ''}</div>`,
  ].join('');
  const rb = $('#upRollback');
  if (rb) rb.addEventListener('click', () => { if (confirm(T('up.confirmRollback'))) startUpdate(rb, '/api/update/rollback', {}); });
  const j = data.job;
  const running = j.status === 'running';
  $('#upJob').innerHTML = j.message ? `<span class="dot ${j.status === 'done' ? 'ok' : j.status === 'error' ? 'bad' : 'warn'}"></span>${esc(loc(j.message))}
    · <a href="#" data-loglink="update">${T('log.update')}</a>` : '';
  $$('#tab-update button.primary, #upRollback').forEach((b) => { b.disabled = running; });
  $('#upSrcBtn').disabled = running || !c.go_available;
  clearTimeout(updTimer);
  if (running && currentTab === 'update') updTimer = setTimeout(() => loadUpdate(false), 3000);
  if (withReleases) loadReleases(false);
}

async function loadReleases(refresh) {
  const sel = $('#upRelSel');
  sel.innerHTML = `<option>${T('up.relLoading')}</option>`;
  try {
    const {releases} = await api(`/api/update/releases${refresh ? '?refresh=true' : ''}`);
    sel.innerHTML = releases.map((r, i) => `<option value="${esc(r.tag)}">${esc(r.tag)}${i === 0 ? T('up.relLatest') : ''} — ${esc((r.published || '').slice(0, 10))}</option>`).join('');
  } catch (e) {
    sel.innerHTML = `<option value="">${T('up.relFail')}</option>`;
    toast(e.message, 6000);
  }
}

async function startUpdate(btn, path, body) {
  const res = await act(btn, () => api(path, {method: 'POST', body}), T('up.started'));
  if (res) loadUpdate(false);
}

$('#upRelBtn').addEventListener('click', (e) => {
  const tag = $('#upRelSel').value;
  if (tag && confirm(T('up.confirm'))) startUpdate(e.target, '/api/update/release', {tag});
});
$('#upRelRefresh').addEventListener('click', () => loadReleases(true));
$('#upSrcBtn').addEventListener('click', (e) => {
  if (confirm(T('up.confirm'))) startUpdate(e.target, '/api/update/source', {ref: $('#upRef').value.trim() || 'main'});
});
$('#upFile').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  if (confirm(T('up.confirm'))) {
    const fd = new FormData();
    fd.append('file', f);
    const res = await act(null, () => api('/api/update/upload', {method: 'POST', body: fd}), T('up.started'));
    if (res) loadUpdate(false);
  }
  e.target.value = '';
});
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-loglink]');
  if (!a) return;
  e.preventDefault();
  $('#logName').value = a.dataset.loglink;
  showTab('logs');
});

// ------------------------------------------------------------- 日志
async function loadLogs() {
  const pre = $('#logText');
  const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
  const {text} = await api(`/api/logs/${$('#logName').value}?lines=500`).catch(() => ({text: ''}));
  pre.textContent = text || T('log.empty');
  if (atBottom) pre.scrollTop = pre.scrollHeight;
}
$('#logName').addEventListener('change', loadLogs);
$('#logRefresh').addEventListener('click', loadLogs);
setInterval(() => { if (currentTab === 'logs' && $('#logAuto').checked) loadLogs(); }, 4000);

$('#logoutBtn').addEventListener('click', async () => { await api('/api/logout', {method: 'POST'}); location.href = '/login'; });

// ------------------------------------------------------------- 启动
applyI18n();
api('/api/settings/language', {method: 'PUT', body: {language: LANG}}).catch(() => {});
refresh().then(() => {
  const h = location.hash.slice(1);
  if (h && document.getElementById(`tab-${h}`)) showTab(h);
});
window.addEventListener('hashchange', () => {
  const h = location.hash.slice(1);
  if (h !== currentTab && document.getElementById(`tab-${h}`)) showTab(h);
});
setInterval(refresh, 5000);

document.getElementById('langBox').innerHTML = langSwitcherHtml();
document.getElementById('langSel').addEventListener('change', (e) => setLang(e.target.value));
applyI18n();

document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = document.getElementById('err');
  err.textContent = '';
  const r = await fetch('/api/login', {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Lang': LANG},
    body: JSON.stringify({password: document.getElementById('pw').value}),
  });
  if (r.ok) location.href = '/';
  else err.textContent = T('login.wrong');
});

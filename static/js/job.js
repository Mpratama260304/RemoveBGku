(() => {
  const page = document.querySelector('#job-page');
  if (!page) return;
  const range = document.querySelector('#comparison-range');
  const before = document.querySelector('#comparison-before');
  if (range && before) range.addEventListener('input', () => { before.style.width = `${range.value}%`; });
  if (!['queued', 'processing'].includes(page.dataset.status)) return;
  let delay = 2000; let stopped = false;
  const poll = async () => {
    if (stopped || document.hidden) { window.setTimeout(poll, delay); return; }
    try {
      const response = await fetch(page.dataset.statusUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      if (!response.ok) throw new Error('status');
      const data = await response.json();
      document.querySelector('#job-status').textContent = data.status_label;
      if (data.terminal) { stopped = true; window.location.reload(); return; }
      delay = 2000;
    } catch (_) { delay = Math.min(delay * 1.6, 12000); }
    window.setTimeout(poll, delay);
  };
  window.setTimeout(poll, delay);
  window.addEventListener('pagehide', () => { stopped = true; });
})();

(() => {
  const canvas = document.querySelector('[data-chart-table]');
  if (!canvas) return;
  const table = document.getElementById(canvas.dataset.chartTable);
  const rows = [...table.querySelectorAll('tbody tr')]
    .map((row) => {
      const cells = row.querySelectorAll('td');
      return cells.length >= 3 ? { label: cells[0].textContent, total: Number(cells[1].textContent), success: Number(cells[2].textContent) } : null;
    })
    .filter(Boolean);
  if (!rows.length) { canvas.hidden = true; return; }
  const draw = () => {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    const max = Math.max(...rows.map((row) => row.total), 1);
    const gap = 5; const barWidth = Math.max(3, (width - 28 - gap * rows.length) / rows.length);
    rows.forEach((row, index) => {
      const x = 14 + index * (barWidth + gap);
      const totalHeight = (row.total / max) * (height - 28);
      const successHeight = (row.success / max) * (height - 28);
      ctx.fillStyle = '#dfe9e4'; ctx.fillRect(x, height - 14 - totalHeight, barWidth, totalHeight);
      ctx.fillStyle = '#27ad73'; ctx.fillRect(x, height - 14 - successHeight, barWidth, successHeight);
    });
  };
  draw();
  window.addEventListener('resize', draw, { passive: true });
})();

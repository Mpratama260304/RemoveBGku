(() => {
  const shell = document.querySelector('#upload');
  const form = document.querySelector('#upload-form');
  if (!shell || !form) return;
  const input = document.querySelector('#image-input');
  const dropzone = document.querySelector('#dropzone');
  const preview = document.querySelector('#file-preview');
  const image = document.querySelector('#preview-image');
  const fileName = document.querySelector('#file-name');
  const fileSize = document.querySelector('#file-size');
  const clear = document.querySelector('#clear-file');
  const submit = document.querySelector('#submit-upload');
  const notice = document.querySelector('#upload-notice');
  const progress = document.querySelector('#upload-progress');
  const progressBar = progress.querySelector('span');
  let objectUrl = null;

  const displayFile = (file) => {
    notice.textContent = '';
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) { notice.textContent = 'Gunakan file JPG, PNG, atau WebP.'; input.value = ''; return; }
    if (file.size > Number(shell.dataset.maxBytes)) { notice.textContent = 'Ukuran file melebihi batas.'; input.value = ''; return; }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    image.src = objectUrl;
    fileName.textContent = file.name;
    fileSize.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
    dropzone.hidden = true;
    preview.hidden = false;
    submit.disabled = false;
  };
  input.addEventListener('change', () => displayFile(input.files[0]));
  ['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add('dragover'); }));
  ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove('dragover'); }));
  dropzone.addEventListener('drop', (event) => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; displayFile(file);
  });
  clear.addEventListener('click', () => { input.value = ''; preview.hidden = true; dropzone.hidden = false; submit.disabled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!input.files[0] || submit.disabled) return;
    const xhr = new XMLHttpRequest();
    xhr.open('POST', shell.dataset.uploadUrl);
    xhr.setRequestHeader('X-CSRFToken', form.querySelector('[name=csrfmiddlewaretoken]').value);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.addEventListener('progress', (e) => { if (e.lengthComputable) progressBar.style.width = `${Math.round(e.loaded / e.total * 100)}%`; });
    xhr.addEventListener('load', () => {
      let data = {}; try { data = JSON.parse(xhr.responseText); } catch (_) { data.error = 'Respons server tidak valid.'; }
      if (xhr.status === 202) { window.location.assign(data.job_url); return; }
      notice.textContent = data.error || 'Unggahan gagal. Silakan coba lagi.';
      submit.disabled = false; submit.textContent = 'Hapus Background →'; progress.hidden = true;
    });
    xhr.addEventListener('error', () => { notice.textContent = 'Koneksi terputus. Periksa internet lalu coba lagi.'; submit.disabled = false; progress.hidden = true; });
    submit.disabled = true; submit.textContent = 'Mengunggah…'; progress.hidden = false; progressBar.style.width = '0%'; notice.textContent = '';
    xhr.send(new FormData(form));
  });
})();

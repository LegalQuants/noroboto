// Wait for the Superdoc UMD bundle to register the global, then mount.
let superdoc = null;

async function fetchDocBlob() {
  const res = await fetch(`/current-doc?t=${Date.now()}`);
  if (!res.ok) throw new Error(`current-doc failed: ${res.status}`);
  return await res.blob();
}

async function mountSuperdoc() {
  const SuperDocCtor = window.SuperDoc?.SuperDoc ?? window.SuperDoc;
  if (typeof SuperDocCtor !== 'function') {
    console.error('SuperDoc global not available', window.SuperDoc);
    return;
  }
  // Tear down a prior instance if present so re-mounts pick up the new file.
  if (superdoc?.destroy) {
    try { superdoc.destroy(); } catch (e) { /* ignore */ }
  }
  document.getElementById('superdoc').innerHTML = '';
  document.getElementById('superdoc-toolbar').innerHTML = '';

  const blob = await fetchDocBlob();
  const file = new File([blob], 'current.docx', { type: blob.type });

  superdoc = new SuperDocCtor({
    selector: '#superdoc',
    toolbar: '#superdoc-toolbar',
    document: file,
    documentMode: 'editing',
  });
}

function getSelectedText() {
  // Superdoc is ProseMirror/Tiptap-based; the active editor state holds the selection.
  const editor = superdoc?.activeEditor ?? superdoc?.getInstance?.()?.activeEditor;
  if (editor?.state?.selection) {
    const { from, to } = editor.state.selection;
    if (from !== to) {
      return editor.state.doc.textBetween(from, to, ' ');
    }
  }
  return (window.getSelection()?.toString() ?? '').trim();
}

function wireButtons() {
  document.getElementById('btn-show').addEventListener('click', () => {
    const text = getSelectedText();
    alert(text || '(no selection)');
  });

  document.getElementById('btn-inject').addEventListener('click', async () => {
    const selected = getSelectedText();
    const res = await fetch('/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selected_text: selected }),
    });
    if (!res.ok) {
      alert(`Injection failed: ${res.status}`);
      return;
    }
    const data = await res.json();
    await mountSuperdoc();
    const banner = data.banner ?? '❌ YOU HAVE BEEN HACKED ❌';
    alert(`${selected || '(no selection)'}\n\n${banner}`);
  });
}

function wireDropzone() {
  const zone = document.getElementById('dropzone');
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('hover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('hover'));
  zone.addEventListener('drop', async (e) => {
    e.preventDefault();
    zone.classList.remove('hover');
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.docx')) {
      alert('Only .docx files are accepted.');
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      alert(`Upload failed: ${res.status}`);
      return;
    }
    await mountSuperdoc();
  });
}

async function boot() {
  // The Superdoc UMD script is type=module and loads async; poll briefly.
  for (let i = 0; i < 50 && !window.SuperDoc; i++) {
    await new Promise((r) => setTimeout(r, 100));
  }
  wireButtons();
  wireDropzone();
  await mountSuperdoc();
}

boot();

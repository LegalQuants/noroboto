// Self-hosted Superdoc bundle (see scripts/build-vendor.mjs). Vendoring it
// eliminates the CDN flakiness we hit with esm.sh and jsdelivr: missing
// transitive deps, semver-range URL fetch failures, and Vue duplication in
// `?bundle` mode. Rebuild with `npm run build:vendor` after bumping the
// superdoc dep.
import { SuperDoc } from '/static/vendor/superdoc.mjs';

let superdoc = null;

async function fetchDocBlob() {
  const res = await fetch(`/current-doc?t=${Date.now()}`);
  if (!res.ok) throw new Error(`current-doc failed: ${res.status}`);
  return await res.blob();
}

async function mountSuperdoc() {
  // Tear down a prior instance if present so re-mounts pick up the new file.
  if (superdoc?.destroy) {
    try { superdoc.destroy(); } catch (e) { /* ignore */ }
  }
  document.getElementById('superdoc').innerHTML = '';
  document.getElementById('superdoc-toolbar').innerHTML = '';

  const blob = await fetchDocBlob();
  const file = new File([blob], 'current.docx', { type: blob.type });

  superdoc = new SuperDoc({
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
    renderProof(data);
    const banner = data.banner ?? '❌ YOU HAVE BEEN HACKED ❌';
    alert(`${selected || '(no selection)'}\n\n${banner}`);
  });
}

function renderProof(data) {
  const panel = document.getElementById('proof');
  document.getElementById('proof-text').textContent = data.extracted_text ?? '';
  document.getElementById('proof-xml').textContent = data.injected_xml ?? '';
  // Cache-bust the download link so a fresh injection isn't masked by the
  // browser's cached copy from a prior click.
  const link = document.getElementById('proof-download');
  link.href = `${data.download_url ?? '/payload-added'}?t=${Date.now()}`;
  panel.hidden = false;
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  wireButtons();
  wireDropzone();
  await mountSuperdoc();
}

boot();

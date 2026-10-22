let bridge = null;
let operationRunning = false;
const $ = (id) => document.getElementById(id);
let toastTimer;

function notify(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 5000);
}

function show(page) {
  for (const id of ['home', 'settings']) $(id).classList.toggle('active', id === page);
}

function tab(name) {
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(el => el.classList.toggle('active', el.id === `${name}-panel`));
}

function setState(raw) {
  const result = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!result.ok) {
    $('instance-line').textContent = result.error;
    $('instance-badge').textContent = 'ERROR';
    $('instance-badge').classList.add('error');
    return;
  }
  const state = result.state;
  $('account-label').textContent = state.account || 'Cuenta';
  $('account-detail').textContent = state.account
    ? `Sesión guardada para ${state.account}. Se actualizará antes de iniciar Minecraft.`
    : 'Inicia sesión con Microsoft para jugar. El launcher comprobará tu licencia de Minecraft.';
  $('memory-label').textContent = `${Math.round(state.memoryMb / 1024 * 10) / 10} GiB`;
  $('manifest-source').textContent = state.localManifest
    ? 'Pack local preparado. Cuando tengas hosting, coloca su URL HTTPS en launcher-config.json.'
    : state.packConfigured
      ? 'El launcher descarga y verifica los archivos desde tu hosting antes de iniciar Minecraft.'
      : 'Falta la URL HTTPS del pack en launcher-config.json.';
  if (!state.packConfigured) {
    $('instance-line').textContent = 'Falta configurar el servidor de archivos del pack.';
    $('instance-badge').textContent = 'CONFIGURAR';
    $('instance-badge').classList.add('error');
  } else {
    $('instance-line').textContent = 'Minecraft 1.20.1 · Forge 47.4.20 · 133 mods';
    $('instance-badge').textContent = state.installed ? 'INSTALADO' : 'LISTO PARA INSTALAR';
    $('instance-badge').classList.remove('error');
  }
}

function setBusy(busy) {
  operationRunning = busy;
  $('play-button').disabled = busy;
  $('login-button').disabled = busy;
  $('update-button').disabled = busy;
  if (!busy) $('download-status').classList.remove('visible');
}

function handleEvent(raw) {
  const event = JSON.parse(raw);
  if (event.type === 'status') {
    $('download-status').classList.add('visible');
    $('download-text').textContent = event.text;
  } else if (event.type === 'progress') {
    $('download-progress').max = Math.max(event.max || 1, 1);
    $('download-progress').value = event.value || 0;
  } else if (event.type === 'error') {
    notify(event.text);
    setBusy(false);
  } else if (event.type === 'done') {
    notify(event.action === 'play' ? 'Minecraft está iniciando.' : 'Operación completada.');
    setBusy(false);
  } else if (event.type === 'state') {
    setState({ok: true, state: event.state});
  }
}

function start(method) {
  if (!bridge || operationRunning) return;
  bridge[method](raw => {
    const result = JSON.parse(raw);
    if (!result.ok) notify(result.error);
    else {
      setBusy(true);
      $('download-text').textContent = 'Preparando…';
      $('download-progress').value = 0;
      $('download-status').classList.add('visible');
    }
  });
}

document.querySelectorAll('.tab').forEach(el => el.addEventListener('click', () => tab(el.dataset.tab)));
$('settings-button').addEventListener('click', () => show('settings'));
$('account-button').addEventListener('click', () => { show('settings'); tab('accounts'); });
$('back-button').addEventListener('click', () => show('home'));
$('play-button').addEventListener('click', () => start('play'));
$('login-button').addEventListener('click', () => start('login'));
$('update-button').addEventListener('click', () => start('update'));
$('open-folder').addEventListener('click', () => {
  if (bridge) bridge.openFolder(raw => {
    const result = JSON.parse(raw);
    if (!result.ok) notify(result.error);
  });
});

const video = $('background-video');
const videoToggle = $('video-toggle');
videoToggle.checked = localStorage.getItem('playVideo') !== 'false';
if (!videoToggle.checked) video.pause();
videoToggle.addEventListener('change', () => {
  localStorage.setItem('playVideo', String(videoToggle.checked));
  if (videoToggle.checked) video.play().catch(() => {});
  else video.pause();
});

if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined') {
  new QWebChannel(qt.webChannelTransport, channel => {
    bridge = channel.objects.launcher;
    bridge.event.connect(handleEvent);
    bridge.getState(setState);
  });
} else {
  $('instance-line').textContent = 'Abre esta interfaz desde la aplicación de escritorio.';
  $('instance-badge').textContent = 'VISTA PREVIA';
}

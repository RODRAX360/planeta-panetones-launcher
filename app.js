let bridge = null;
let operationRunning = false;
const $ = (id) => document.getElementById(id);
let toastTimer;

function setAvatar(element, url, letter) {
  element.textContent = url ? '' : (letter || 'P').charAt(0).toUpperCase();
  element.style.backgroundImage = url ? `url("${url}")` : '';
  element.classList.toggle('has-skin', !!url);
}

function renderProfiles(state) {
  const list = $('profile-list');
  list.replaceChildren();
  const profiles = [{id: 'microsoft', label: state.microsoftAccount || 'Cuenta Microsoft', type: 'Microsoft'},
    ...(state.localProfiles || []).map(name => ({id: `local:${name}`, label: name, type: 'Local'}))];
  for (const profile of profiles) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'profile-option' + (state.selectedProfile === profile.id ? ' selected' : '');
    button.textContent = `${profile.label} · ${profile.type}`;
    button.addEventListener('click', () => bridge?.selectProfile(profile.id, applyResult));
    list.append(button);
  }
}

function applyResult(raw) {
  const result = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!result.ok) notify(result.error);
  else setState(result);
}

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
  setAvatar($('account-avatar'), state.avatar, state.account);
  setAvatar($('skin-avatar'), state.avatar, state.account);
  $('account-detail').textContent = state.microsoftAccount
    ? `Cuenta Microsoft conectada: ${state.microsoftAccount}. ${state.accountType === 'local' ? 'Ahora tienes seleccionado un perfil local.' : 'La sesión se actualizará antes de jugar.'}`
    : 'Inicia sesión con Microsoft para jugar en servidores con autenticación. También puedes crear un perfil local.';
  renderProfiles(state);
  $('skin-card').hidden = state.accountType !== 'local';
  $('skin-detail').textContent = state.localSkinSet
    ? `Skin local de ${state.account} guardada en este equipo.`
    : `Elige una skin PNG para ${state.account}.`;
  $('memory-label').textContent = `${Math.round(state.memoryMb / 1024 * 10) / 10} GiB`;
  $('mod-count').textContent = state.modCount || '—';
  $('discord-detail').textContent = state.discordConfigured
    ? 'Discord mostrará Planeta Panetones Launcher cuando su aplicación de escritorio esté abierta.'
    : 'Falta el Application ID de Discord. El estado se activará cuando se configure.';
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
    $('instance-line').textContent = `Minecraft 1.20.1 · Forge 47.4.20 · ${state.modCount || '—'} mods`;
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
$('create-local').addEventListener('click', () => {
  if (!bridge) return;
  bridge.createLocalProfile($('local-name').value, raw => {
    applyResult(raw);
    if (JSON.parse(raw).ok) $('local-name').value = '';
  });
});
$('local-name').addEventListener('keydown', event => { if (event.key === 'Enter') $('create-local').click(); });
$('choose-skin').addEventListener('click', () => bridge?.chooseLocalSkin(applyResult));
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

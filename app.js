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
  if (page === 'settings') document.querySelector('.settings-content').scrollTop = 0;
}

function tab(name) {
  document.querySelector('.settings-content').scrollTop = 0;
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(el => el.classList.toggle('active', el.id === `${name}-panel`));
}

function renderServer(status) {
  const text = $('instance-line');
  const light = $('server-light');
  const players = $('server-players');
  const latency = $('server-latency');
  light.className = 'server-light';
  text.className = '';
  if (!status?.configured) {
    text.textContent = 'Servidor próximamente';
    light.classList.add('pending');
    text.classList.add('pending');
    players.textContent = '—';
    latency.textContent = 'Ping —';
    $('server-detail').textContent = 'La dirección pública todavía no está disponible. Cuando exista, se podrá configurar para mostrar estado, jugadores y ping reales.';
  } else if (!status.online) {
    text.textContent = 'Apagado';
    light.classList.add('offline');
    text.classList.add('offline');
    players.textContent = '0';
    latency.textContent = 'Ping —';
    $('server-detail').textContent = 'El servidor configurado no responde a la consulta de Minecraft.';
  } else {
    text.textContent = 'En línea';
    light.classList.add('online');
    text.classList.add('online');
    players.textContent = `${status.players ?? 0}/${status.maximum ?? '—'}`;
    latency.textContent = `Ping ${status.latencyMs} ms`;
    $('server-detail').textContent = `${status.players ?? 0} jugadores conectados · ping ${status.latencyMs} ms.`;
  }
}

function setState(raw) {
  const result = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!result.ok) {
    notify(result.error);
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
  renderServer(state.serverStatus);
  $('manifest-source').textContent = state.localManifest
    ? 'Pack local preparado. Cuando tengas hosting, coloca su URL HTTPS en launcher-config.json.'
    : state.packConfigured
      ? 'El launcher descarga y verifica los archivos desde tu hosting antes de iniciar Minecraft.'
      : 'Falta la URL HTTPS del pack en launcher-config.json.';
  if (!state.packConfigured) {
    $('version-label').textContent = 'Pack pendiente de publicar';
  } else {
    $('version-label').textContent = `Forge 1.20.1 · ${state.modCount || '—'} mods`;
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
  } else if (event.type === 'server') {
    renderServer(event.status);
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
  renderServer({configured: false});
}

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
  const profiles = [
    ...(state.microsoftAccounts || []).map(account => ({id: `microsoft:${account.id}`, label: account.name, type: 'Microsoft', identifier: account.id})),
    ...(state.localProfiles || []).map(name => ({id: `local:${name}`, label: name, type: 'Local'}))
  ];
  if (!profiles.length) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = 'Todavía no tienes cuentas guardadas. Añade una cuenta Microsoft o crea un perfil local.';
    list.append(empty);
  }
  for (const profile of profiles) {
    const card = document.createElement('div');
    card.className = 'profile-card' + (state.selectedProfile === profile.id ? ' selected' : '');
    const avatar = document.createElement('span');
    avatar.className = 'avatar';
    setAvatar(avatar, state.profileAvatars?.[profile.id], profile.label);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'profile-select';
    const name = document.createElement('strong');
    name.textContent = profile.label;
    const detail = document.createElement('small');
    detail.textContent = profile.identifier || (profile.type === 'Local' ? 'Perfil sin licencia verificada' : 'Cuenta Microsoft');
    button.append(name, detail);
    button.addEventListener('click', () => bridge?.selectProfile(profile.id, applyResult));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'profile-remove';
    remove.textContent = '×';
    remove.title = `Quitar ${profile.label}`;
    remove.setAttribute('aria-label', remove.title);
    remove.addEventListener('click', () => {
      if (!bridge || !confirm(`¿Quitar ${profile.label} del launcher?`)) return;
      if (profile.type === 'Microsoft') bridge.removeMicrosoftAccount(profile.id, applyResult);
      else bridge.removeLocalProfile(profile.label, applyResult);
    });
    card.append(avatar, button, remove);
    list.append(card);
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
  $('account-button').title = state.account ? `Cuenta: ${state.account}` : 'Cuenta de Minecraft';
  $('account-button').setAttribute('aria-label', $('account-button').title);
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
  $('memory-label').textContent = `${(state.memoryMb / 1024).toFixed(1)} GiB`;
  $('system-memory-label').textContent = state.systemMemoryMb ? `${(state.systemMemoryMb / 1024).toFixed(1)} GiB` : 'no detectada';
  $('memory-range').max = String(state.memoryLimitMb);
  $('memory-input').max = String(state.memoryLimitMb);
  $('memory-range').value = String(state.memoryMb);
  $('memory-input').value = String(state.memoryMb);
  $('resolution-width').value = String(state.resolutionWidth);
  $('resolution-height').value = String(state.resolutionHeight);
  $('resolution-status').textContent = state.customResolution
    ? `Se iniciará a ${state.resolutionWidth} × ${state.resolutionHeight} píxeles.`
    : 'Se usa la resolución predeterminada.';
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
}

function setBusy(busy) {
  operationRunning = busy;
  document.querySelector('.bottom-bar').classList.toggle('busy', busy);
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
$('memory-range').addEventListener('input', () => { $('memory-input').value = $('memory-range').value; });
$('memory-input').addEventListener('input', () => {
  const value = Number($('memory-input').value);
  if (Number.isFinite(value)) $('memory-range').value = String(value);
});
$('save-memory').addEventListener('click', () => {
  if (!bridge) return;
  const value = Number($('memory-input').value);
  if (!Number.isInteger(value)) return notify('Escribe una cantidad de RAM válida en MiB.');
  bridge.saveMemory(value, raw => {
    applyResult(raw);
    if (JSON.parse(raw).ok) notify('RAM guardada para el próximo inicio de Minecraft.');
  });
});
$('save-resolution').addEventListener('click', () => {
  if (!bridge) return;
  const width = Number($('resolution-width').value);
  const height = Number($('resolution-height').value);
  if (!Number.isInteger(width) || !Number.isInteger(height)) return notify('Escribe un ancho y alto válidos.');
  bridge.saveResolution(width, height, raw => {
    applyResult(raw);
    if (JSON.parse(raw).ok) notify('Resolución guardada para el próximo inicio de Minecraft.');
  });
});
$('reset-resolution').addEventListener('click', () => bridge?.resetResolution(raw => {
  applyResult(raw);
  if (JSON.parse(raw).ok) notify('Resolución predeterminada restaurada.');
}));
$('update-button').addEventListener('click', () => start('update'));
$('open-folder').addEventListener('click', () => {
  if (bridge) bridge.openFolder(raw => {
    const result = JSON.parse(raw);
    if (!result.ok) notify(result.error);
  });
});
$('open-mods-folder').addEventListener('click', () => {
  if (bridge) bridge.openModsFolder(raw => {
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

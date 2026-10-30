let bridge = null;
let currentState = null;
let operationRunning = false;
let routeInitialized = false;
let settingsReturnPage = 'instances';
let activeOperation = null;
let toastTimer = null;
let videoSourceLoaded = false;

const $ = id => document.getElementById(id);
const pages = ['auth', 'instances', 'home', 'settings'];
const video = $('background-video');
const videoToggle = $('video-toggle');

function parseResult(raw) {
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch (_error) {
    return {ok: false, error: 'El launcher devolvió una respuesta no válida.'};
  }
}

function notify(message) {
  if (!message) return;
  const toast = $('toast');
  toast.textContent = String(message);
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 5000);
}

function showLoginError(message) {
  const error = $('auth-error');
  error.textContent = String(message);
  error.hidden = false;
}

function setAvatar(element, url, name) {
  if (!element) return;
  element.textContent = url ? '' : String(name || 'P').charAt(0).toUpperCase();
  element.style.backgroundImage = url ? 'url("' + String(url).replaceAll('"', '%22') + '")' : '';
  element.classList.toggle('has-skin', Boolean(url));
}

function show(page) {
  if ((page === 'home' || page === 'instances' || page === 'settings') && !currentState?.account) {
    page = 'auth';
  }
  for (const name of pages) {
    $(name).classList.toggle('active', name === page);
  }
  document.body.dataset.page = page;
  if (page === 'settings') $('settings').querySelector('.settings-content').scrollTop = 0;
  syncVideo();
}

function openSettings(fromPage) {
  if (!currentState?.account) return show('auth');
  settingsReturnPage = fromPage;
  tab('accounts');
  show('settings');
}

function tab(name) {
  document.querySelectorAll('.tab').forEach(element => {
    element.classList.toggle('active', element.dataset.tab === name);
    element.setAttribute('aria-selected', element.dataset.tab === name ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(element => {
    element.classList.toggle('active', element.id === name + '-panel');
  });
  $('settings').querySelector('.settings-content').scrollTop = 0;
}

function renderInstances(state) {
  $('play-instance-name').textContent = state.instanceName || 'Principal';
  const grid = $('instance-grid');
  grid.replaceChildren();
  for (const item of state.instances || []) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'instance-tile ' + item.id + (item.id === state.selectedInstance ? ' selected' : '');
    button.setAttribute('aria-label', 'Elegir instancia ' + item.name);
    button.setAttribute('aria-current', item.id === state.selectedInstance ? 'true' : 'false');

    const artwork = document.createElement('span');
    artwork.className = 'instance-artwork';
    artwork.setAttribute('aria-hidden', 'true');
    const badge = document.createElement('span');
    badge.className = 'instance-badge';
    badge.textContent = item.installed ? 'INSTALADA' : 'DISPONIBLE';
    const copy = document.createElement('span');
    copy.className = 'instance-tile-copy';
    const title = document.createElement('strong');
    title.textContent = item.name;
    const description = document.createElement('small');
    description.textContent = item.description || '';
    const meta = document.createElement('span');
    meta.className = 'instance-meta';
    meta.textContent = 'Minecraft 1.20.1 · Forge' + (item.modCount ? ' · ' + item.modCount + ' mods' : '');
    const action = document.createElement('span');
    action.className = 'instance-action';
    action.textContent = 'Entrar →';
    copy.append(title, description, meta, action);
    button.append(artwork, badge, copy);
    button.addEventListener('click', () => {
      if (!bridge || operationRunning) return;
      bridge.selectInstance(item.id, raw => {
        const result = parseResult(raw);
        if (!result?.ok) return notify(result?.error || 'No se pudo elegir la instancia.');
        setState(result);
        show('home');
      });
    });
    grid.append(button);
  }
}

function renderServer(status) {
  const line = $('server-line');
  const dot = $('server-dot');
  const ping = $('server-ping');
  const address = status?.address || '';
  $('server-status').title = address;
  dot.className = 'server-light';
  if (!status?.configured) {
    line.textContent = 'Servidor próximamente';
    ping.textContent = 'Ping —';
    $('server-detail').textContent = 'La dirección del servidor todavía no está configurada.';
  } else if (!status.online) {
    line.textContent = 'Servidor sin conexión';
    dot.classList.add('offline');
    ping.textContent = 'Ping —';
    $('server-detail').textContent = address + ' · ' + (status.message || 'El servidor no responde en este momento.');
  } else {
    const players = status.players ?? 0;
    const maximum = status.maximum ?? '—';
    const latency = status.latencyMs ?? '—';
    line.textContent = players + '/' + maximum + ' jugadores';
    dot.classList.add('online');
    ping.textContent = 'Ping ' + latency + ' ms';
    $('server-detail').textContent = address + ' · ' + players + ' jugadores conectados · ping ' + latency + ' ms.';
  }
}

function renderUpdateStatus(status, state) {
  const detail = $('launcher-update-detail');
  if (status?.message) {
    detail.textContent = status.message;
  } else if (state.launcherUpdateConfigured) {
    detail.textContent = 'Versión ' + (state.launcherVersion || '—') + '. Se comprueba al iniciar.';
  } else {
    detail.textContent = 'Versión ' + (state.launcherVersion || '—') + '. No hay fuente de actualización configurada.';
  }
  const banner = $('update-banner');
  if (banner) {
    banner.hidden = status?.status !== 'available';
    if (!banner.hidden) banner.textContent = 'Versión ' + status.availableVersion + ' disponible. Actualizar launcher →';
  }
}

function renderAccount(state) {
  const account = state.account || 'Jugador';
  for (const id of ['account-avatar', 'instance-account-avatar', 'settings-avatar']) {
    setAvatar($(id), state.avatar, account);
  }
  $('account-button').setAttribute('aria-label', 'Abrir ajustes de ' + account);
  $('instance-account-button').setAttribute('aria-label', 'Abrir ajustes de ' + account);
  $('settings-account-name').textContent = account;
  $('settings-account-type').textContent = state.accountType === 'local' ? 'Perfil local no premium' : 'Cuenta Microsoft';
  $('remove-account').disabled = !state.selectedProfile;
  $('skin-card').hidden = state.accountType !== 'local';
  $('skin-detail').textContent = state.localSkinSet
    ? 'Skin local guardada para ' + account + '.'
    : 'Elige una skin PNG para ' + account + '.';
}

function renderSettings(state) {
  $('memory-range').max = String(state.memoryLimitMb || 32768);
  $('memory-input').max = String(state.memoryLimitMb || 32768);
  $('memory-range').value = String(state.memoryMb || 8192);
  $('memory-input').value = String(state.memoryMb || 8192);
  updateMemoryLabel();
  $('system-memory-label').textContent = state.systemMemoryMb
    ? (state.systemMemoryMb / 1024).toFixed(1) + ' GiB'
    : 'no detectada';
  $('resolution-enabled').checked = Boolean(state.customResolution);
  $('resolution-width').value = String(state.resolutionWidth || 854);
  $('resolution-height').value = String(state.resolutionHeight || 480);
  updateResolutionControls();
  $('manifest-source').textContent = state.localManifest
    ? 'Pack local preparado. Configura su URL HTTPS para distribuirlo.'
    : state.packConfigured
      ? 'La instancia seleccionada se verifica y descarga al pulsar Jugar.'
      : 'Falta la URL HTTPS del pack en launcher-config.json.';
  renderUpdateStatus(state.launcherUpdateStatus, state);
}

function setState(raw) {
  const result = parseResult(raw);
  if (!result?.ok || !result.state) {
    notify(result?.error || 'No se pudo leer el estado del launcher.');
    return;
  }
  const hadAccount = Boolean(currentState?.account);
  const firstState = !routeInitialized;
  currentState = result.state;
  renderInstances(currentState);
  renderAccount(currentState);
  renderSettings(currentState);
  renderServer(currentState.serverStatus);
  $('play-button').disabled = operationRunning || !currentState.account || !currentState.packConfigured;
  if (firstState) {
    routeInitialized = true;
    show(currentState.account ? 'instances' : 'auth');
  } else if (!hadAccount && currentState.account) {
    show('instances');
  } else if (hadAccount && !currentState.account) {
    show('auth');
  }
}

function setBusy(busy) {
  operationRunning = Boolean(busy);
  document.body.classList.toggle('is-launching', operationRunning && activeOperation === 'play');
  for (const id of ['play-button', 'auth-login', 'auth-fresh', 'auth-local', 'create-local', 'update-button', 'settings-save']) {
    const element = $(id);
    if (element) element.disabled = operationRunning || (id === 'play-button' && (!currentState?.account || !currentState?.packConfigured));
  }
  document.querySelectorAll('.instance-tile').forEach(element => { element.disabled = operationRunning; });
  $('play-button').textContent = operationRunning && activeOperation === 'play' ? 'Preparando…' : 'Jugar';
  if (!operationRunning) {
    activeOperation = null;
    $('download-status').classList.remove('visible', 'login');
    $('cancel-login').hidden = true;
    $('cancel-login').disabled = false;
  }
  syncVideo();
}

function openProgress(method) {
  activeOperation = method;
  const login = method === 'login' || method === 'loginFresh';
  if (login) $('auth-error').hidden = true;
  $('download-title').textContent = login
    ? method === 'loginFresh' ? 'Iniciar con otra cuenta' : 'Conectando con Microsoft'
    : method === 'play' ? (currentState?.instanceName || 'Instancia') : 'Verificando instancia';
  $('download-text').textContent = login
    ? method === 'loginFresh' ? 'Abriendo Microsoft para introducir tu correo…' : 'Abriendo Microsoft…'
    : 'Preparando archivos…';
  $('download-progress').max = 100;
  $('download-progress').value = 0;
  $('download-percent').textContent = '0%';
  $('download-status').classList.add('visible');
  $('download-status').classList.toggle('login', login);
  $('cancel-login').hidden = !login;
  setBusy(true);
}

function start(method) {
  if (!bridge) return notify('Abre el launcher de escritorio para continuar.');
  if (operationRunning) return;
  if (method === 'play' && !currentState?.account) return show('auth');
  openProgress(method);
  bridge[method](raw => {
    const result = parseResult(raw);
    if (result?.ok) return;
    if (['login', 'loginFresh'].includes(method)) showLoginError(result?.error || 'No se pudo iniciar sesión.');
    else notify(result?.error || 'No se pudo iniciar la operación.');
    setBusy(false);
  });
}

function handleEvent(raw) {
  const event = parseResult(raw);
  if (!event || typeof event !== 'object') return;
  switch (event.type) {
    case 'status':
      $('download-text').textContent = event.text || 'Preparando…';
      if (operationRunning) $('download-status').classList.add('visible');
      break;
    case 'progress': {
      const max = Math.max(Number(event.max) || 1, 1);
      const value = Math.max(0, Math.min(Number(event.value) || 0, max));
      $('download-progress').max = max;
      $('download-progress').value = value;
      $('download-percent').textContent = Math.round(100 * value / max) + '%';
      break;
    }
    case 'error':
      if (['login', 'loginFresh'].includes(activeOperation)) showLoginError(event.text || 'No se pudo iniciar sesión.');
      else notify(event.text || 'No se pudo completar la operación.');
      setBusy(false);
      break;
    case 'cancelled':
      setBusy(false);
      break;
    case 'done':
      if (event.action === 'play') notify('Minecraft está iniciando.');
      else if (event.action === 'update') notify('Instancia verificada y lista para jugar.');
      setBusy(false);
      break;
    case 'busy':
      if (event.busy && !operationRunning) openProgress('update');
      else if (!event.busy) setBusy(false);
      break;
    case 'state':
      setState({ok: true, state: event.state});
      break;
    case 'server':
      renderServer(event.status);
      break;
    case 'launcher_update_status':
      if (currentState) {
        currentState.launcherUpdateStatus = event;
        renderUpdateStatus(event, currentState);
      }
      break;
    case 'update_notice':
      notify(event.text);
      break;
    default:
      break;
  }
}

function applyResult(raw) {
  const result = parseResult(raw);
  if (!result?.ok) return notify(result?.error || 'No se pudo completar la operación.');
  if (result.state) setState(result);
}

function updateMemoryLabel() {
  const memory = Number($('memory-input').value) || 0;
  $('memory-label').textContent = (memory / 1024).toFixed(1) + ' GiB';
}

function updateResolutionControls() {
  const enabled = $('resolution-enabled').checked;
  $('resolution-width').disabled = !enabled;
  $('resolution-height').disabled = !enabled;
}

function saveSettings() {
  if (!bridge || operationRunning) return;
  const memory = Number($('memory-input').value);
  const width = Number($('resolution-width').value);
  const height = Number($('resolution-height').value);
  const limit = Number(currentState?.memoryLimitMb) || 32768;
  if (!Number.isInteger(memory) || memory < 2048 || memory > limit) {
    return notify('Elige entre 2048 y ' + limit + ' MiB de RAM.');
  }
  if (!Number.isInteger(width) || !Number.isInteger(height) ||
      width < 640 || width > 7680 || height < 360 || height > 4320) {
    return notify('Elige una resolución entre 640×360 y 7680×4320.');
  }
  const resolution = $('resolution-enabled').checked;
  $('settings-save').disabled = true;
  bridge.saveSettings(memory, width, height, resolution, raw => {
    $('settings-save').disabled = false;
    const result = parseResult(raw);
    if (!result?.ok) return notify(result?.error || 'No se pudieron guardar los ajustes.');
    localStorage.setItem('playVideo', String(videoToggle.checked));
    setState(result);
    show(settingsReturnPage);
    syncVideo();
    notify('Ajustes guardados.');
  });
}

function syncVideo() {
  const shouldPlay = videoToggle.checked && !document.hidden &&
    $('home').classList.contains('active') && !operationRunning;
  if (!shouldPlay) {
    video.pause();
    return;
  }
  if (!videoSourceLoaded) {
    video.src = 'assets/fondo.mp4';
    videoSourceLoaded = true;
  }
  video.play().catch(() => {});
}

document.querySelectorAll('.tab').forEach(element =>
  element.addEventListener('click', () => tab(element.dataset.tab))
);
$('auth-login').addEventListener('click', () => start('login'));
$('auth-fresh').addEventListener('click', () => start('loginFresh'));
$('auth-local').addEventListener('click', () => {
  $('auth-local-form').hidden = false;
  $('local-name').focus();
});
$('create-local').addEventListener('click', () => {
  if (!bridge || operationRunning) return notify('Abre el launcher de escritorio para continuar.');
  const name = $('local-name').value.trim();
  bridge.createLocalProfile(name, raw => {
    const result = parseResult(raw);
    if (!result?.ok) return notify(result?.error || 'No se pudo crear el perfil local.');
    $('local-name').value = '';
    $('auth-local-form').hidden = true;
    setState(result);
  });
});
$('local-name').addEventListener('keydown', event => {
  if (event.key === 'Enter') $('create-local').click();
});
$('cancel-login').addEventListener('click', () => {
  if (!bridge || !['login', 'loginFresh'].includes(activeOperation) || !operationRunning) return;
  $('cancel-login').disabled = true;
  $('download-text').textContent = 'Cancelando inicio de sesión…';
  bridge.cancelLogin(raw => {
    const result = parseResult(raw);
    if (!result?.ok) {
      notify(result?.error || 'No se pudo cancelar el inicio de sesión.');
      setBusy(false);
    }
  });
});
$('instance-account-button').addEventListener('click', () => openSettings('instances'));
$('account-button').addEventListener('click', () => openSettings('home'));
$('instances-home').addEventListener('click', () => show('instances'));
$('play-button').addEventListener('click', () => start('play'));
$('settings-save').addEventListener('click', saveSettings);
$('remove-account').addEventListener('click', () => {
  if (!bridge || !currentState?.selectedProfile || operationRunning) return;
  if (!confirm('¿Quitar esta cuenta del launcher?')) return;
  const selected = currentState.selectedProfile;
  if (selected.startsWith('microsoft:')) {
    bridge.removeMicrosoftAccount(selected, applyResult);
  } else if (selected.startsWith('local:')) {
    bridge.removeLocalProfile(selected.slice(6), applyResult);
  }
});
$('choose-skin').addEventListener('click', () => bridge?.chooseLocalSkin(applyResult));
$('memory-range').addEventListener('input', () => {
  $('memory-input').value = $('memory-range').value;
  updateMemoryLabel();
});
$('memory-input').addEventListener('input', () => {
  $('memory-range').value = $('memory-input').value;
  updateMemoryLabel();
});
$('resolution-enabled').addEventListener('change', updateResolutionControls);
videoToggle.checked = localStorage.getItem('playVideo') !== 'false';
videoToggle.addEventListener('change', syncVideo);
$('update-button').addEventListener('click', () => start('update'));
for (const [id, method] of [['open-folder', 'openFolder'], ['open-mods-folder', 'openModsFolder']]) {
  $(id).addEventListener('click', () => bridge?.[method](raw => {
    const result = parseResult(raw);
    if (!result?.ok) notify(result?.error || 'No se pudo abrir la carpeta.');
  }));
}
const updateBanner = $('update-banner');
if (updateBanner) {
  updateBanner.addEventListener('click', () => bridge?.installLauncherUpdate(raw => {
    const result = parseResult(raw);
    if (!result?.ok) notify(result?.error || 'No se pudo iniciar la actualización.');
  }));
}
document.addEventListener('visibilitychange', syncVideo);
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (['login', 'loginFresh'].includes(activeOperation) && operationRunning) {
    $('cancel-login').click();
  } else if (!operationRunning && $('home').classList.contains('active')) {
    show('instances');
  }
});
syncVideo();

if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined') {
  new QWebChannel(qt.webChannelTransport, channel => {
    bridge = channel.objects.launcher;
    bridge.event.connect(handleEvent);
    bridge.getState(setState);
  });
} else {
  renderServer({configured: false});
  renderUpdateStatus({status: 'unconfigured', message: 'Abre el launcher de escritorio para jugar.'}, {});
}

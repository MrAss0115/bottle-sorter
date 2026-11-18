import {getLanguage, getLocale, translatePage} from './i18n.mjs';
import {escapeHtml as esc} from './view-model.mjs';

const $ = id => document.getElementById(id);
const tr = (en, zh) => getLanguage() === 'zh' ? zh : en;
let token = '', offset = 0, total = 0, rows = [], requestId = 0, controller;
let active = {device: '', uid: '', mode: 'events', limit: 20};
let busy = false;
const time = value => new Intl.DateTimeFormat(getLocale(), {dateStyle:'medium', timeStyle:'medium'}).format(new Date(value));

function clearData() {
  controller?.abort(); requestId++; busy = false; token = ''; rows = []; total = 0; offset = 0;
  $('rewardPassword').value = '';
  $('rewardData').hidden = true; $('rewardUnlock').hidden = false;
  $('rewardHead').replaceChildren(); $('rewardBody').replaceChildren();
  $('rewardCount').textContent = ''; $('rewardStatus').textContent = '';
}

function render() {
  if (!token) return;
  const balance = active.mode === 'balances';
  const labels = balance
    ? [tr('RFID UID','RFID 卡號'), tr('Device','設備'), tr('Latest balance','最新設備餘額'), tr('Latest batch','最新批次'), tr('Received at','伺服器接收時間')]
    : [tr('RFID UID','RFID 卡號'), tr('Device','設備'), tr('Batch','批次'), tr('Earned','本次積分'), tr('Device total after batch','本批後設備累計'), tr('Bottles / cans / other','瓶／罐／其他'), tr('Received at','伺服器接收時間')];
  $('rewardHead').innerHTML = '<tr>' + labels.map(v=>`<th scope="col">${esc(v)}</th>`).join('') + '</tr>';
  $('rewardBody').innerHTML = rows.length ? rows.map(r => '<tr>' +
    `<td><code>${esc(r.uid)}</code></td><td><code>${esc(r.device)}</code></td>` +
    (balance ? `<td>${r.total}</td><td>#${r.last_batch}</td>` :
      `<td>#${r.batch}</td><td>+${r.earned}</td><td>${r.total}</td><td>${r.bottles} / ${r.cans} / ${r.rejected}</td>`) +
    `<td>${esc(time(r.received_at))}</td></tr>`).join('') :
    `<tr><td colspan="${labels.length}" class="empty-cell">${tr('No matching records yet.','暫無符合條件的記錄。')}</td></tr>`;
  $('rewardCount').textContent = tr(`${total} records`, `共 ${total} 筆`);
  $('rewardPage').textContent = tr(`Page ${Math.floor(offset / active.limit) + 1} · ${rows.length} shown`, `第 ${Math.floor(offset / active.limit) + 1} 頁 · 顯示 ${rows.length} 筆`);
  $('rewardPrev').disabled = offset === 0 || busy;
  $('rewardNext').disabled = offset + active.limit >= total || busy;
}

async function refresh() {
  if (!token) return;
  controller?.abort(); controller = new AbortController();
  const current = ++requestId;
  busy = true; render();
  const requestController = controller;
  const timeout = setTimeout(()=>requestController.abort(), 8000);
  const params = new URLSearchParams({limit:active.limit, offset});
  if (active.device) params.set('device', active.device);
  if (active.uid) params.set('uid', active.uid);
  try {
    const response = await fetch(`${active.mode === 'balances' ? '/api/reward-balances' : '/api/rewards'}?${params}`, {
      cache:'no-store', signal:controller.signal, headers:{Authorization:`Bearer ${token}`},
    });
    if (current !== requestId) return;
    if (response.status === 401) {
      clearData(); $('rewardStatus').textContent = tr('Viewing password is incorrect or has changed.','查看口令錯誤或已變更。'); return;
    }
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    if (current !== requestId) return;
    rows = data.items; total = data.total;
    $('rewardData').hidden = false; $('rewardUnlock').hidden = true;
    $('rewardPassword').value = '';
    $('rewardStatus').textContent = tr('Updated. Refreshes every 10 seconds while unlocked.','已更新。解鎖期間每 10 秒自動刷新。');
  } catch (error) {
    if (current !== requestId) return;
    $('rewardStatus').textContent = tr('Unable to refresh. Check the service and credentials; any visible records are from the previous successful refresh.', '無法刷新。請檢查服務與口令；目前顯示的記錄來自上次成功更新。');
  } finally {
    clearTimeout(timeout);
    if (current === requestId) {busy = false; render(); translatePage();}
  }
}

$('rewardUnlock').addEventListener('submit', event => {
  event.preventDefault(); token = $('rewardPassword').value.trim(); offset = 0; refresh();
});
$('rewardLock').addEventListener('click', clearData);
$('rewardFilters').addEventListener('submit', event => {
  event.preventDefault();
  active = {device:$('rewardDevice').value.trim(), uid:$('rewardUid').value.trim(), mode:$('rewardMode').value, limit:Number($('rewardLimit').value)};
  offset = 0; refresh();
});
$('rewardPrev').addEventListener('click', ()=>{offset = Math.max(0, offset-active.limit); refresh();});
$('rewardNext').addEventListener('click', ()=>{offset += active.limit; refresh();});
$('languageToggle').addEventListener('click', ()=>{render(); translatePage();});
const timer = setInterval(()=>{if(token && !busy && !$('rewardData').hidden && !document.hidden) refresh();},10000);
window.addEventListener('pagehide', ()=>{clearInterval(timer); clearData();});
translatePage();

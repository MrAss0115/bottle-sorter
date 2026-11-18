// Presentation-only translations. API values, identifiers and original JSON stay unchanged.
const translations = {
  'BottleScope — Collection Monitor': 'BottleScope — 收集監測',
  'Skip to monitoring': '跳轉到監測內容', 'BottleScope home': 'BottleScope 首頁',
  'COLLECTION MONITOR': '收集監測', 'WORKSPACE': '工作區', 'Workspace': '工作區',
  'Main navigation': '主導航', 'Live overview': '實時概覽', 'Measurements': '測量記錄',
  'Device details': '設備詳情', 'Sorting station': '分揀工作站',
  '1 device · 3 collection bins': '1 臺設備 · 3 個收集桶',
  'About this monitor': '關於監測頁面', 'Collection monitor': '收集監測',
  'YOUR SORTING STATION, AT A GLANCE': '分揀工作站，一覽即知',
  'Collection overview': '收集概覽',
  'A clear view of your device and every collection bin.': '清晰查看設備與各個收集桶的狀態。',
  'Live · every 3s': '實時 · 每 3 秒', 'Resume live': '恢復實時更新', 'Refresh': '刷新',
  'Connecting': '正在連接', 'Service connected': '服務已連接', 'Service unavailable': '服務不可用',
  'CONNECTED DEVICE': '連接設備', 'Bottle sorter 01': '瓶罐分揀機 01',
  'Awaiting sync': '等待同步', 'Awaiting device': '等待設備', 'Online': '在線', 'Offline': '離線',
  'online': '在線', 'offline': '離線', 'awaiting device': '等待設備',
  'Connection is verified by device heartbeat': '根據設備心跳確認連接狀態',
  'Current activity': '當前任務', 'Last heartbeat': '最近心跳', 'Heartbeat age': '距上次心跳',
  'Dropped uploads · this boot': '本次開機丟棄的上傳',
  'Idle': '空閒', 'Positioning bin': '正在定位桶位', 'Waiting to settle': '等待穩定',
  'Measuring': '正在測量', 'Device error': '設備異常', 'Awaiting report': '等待上報',
  'No device heartbeat received': '尚未收到設備心跳',
  'Collection bins': '收集桶', 'Independent measurements. One clear view.': '各桶獨立測量，統一查看狀態。',
  '3 collection bins': '3 個收集桶', '1 device': '1 臺設備', 'Collection bin status': '收集桶狀態',
  'Capacity calibration required': '需要容量標定', 'Learn more': '了解更多',
  'Distance readings are saved. Remaining capacity needs measured calibration values.': '距離讀數已保存；計算剩餘容量需要實測標定參數。',
  'Capacity calibration needs attention': '請檢查容量標定',
  'Calibration configuration needs attention': '請檢查標定配置',
  'Values are not used until configuration checks pass.': '配置檢查通過後才會使用這些參數。',
  'Bench test: example thresholds': '臺架測試：示例閾值',
  'Live sensor readings; test percentages. These values do not certify actual bin capacity.': '可接收實時距離；百分比僅供測試，不代表已完成實物容量標定。',
  'Demo thresholds are active. Sensor distances can be live; percentages and full-state labels are for bench testing, not measured bin capacity.': '當前使用演示閾值。距離可來自實時上報，百分比及滿桶狀態僅供臺架測試，不代表已完成實物容量標定。',
  'The monitoring service is unavailable. Retrying automatically; any visible values are from the last successful sync.': '監測服務暫不可用，正在自動重試；當前可見數值來自上次成功同步。',
  'Measurement history could not be refreshed. Previously loaded records are retained.': '測量歷史刷新失敗，仍保留已加載的記錄。',
  'Auto-refresh is paused. You are viewing the last synchronized state. Select Resume live to continue.': '自動刷新已暫停，當前顯示上次同步的狀態；點擊“恢復實時更新”繼續。',
  'Plastic bottles': '塑料瓶', 'Plastic': '塑料', 'Aluminium cans': '易拉罐', 'Cans': '易拉罐',
  'Temporary bin': '臨時桶', 'Temporary': '臨時桶', 'Unknown bin': '未知桶',
  'plastic bottles': '塑料瓶', 'aluminium cans': '易拉罐', 'temporary bin': '臨時桶',
  'PET / PLASTIC': 'PET / 塑料', 'ALUMINIUM / METAL': '鋁 / 金屬', 'OTHER / OVERFLOW': '其他 / 溢出',
  'Estimated remaining': '預計剩餘容量', 'Last valid': '上次有效值', 'last valid': '上次有效值',
  'Last known': '上次狀態', 'Not measured': '尚未測量', 'Config mismatch': '配置不匹配',
  'Reading failed': '測量失敗', 'Update needed': '需要更新', 'Unconfirmed': '未確認',
  'Full': '已滿', 'Clear': '未滿', 'Needs calibration': '需要標定', 'Config error': '配置錯誤',
  'Nearly full': '接近滿桶', 'Normal': '正常', 'Measurement failed': '測量失敗',
  'No sensor echo': '沒有傳感器回波', 'Out of sensor range': '超出傳感器范圍',
  'Unstable readings': '讀數不穩定', 'Sensor distance': '傳感器距離',
  'Last valid distance': '上次有效距離', 'Last attempt received': '最近測量接收時間', 'Latest attempt received': '最近測量接收時間',
  'Last synchronized state': '上次同步狀態', 'Awaiting a measurement': '等待測量',
  'View details': '查看詳情', 'Waiting for device data': '等待設備數據',
  'Showing the last synchronized data': '顯示上次同步的數據',
  'Device offline · last known data': '設備離線 · 顯示歷史數據',
  'No reading in this session': '本次開機尚無測量', 'This reading needs an update': '這條測量需要更新',
  'Measured calibration is not available': '尚無可用的實測標定',
  'Full state has not been confirmed': '尚未確認滿桶狀態',
  'Based on the latest device measurement': '根據設備最新測量計算',
  'Capacity is an ultrasonic estimate, not an exact volume or item count.': '容量由超聲波距離估算，並非精確體積或物品數量。',
  'Waiting for first sync': '等待首次同步', 'Recent measurements': '最近測量',
  'Every attempt has a place in the record.': '每次測量嘗試都有記錄。',
  'Loading records': '正在加載記錄', 'Bin': '桶', 'All bins': '全部桶', 'Result': '結果',
  'All results': '全部結果', 'Successful': '成功', 'Failed': '失敗', 'Latest': '最近',
  'records': '條記錄', 'Latest records': '最近記錄條數', 'Measurement': '測量編號',
  'Collection bin': '收集桶', 'Distance': '距離', 'Full state': '滿桶狀態',
  'Received at': '接收時間', 'Actions': '操作', 'Newest received first': '按接收時間倒序',
  'Filtered within the loaded records': '在已加載記錄中篩選',
  'Failed readings never erase the last valid measurement.': '失敗讀數不會清除上次有效測量。',
  'Unavailable': '不可用', 'Loading measurements…': '正在加載測量…',
  'History is currently unavailable': '歷史記錄暫不可用',
  'No matching measurements': '沒有符合條件的測量', 'No measurements for this bin yet': '該桶尚無測量',
  'No measurements yet': '尚無測量記錄',
  'The page will retry while live refresh is enabled.': '開啟實時刷新後，頁面會繼續重試。',
  'Try a different result filter.': '請嘗試其他結果篩選條件。',
  'Device uploads will appear here, including failed attempts.': '設備上傳的記錄會顯示在這裏，包括失敗的測量嘗試。',
  'The context behind your readings.': '查看讀數對應的設備信息。',
  'Understanding the data': '了解這些數據', 'Current session': '當前開機會話',
  'Each device restart has its own identity. Earlier measurements stay in history.': '每次設備重啟都有獨立身份；以前的測量仍保留在歷史中。',
  'Calibration': '容量標定', 'Configured': '已配置', 'Not ready': '尚未就緒',
  'Configuration error': '配置錯誤', 'Demo thresholds': '演示閾值',
  'Waiting for configuration.': '等待配置。',
  'Measured calibration values are still needed. Distance readings and history remain available.': '仍需提供實測標定參數；距離讀數和歷史記錄仍可查看。',
  'Configuration checks failed. Capacity estimates are unavailable until the configuration is corrected.': '配置檢查未通過，修正前無法估算容量。',
  'Calibration parameters passed software checks. Estimates are calculated for each bin independently.': '標定參數已通過軟件檢查，各桶獨立計算估算值。',
  'Demo mode is active. No bin has complete capacity thresholds.': '演示模式已開啟，但尚無桶具備完整容量閾值。',
  'Data freshness': '數據時效', 'Device availability and measurement freshness are checked independently.': '設備在線狀態與測量時效分別判斷。',
  'Heartbeat timeout': '心跳超時', 'Reading expires after': '測量有效期',
  'Every collection, accounted for.': '每次收集，都有記錄。',
  'Device-reported data · Monitoring only': '設備上報數據 · 僅供監測',
  'BOTTLESCOPE / DETAILS': 'BOTTLESCOPE / 詳情', 'Close details': '關閉詳情',
  'Reported state': '上報狀態', 'Latest attempt': '最近測量', 'Last valid received': '上次有效測量接收時間',
  'Latest sensor error': '最近傳感器錯誤', 'Error': '錯誤', 'None reported': '未上報錯誤', 'None': '無',
  'Device time at measurement': '測量時設備運行時長', 'Session': '開機身份',
  'Calibration version': '配置版本', 'Show original record': '查看原始記錄',
  'Not measured in this session': '本次開機尚未測量',
  'No synchronized status is available yet.': '尚無已同步的狀態。',
  'A new failed attempt keeps the previous valid reading. Device availability, freshness and calibration must be checked before treating a value as current.': '新測量失敗時仍保留之前的有效讀數；將數值視為當前值之前，需要檢查設備在線狀態、測量時效和標定配置。',
  'Online does not mean a fresh reading': '在線不代表測量仍然有效',
  'Estimated remaining capacity': '預計剩餘容量',
  'Each bin needs its own measured empty, full and clear distances. A missing percentage is shown as a dash, never as zero. The estimate comes from ultrasonic height measurements, not exact volume.': '每個桶都需要實測空桶、滿桶和解除滿桶距離。缺少百分比時顯示橫線，不會顯示為零；容量由超聲波高度估算，並非精確體積。',
  'Last valid values are kept': '保留上次有效讀數',
  'If a measurement fails, the device goes offline, or a reading expires, the last valid value may remain visible with a clear label. An unconfirmed full state is never presented as ready to accept an item.': '測量失敗、設備離線或讀數過期時，頁面可能保留帶明確標記的上次有效值。滿桶狀態未確認時，不會表示設備已可繼續接收物品。',
  'This page only monitors': '此頁面僅用於監測',
  'Refreshing this page does not send a heartbeat or create measurements. Positioning and release protection remain on the device.': '刷新頁面不會發送心跳或創建測量；桶位定位與投放保護仍由設備處理。',
  'Configuration check details': '配置檢查詳情',
  'Enable JavaScript to view device status. API documentation remains available at /docs.': '請啟用 JavaScript 查看設備狀態；仍可通過 /docs 訪問接口文檔。',
  'Switch to Traditional Chinese': '切換為繁體中文', 'Switch to English': '切換為英文',
};

Object.assign(translations, {
  'Device': '設備', 'RFID UID': 'RFID 卡號',
  'Updated. Refreshes every 10 seconds while unlocked.': '已更新。解鎖期間每 10 秒自動刷新。',
  'Viewing password is incorrect or has changed.': '查看口令錯誤或已變更。',
  'Unable to refresh. Check the service and credentials; any visible records are from the previous successful refresh.': '無法刷新。請檢查服務與口令；目前顯示的記錄來自上次成功更新。',
  'Recycling rewards': '回收積分', 'RFID rewards reported by your sorting devices.': '查看分揀設備上傳的 RFID 積分記錄。',
  'Viewing password': '查看口令', 'Unlock rewards': '解鎖積分記錄',
  'Use the separate viewing password. It is kept in this tab only.': '請使用獨立查看口令；僅在本分頁記憶體中保留。',
  'Exact device ID': '完整設備編號', 'Exact UID, keep leading zeros': '完整卡號，保留前導 0',
  'View': '檢視', 'Reward history': '積分流水', 'Latest device balances': '最新設備餘額',
  'Per page': '每頁筆數', 'Apply / refresh': '篩選／刷新', 'Lock rewards': '鎖定積分記錄',
  'Previous page': '上一頁', 'Next page': '下一頁',
  'Balances are separate for each device. Received time is server receipt time, not the actual recycling time.': '各設備餘額分開記錄。接收時間為伺服器收到資料的時間，並非實際回收時間。',
});

export function translateText(value, language = 'zh') {
  if (language !== 'zh' || !value) return value;
  const original = String(value);
  const text = original.trim();
  if (!text) return original;
  let translated = translations[text];
  if (translated === undefined) {
    let match;
    if ((match = text.match(/^Last: (.+)$/))) translated = `上次：${translateText(match[1], language)}`;
    else if ((match = text.match(/^BIN (\d+)$/))) translated = `桶 ${match[1]}`;
    else if ((match = text.match(/^Reading #(\d+)$/))) translated = `測量 #${match[1]}`;
    else if ((match = text.match(/^Measurement #(\d+)$/))) translated = `測量記錄 #${match[1]}`;
    else if ((match = text.match(/^View measurement (\d+) details$/))) translated = `查看測量 ${match[1]} 的詳情`;
    else if ((match = text.match(/^View (.+) details$/))) translated = `查看${translateText(match[1], language)}詳情`;
    else if ((match = text.match(/^([\d,]+) shown · ([\d,]+) loaded$/))) translated = `顯示 ${match[1]} 條 · 已加載 ${match[2]} 條`;
    else if ((match = text.match(/^(.+) · up to (\d+) records$/))) translated = `${translateText(match[1], language)} · 最多 ${match[2]} 條記錄`;
    else if ((match = text.match(/^(Last sync|Paused at) (.+)$/))) translated = `${match[1] === 'Last sync' ? '最近同步' : '暫停於'} ${match[2]}`;
    else if ((match = text.match(/^([\d.,]+)s without a new heartbeat marks the device offline$/))) translated = `連續 ${match[1]} 秒未收到新心跳，設備將標為離線`;
    else if ((match = text.match(/^([\d.,]+) sec$/))) translated = `${match[1]} 秒`;
    else if ((match = text.match(/^(\d+)s$/))) translated = `${match[1]} 秒`;
    else if ((match = text.match(/^(\d+)m (\d+)s$/))) translated = `${match[1]} 分 ${match[2]} 秒`;
    else if ((match = text.match(/^(\d+)h (\d+)m$/))) translated = `${match[1]} 小時 ${match[2]} 分`;
    else if ((match = text.match(/^(\d+)d (\d+)h$/))) translated = `${match[1]} 天 ${match[2]} 小時`;
    else if ((match = text.match(/^Demo thresholds configured for: (.+)\. Percentages are for bench testing\.$/))) {
      translated = `已配置演示閾值：${match[1].split(', ').map(name => translateText(name, language)).join('、')}。百分比僅供臺架測試。`;
    } else if ((match = text.match(/^The device is marked offline after (.+) seconds without a new accepted heartbeat\. A bin reading needs an update after (.+) seconds\. These are independent checks\.$/))) {
      translated = `連續 ${match[1]} 秒沒有新的有效心跳，設備將標為離線；桶的測量經過 ${match[2]} 秒後需要更新。這兩項獨立判斷。`;
    } else if (text.includes(' · ')) translated = text.split(' · ').map(part => translateText(part, language)).join(' · ');
  }
  if (translated === undefined) return original;
  return original.slice(0, original.indexOf(text)) + translated + original.slice(original.indexOf(text) + text.length);
}

const storageKey = 'bottlescope.language';
let language = 'en';
try { if (localStorage.getItem(storageKey) === 'zh') language = 'zh'; } catch {}
const sources = new WeakMap();
export const getLanguage = () => language;
export const getLocale = () => language === 'zh' ? 'zh-HK' : 'en-GB';
export function setLanguage(next) {
  language = next === 'zh' ? 'zh' : 'en';
  try { localStorage.setItem(storageKey, language); } catch {}
}

function translateValue(node, key, value, write) {
  let cache = sources.get(node);
  if (!cache) { cache = new Map(); sources.set(node, cache); }
  const previous = cache.get(key);
  const source = previous && previous.translated === value ? previous.source : value;
  const translated = translateText(source, language);
  if (translated !== value) write(translated);
  cache.set(key, {source, translated});
}

export function translatePage() {
  document.documentElement.lang = getLocale();
  document.title = translateText('BottleScope — Collection Monitor', language);
  const button = document.getElementById('languageToggle');
  if (button) {
    const label = language === 'en' ? 'Switch to Traditional Chinese' : '切換為英文';
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
    button.setAttribute('aria-pressed', String(language === 'zh'));
    button.querySelectorAll('[data-language]').forEach(span => span.classList.toggle('is-active', span.dataset.language === language));
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const parent = node.parentElement;
    if (!parent || parent.closest('script, style, pre, #languageToggle')) continue;
    if (parent.closest('code') && node.nodeValue.trim() !== 'No device heartbeat received' && !sources.has(node)) continue;
    translateValue(node, 'text', node.nodeValue, value => { node.nodeValue = value; });
  }
  document.querySelectorAll('[aria-label], [title], [placeholder]').forEach(element => {
    if (element === button || element.closest('pre, script, style')) return;
    for (const attr of ['aria-label', 'title', 'placeholder']) {
      if (element.hasAttribute(attr)) translateValue(element, attr, element.getAttribute(attr), value => element.setAttribute(attr, value));
    }
  });
}

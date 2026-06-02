// ============================================================
// IT-News Frontend Application (Dark Design + Calendar)
// ============================================================

const API_BASE = '/api';

// ===== App State =====
let state = {
  source: 'all',
  category: 'all',
  selectedDay: null,
  currentDay: null,
  articles: [],
  stats: {},
  daysAvailable: [],
  calMonth: new Date(),
  calOpen: false,
};

// ===== Helpers =====

function formatNum(n) {
  n = parseInt(n) || 0;
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : n.toString();
}

function esc(s) {
  if (!s) return '';
  const el = document.createElement('div');
  el.textContent = s;
  return el.innerHTML;
}

function getHostname(url) {
  try { return new URL(url).hostname; } catch(e) { return ''; }
}

function humanTime(isoStr) {
  if (!isoStr) return 'недавно';
  try {
    const dt = new Date(isoStr);
    const diff = Math.floor((Date.now() - dt.getTime()) / 1000);
    if (diff < 60) return 'только что';
    if (diff < 3600) return Math.floor(diff / 60) + ' мин. назад';
    if (diff < 86400) return Math.floor(diff / 3600) + ' ч. назад';
    if (diff < 604800) return Math.floor(diff / 86400) + ' дн. назад';
    return dt.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  } catch(e) {
    return 'недавно';
  }
}

function fmtDate(d) {
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}

const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const DAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

// ===== API Calls =====

async function fetchAPI(endpoint) {
  try {
    const sep = endpoint.includes('?') ? '&' : '?';
    const url = API_BASE + endpoint + sep + '_=' + Date.now();
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    console.error('[IT-News] API error:', e);
    return null;
  }
}

async function loadStats() {
  const data = await fetchAPI('/stats');
  if (!data) return;
  state.stats = data;

  const elAll = document.getElementById('cntAll');
  const elReddit = document.getElementById('cntReddit');
  const elHabr = document.getElementById('cntHabr');
  if (elAll) elAll.textContent = data.total_articles || 0;
  if (elReddit) elReddit.textContent = (data.by_source && data.by_source.reddit) || 0;
  if (elHabr) elHabr.textContent = (data.by_source && data.by_source.habr) || 0;
}

async function loadDays() {
  const data = await fetchAPI('/days');
  if (!data) return;
  state.daysAvailable = data.days || [];
  renderCalendar();
}

async function loadArticles() {
  const list = document.getElementById('newsList');
  if (!list) return;

  list.innerHTML = '<div class="loading">Загрузка новостей</div>';

  const params = new URLSearchParams();
  params.set('source', state.source);
  params.set('category', state.category);
  if (state.selectedDay) {
    params.set('day', state.selectedDay);
  }

  const endpoint = '/articles?' + params.toString();
  console.log('[IT-News] Fetching:', endpoint);

  const data = await fetchAPI(endpoint);
  console.log('[IT-News] Response:', data ? 'count=' + data.count : 'null');

  if (!data) {
    list.innerHTML = '<div class="error-msg">Ошибка загрузки. Попробуйте позже.</div>';
    return;
  }

  state.articles = data.articles || [];

  if (state.articles.length === 0) {
    const dayLabel = state.selectedDay ? state.selectedDay : 'сегодня';
    list.innerHTML = '<div class="empty-state">Нет новостей за ' + dayLabel + ' в этой категории</div>';
    return;
  }

  renderNews();
}

// ===== Render News =====

function renderNews() {
  const list = document.getElementById('newsList');
  if (!list) return;

  const filtered = state.category === 'all'
    ? state.articles
    : state.articles.filter(a => a.category === state.category);

  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state">Нет новостей в этой категории</div>';
    return;
  }

  list.innerHTML = filtered.map(function(a) {
    const isHabr = a.source === 'habr';
    const voteClass = isHabr ? 'habr-vote' : '';
    const scoreDisplay = (a.score > 0 ? '+' : '') + formatNum(a.score);

    const metaSource = isHabr
      ? '<span class="meta-habr-hub">Хабр</span>'
      : '<span class="meta-subreddit">r/' + esc(a.subreddit || 'technology') + '</span>';

    const authorHtml = a.author
      ? '<span class="meta-author"><img src="icons/pin/icons8-мужчина-пользователь-50.png" alt="" class="meta-icon" width="14" height="14"> ' + esc(a.author) + '</span>'
      : '';

    const readingHtml = isHabr && a.reading_time
      ? '<span><img src="icons/pin/icons8-показать-50.png" alt="" class="meta-icon" width="14" height="14"> ' + a.reading_time + ' мин</span>'
      : '';

    const descHtml = a.lead
      ? '<div class="card-desc-ru ' + (isHabr ? 'habr-desc' : '') + '">' + esc(a.lead) + '</div>'
      : '';

    const hostname = a.url ? esc(getHostname(a.url)) : '';
    const relTime = humanTime(a.published_at || '');
    const cardClass = isHabr ? 'news-card habr-card' : 'news-card';
    const origTitleHtml = !isHabr && a.title && a.title !== a.title_ru
      ? '<span class="orig-title">' + esc(a.title) + '</span>'
      : '';

    return (
      '<article class="' + cardClass + '" onclick="window.open(\'' + esc(a.url) + '\', \'_blank\')">' +
        '<div class="card-top">' +
          '<div class="vote-box ' + voteClass + '">' +
            '<span class="score">' + scoreDisplay + '</span>' +
            '<span class="label">' + (isHabr ? 'рейтинг' : 'votes') + '</span>' +
          '</div>' +
          '<div class="card-content">' +
            '<h2 class="card-title-ru">' + esc(a.title_ru || a.title || 'Без заголовка') + '</h2>' +
            descHtml +
            '<div class="card-meta">' +
              metaSource + authorHtml +
              '<span><img src="icons/pin/icons8-комментарии-50.png" alt="" class="meta-icon" width="14" height="14"> ' + formatNum(a.comments || 0) + '</span>' +
              readingHtml +
              '<span><img src="icons/pin/icons8-часы-50.png" alt="" class="meta-icon" width="14" height="14"> ' + relTime + '</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="card-original">' +
          '<a href="' + esc(a.url) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">' +
            '<img src="icons/pin/icons8-интернет-50.png" alt="" class="meta-icon" width="14" height="14"> Читать оригинал на ' + hostname +
          '</a>' +
          origTitleHtml +
        '</div>' +
      '</article>'
    );
  }).join('');
}

// ===== Source / Filter =====

function switchSource(source) {
  state.source = source;
  state.category = 'all';

  document.querySelectorAll('.source-tab').forEach(function(t) {
    const tid = t.id.replace('tab', '').toLowerCase();
    t.classList.toggle('active', tid === source);
  });

  document.querySelectorAll('.filter-btn').forEach(function(b) {
    b.classList.remove('active');
    if (b.getAttribute('onclick') && b.getAttribute('onclick').includes("'all'")) {
      b.classList.add('active');
    }
  });

  loadArticles();
}

function filterNews(cat, btn) {
  document.querySelectorAll('.filter-btn').forEach(function(b) {
    b.classList.remove('active');
  });
  if (btn) btn.classList.add('active');
  state.category = cat;
  renderNews();
}

// ===== Calendar =====

function toggleCalendar() {
  state.calOpen = !state.calOpen;
  const dd = document.getElementById('calendarDropdown');
  const arrow = document.getElementById('calArrow');
  if (dd) dd.style.display = state.calOpen ? 'block' : 'none';
  if (arrow) arrow.style.transform = state.calOpen ? 'rotate(180deg)' : '';
  if (state.calOpen) renderCalendar();
}

function renderCalendar() {
  const grid = document.getElementById('calGrid');
  const label = document.getElementById('calMonthLabel');
  if (!grid || !label) return;

  const d = state.calMonth;
  const year = d.getFullYear();
  const month = d.getMonth();

  label.textContent = MONTHS_RU[month] + ' ' + year;
  grid.innerHTML = '';

  // Day names
  DAYS_SHORT.forEach(function(name) {
    const el = document.createElement('div');
    el.className = 'day-name';
    el.textContent = name;
    grid.appendChild(el);
  });

  const firstDay = new Date(year, month, 1);
  let dayOfWeek = firstDay.getDay();
  dayOfWeek = dayOfWeek === 0 ? 6 : dayOfWeek - 1;

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();
  const today = new Date();
  const todayStr = fmtDate(today);

  // Build set of days with news
  const newsDays = {};
  state.daysAvailable.forEach(function(dd) {
    newsDays[dd.day] = true;
  });

  // Previous month filler
  for (let i = dayOfWeek - 1; i >= 0; i--) {
    const el = document.createElement('div');
    el.className = 'cal-day empty';
    el.textContent = daysInPrevMonth - i;
    grid.appendChild(el);
  }

  // Current month days
  for (let day = 1; day <= daysInMonth; day++) {
    const el = document.createElement('div');
    const dateStr = year + '-' + String(month + 1).padStart(2, '0') + '-' + String(day).padStart(2, '0');
    el.textContent = day;
    el.dataset.date = dateStr;

    const classes = ['cal-day'];
    if (dateStr === todayStr) classes.push('today');
    if (newsDays[dateStr]) classes.push('has-news');
    if (state.selectedDay === dateStr) classes.push('selected');

    el.className = classes.join(' ');
    el.addEventListener('click', function() {
      selectDay(dateStr);
    });
    grid.appendChild(el);
  }

  // Next month filler
  const totalCells = dayOfWeek + daysInMonth;
  const remaining = (7 - (totalCells % 7)) % 7;
  for (let i = 0; i < remaining; i++) {
    const el = document.createElement('div');
    el.className = 'cal-day empty';
    el.textContent = i + 1;
    grid.appendChild(el);
  }
}

function selectDay(dateStr) {
  state.selectedDay = dateStr;
  state.calOpen = false;

  const dd = document.getElementById('calendarDropdown');
  const arrow = document.getElementById('calArrow');
  if (dd) dd.style.display = 'none';
  if (arrow) arrow.style.transform = '';

  // Update label
  const label = document.getElementById('calLabel');
  if (label) {
    const today = fmtDate(new Date());
    if (dateStr === today) {
      label.textContent = 'Сегодня';
    } else {
      const parts = dateStr.split('-');
      label.textContent = parts[2] + ' ' + MONTHS_RU[parseInt(parts[1]) - 1] + ' ' + parts[0];
    }
  }

  renderCalendar();
  loadArticles();
}

function calPrevMonth() {
  state.calMonth.setMonth(state.calMonth.getMonth() - 1);
  renderCalendar();
}

function calNextMonth() {
  state.calMonth.setMonth(state.calMonth.getMonth() + 1);
  renderCalendar();
}

function calGoToday() {
  state.calMonth = new Date();
  selectDay(fmtDate(new Date()));
}

// Close calendar on outside click
document.addEventListener('click', function(e) {
  const bar = document.getElementById('calendarBar');
  if (bar && !bar.contains(e.target) && state.calOpen) {
    state.calOpen = false;
    const dd = document.getElementById('calendarDropdown');
    const arrow = document.getElementById('calArrow');
    if (dd) dd.style.display = 'none';
    if (arrow) arrow.style.transform = '';
  }
});

// ===== Swipe Navigation (source tabs) =====

(function() {
  var tabs = document.querySelector('.source-tabs');
  if (!tabs) return;

  var startX = 0;
  var startY = 0;
  var tracking = false;
  var touchInTabs = false;

  document.addEventListener('touchstart', function(e) {
    var rect = tabs.getBoundingClientRect();
    var t = e.touches[0];
    startX = t.clientX;
    startY = t.clientY;
    tracking = true;
    touchInTabs = (t.clientY >= rect.top && t.clientY <= rect.bottom);
  }, { passive: true });

  document.addEventListener('touchmove', function(e) {
    if (!tracking || !touchInTabs) return;
    var t = e.touches[0];
    var dx = Math.abs(t.clientX - startX);
    var dy = Math.abs(t.clientY - startY);
    if (dx > 30 && dx > dy * 1.2) {
      e.preventDefault();
      // Визуальный фидбек — подсветка следующего/предыдущего таба
      highlightSwipeTarget(t.clientX - startX);
    }
  }, { passive: false });

  document.addEventListener('touchend', function(e) {
    if (!tracking || !touchInTabs) return;
    tracking = false;
    touchInTabs = false;
    clearHighlight();

    var endX = e.changedTouches[0].clientX;
    var diff = startX - endX;
    var absDiff = Math.abs(diff);

    if (absDiff < 60) return;

    var sources = ['all', 'reddit', 'habr'];
    var idx = sources.indexOf(state.source);
    if (idx === -1) return;

    if (diff > 0 && idx < sources.length - 1) {
      switchSource(sources[idx + 1]);
    } else if (diff < 0 && idx > 0) {
      switchSource(sources[idx - 1]);
    }
  });

  function highlightSwipeTarget(dx) {
    var sources = ['all', 'reddit', 'habr'];
    var idx = sources.indexOf(state.source);
    if (idx === -1) return;
    var target = null;
    if (dx > 0 && idx < sources.length - 1) {
      target = document.getElementById('tab' + capitalize(sources[idx + 1]));
    } else if (dx < 0 && idx > 0) {
      target = document.getElementById('tab' + capitalize(sources[idx - 1]));
    }
    // Убираем подсветку со всех
    document.querySelectorAll('.source-tab').forEach(function(t) {
      t.style.transition = 'background .15s, box-shadow .15s';
      if (t !== target) t.style.boxShadow = '';
    });
    if (target) {
      target.style.boxShadow = '0 0 12px rgba(99,102,241,0.5)';
    }
  }

  function clearHighlight() {
    document.querySelectorAll('.source-tab').forEach(function(t) {
      t.style.boxShadow = '';
    });
  }

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
})();

// ===== Init =====

async function loadAll() {
  await Promise.all([loadStats(), loadDays()]);

  // Set initial day to today
  const today = fmtDate(new Date());
  state.selectedDay = today;
  state.calMonth = new Date();

  const label = document.getElementById('calLabel');
  if (label) label.textContent = 'Сегодня';

  await loadArticles();

  // Update footer
  const s = state.stats;
  const footerInfo = document.getElementById('footerInfo');
  if (footerInfo && s) {
    footerInfo.innerHTML =
      'Всего: ' + (s.total_articles || 0) + ' статей' +
      ' • Reddit: ' + ((s.by_source && s.by_source.reddit) || 0) +
      ' • Хабр: ' + ((s.by_source && s.by_source.habr) || 0);
  }

  const timeEl = document.getElementById('updateTime');
  if (timeEl) {
    timeEl.textContent = 'Обновлено: ' + new Date().toLocaleString('ru-RU');
  }
}

// Load on start
loadAll();

// Auto-refresh every 10 minutes
setInterval(loadAll, 10 * 60 * 1000);

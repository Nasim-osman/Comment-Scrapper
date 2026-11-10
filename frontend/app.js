/**
 * OmniScrape - Frontend Application Controller
 */

// State
const state = {
  selectedPlatform: 'auto',
  activeJobId: null,
  isScraping: false,
  ws: null,
  currentComments: [],
  tablePage: 1,
  tableLimit: 25,
  totalTableRows: 0,
  activeLangFilter: 'all',
  searchQuery: '',
  stats: {
    total: 0,
    bangla: 0,
    english: 0,
    mixed: 0
  }
};

// DOM Elements
const elements = {
  // Platform
  platformCards: document.querySelectorAll('.platform-card'),
  // Inputs
  btnModeSingle: document.getElementById('btn-mode-single'),
  btnModeBatch: document.getElementById('btn-mode-batch'),
  groupSingle: document.getElementById('group-single-url'),
  groupBatch: document.getElementById('group-batch-url'),
  inputUrl: document.getElementById('input-url'),
  inputBatchUrls: document.getElementById('input-batch-urls'),
  btnClearUrl: document.getElementById('btn-clear-url'),
  detectedBadge: document.getElementById('detected-platform-badge'),
  // Options
  inputMaxComments: document.getElementById('input-max-comments'),
  inputMinLength: document.getElementById('input-min-length'),
  checkCleanNlp: document.getElementById('check-clean-nlp'),
  checkIncludeReplies: document.getElementById('check-include-replies'),
  checkBanglaOnly: document.getElementById('check-bangla-only'),
  // Buttons
  btnStartScrape: document.getElementById('btn-start-scrape'),
  btnStopScrape: document.getElementById('btn-stop-scrape'),
  // Progress
  progressContainer: document.getElementById('progress-container'),
  progressStatusText: document.getElementById('progress-status-text'),
  progressPercent: document.getElementById('progress-percent'),
  progressBarFill: document.getElementById('progress-bar-fill'),
  // Terminal
  terminalLogs: document.getElementById('terminal-logs'),
  terminalCountBadge: document.getElementById('terminal-count-badge'),
  btnClearTerminal: document.getElementById('btn-clear-terminal'),
  // Stats
  statTotal: document.getElementById('stat-total'),
  statBangla: document.getElementById('stat-bangla'),
  statEnglish: document.getElementById('stat-english'),
  statMixed: document.getElementById('stat-mixed'),
  // Export Buttons
  btnExportCsv: document.getElementById('btn-export-csv'),
  btnExportExcel: document.getElementById('btn-export-excel'),
  btnExportJson: document.getElementById('btn-export-json'),
  // Table
  inputSearchTable: document.getElementById('input-search-table'),
  langPills: document.querySelectorAll('.lang-pill'),
  pillAllCount: document.getElementById('pill-all-count'),
  pillBnCount: document.getElementById('pill-bn-count'),
  pillEnCount: document.getElementById('pill-en-count'),
  pillMixedCount: document.getElementById('pill-mixed-count'),
  commentsTableBody: document.getElementById('comments-table-body'),
  tablePagination: document.getElementById('table-pagination'),
  paginationInfo: document.getElementById('pagination-info'),
  btnPagePrev: document.getElementById('btn-page-prev'),
  btnPageNext: document.getElementById('btn-page-next'),
  pageCurrent: document.getElementById('page-current'),
  // Modal & Sessions
  modalSessions: document.getElementById('modal-sessions'),
  btnOpenSessions: document.getElementById('btn-open-sessions'),
  btnCloseModal: document.getElementById('btn-close-modal'),
  fbSessionBadge: document.getElementById('fb-session-badge'),
  igSessionBadge: document.getElementById('ig-session-badge'),
  twitterSessionBadge: document.getElementById('twitter-session-badge'),
  btnLoginFb: document.getElementById('btn-login-fb'),
  btnLoginIg: document.getElementById('btn-login-ig'),
  btnLoginTwitter: document.getElementById('btn-login-twitter'),
  btnToggleFbCookies: document.getElementById('btn-toggle-fb-cookies'),
  btnToggleIgCookies: document.getElementById('btn-toggle-ig-cookies'),
  btnToggleTwitterCookies: document.getElementById('btn-toggle-twitter-cookies'),
  fbCookieRow: document.getElementById('fb-cookie-input-row'),
  igCookieRow: document.getElementById('ig-cookie-input-row'),
  twitterCookieRow: document.getElementById('twitter-cookie-input-row'),
  inputFbCookies: document.getElementById('input-fb-cookies'),
  inputIgCookies: document.getElementById('input-ig-cookies'),
  inputTwitterCookies: document.getElementById('input-twitter-cookies'),
  btnSaveFbCookies: document.getElementById('btn-save-fb-cookies'),
  btnSaveIgCookies: document.getElementById('btn-save-ig-cookies'),
  btnSaveTwitterCookies: document.getElementById('btn-save-twitter-cookies'),
  inputRedditClientId: document.getElementById('input-reddit-client-id'),
  inputRedditClientSecret: document.getElementById('input-reddit-client-secret'),
  btnSaveRedditKeys: document.getElementById('btn-save-reddit-keys'),
  connectionStatus: document.getElementById('connection-status'),
  metaLoginNotice: document.getElementById('meta-login-notice'),
  btnQuickSession: document.getElementById('btn-quick-session')
};

// URL Detection Helper
function detectPlatform(url) {
  const u = (url || '').toLowerCase();
  if (u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube';
  if (u.includes('reddit.com') || u.includes('redd.it')) return 'reddit';
  if (u.includes('instagram.com') || u.includes('instagr.am')) return 'instagram';
  if (u.includes('facebook.com') || u.includes('fb.watch') || u.includes('fb.com')) return 'facebook';
  if (u.includes('twitter.com') || u.includes('x.com')) return 'twitter';
  return null;
}

function updatePlatformSelection(platform) {
  state.selectedPlatform = platform;
  elements.platformCards.forEach(card => {
    if (card.dataset.platform === platform) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  });

  if (elements.metaLoginNotice) {
    if (platform === 'facebook' || platform === 'instagram') {
      elements.metaLoginNotice.style.display = 'flex';
    } else {
      elements.metaLoginNotice.style.display = 'none';
    }
  }
}

// WebSocket Setup
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  try {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      elements.connectionStatus.innerHTML = '<span class="status-dot"></span><span class="status-label">Server Connected</span>';
      // Heartbeat ping
      setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWsMessage(msg);
      } catch (err) {
        // Ping response or string
      }
    };

    ws.onclose = () => {
      elements.connectionStatus.innerHTML = '<span class="status-dot" style="background:#ef4444;box-shadow:0 0 10px #ef4444;"></span><span class="status-label" style="color:#f87171;">Reconnecting...</span>';
      setTimeout(initWebSocket, 3000);
    };

    state.ws = ws;
  } catch (e) {
    console.error('WS Connection error:', e);
  }
}

function handleWsMessage(msg) {
  if (msg.type === 'log') {
    const data = msg.data;
    appendTerminalLog(data.log, data.status);
    if (data.count !== undefined) {
      elements.terminalCountBadge.textContent = `${data.count} Comments Extracted`;
      elements.statTotal.textContent = data.count;
    }
  } else if (msg.type === 'job_status') {
    const data = msg.data;
    if (data.job_id === state.activeJobId) {
      if (data.status === 'completed' || data.status === 'stopped' || data.status === 'failed') {
        finishScrapeUI(data.status);
      }
    }
  } else if (msg.type === 'session_update') {
    updateSessionBadges(msg.data);
  }
}

// Append Terminal Log Line
function appendTerminalLog(text, status = 'info') {
  const div = document.createElement('div');
  div.className = `log-line ${status}`;
  const time = new Date().toLocaleTimeString();
  div.textContent = `[${time}] ${text}`;
  elements.terminalLogs.appendChild(div);
  elements.terminalLogs.scrollTop = elements.terminalLogs.scrollHeight;
}

// Start Scraping
async function startScraping() {
  let urls = [];
  const isBatch = elements.btnModeBatch.classList.contains('active');

  if (isBatch) {
    urls = elements.inputBatchUrls.value
      .split('\n')
      .map(u => u.trim())
      .filter(u => u.length > 5);
  } else {
    const u = elements.inputUrl.value.trim();
    if (u) urls.push(u);
  }

  if (urls.length === 0) {
    alert('Please enter at least one valid post or video URL.');
    elements.inputUrl.focus();
    return;
  }

  const payload = {
    urls: urls,
    platform: state.selectedPlatform,
    max_comments_per_url: parseInt(elements.inputMaxComments.value, 10) || 200,
    include_replies: elements.checkIncludeReplies.checked,
    clean_text: elements.checkCleanNlp.checked,
    filter_bangla_only: elements.checkBanglaOnly.checked,
    min_length: parseInt(elements.inputMinLength.value, 10) || 1
  };

  // UI state change
  state.isScraping = true;
  elements.btnStartScrape.disabled = true;
  elements.btnStopScrape.disabled = false;
  elements.progressContainer.style.display = 'block';
  elements.progressPercent.textContent = '0%';
  elements.progressBarFill.style.width = '0%';
  elements.progressStatusText.textContent = 'Starting scrape job...';
  elements.statTotal.textContent = '0';
  elements.statBangla.textContent = '0';
  elements.statEnglish.textContent = '0';
  elements.statMixed.textContent = '0';
  elements.terminalCountBadge.textContent = '0 Comments Extracted';
  appendTerminalLog(`Initiating job for ${urls.length} target(s)...`, 'system');

  try {
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to start scraping');

    state.activeJobId = data.job_id;
    appendTerminalLog(`Job ID: ${data.job_id} assigned. Processing in background...`, 'system');

    // Poll status periodically
    pollJobStatus();
  } catch (err) {
    appendTerminalLog(`Error: ${err.message}`, 'error');
    finishScrapeUI('failed');
  }
}

// Stop Scraping
async function stopScraping() {
  if (!state.activeJobId) return;
  try {
    await fetch(`/api/jobs/${state.activeJobId}/stop`, { method: 'POST' });
    appendTerminalLog('Stop signal sent to scraper...', 'warning');
    elements.btnStopScrape.disabled = true;
  } catch (err) {
    console.error('Stop error:', err);
  }
}

// Poll Job Status
function pollJobStatus() {
  if (!state.isScraping || !state.activeJobId) return;

  const interval = setInterval(async () => {
    if (!state.isScraping) {
      clearInterval(interval);
      return;
    }

    try {
      const res = await fetch(`/api/jobs/${state.activeJobId}`);
      if (!res.ok) return;
      const job = await res.json();

      // Update progress
      elements.progressPercent.textContent = `${Math.round(job.progress)}%`;
      elements.progressBarFill.style.width = `${job.progress}%`;
      elements.progressStatusText.textContent = job.current_status_text;
      elements.terminalCountBadge.textContent = `${job.total_comments} Comments Extracted`;
      elements.statTotal.textContent = job.total_comments;

      if (job.status === 'completed' || job.status === 'stopped' || job.status === 'failed') {
        clearInterval(interval);
        finishScrapeUI(job.status);
      }
    } catch (e) {
      console.warn('Poll error:', e);
    }
  }, 2000);
}

// Finish Scrape UI
function finishScrapeUI(status) {
  state.isScraping = false;
  elements.btnStartScrape.disabled = false;
  elements.btnStopScrape.disabled = true;
  elements.progressBarFill.style.width = '100%';
  elements.progressPercent.textContent = '100%';

  if (status === 'completed') {
    elements.progressStatusText.textContent = 'Completed successfully!';
    appendTerminalLog('Extraction job completed successfully. Ready to export!', 'completed');
  } else if (status === 'stopped') {
    elements.progressStatusText.textContent = 'Scraping stopped by user.';
  }

  // Enable Export buttons
  elements.btnExportCsv.disabled = false;
  elements.btnExportExcel.disabled = false;
  elements.btnExportJson.disabled = false;

  // Load Table Data
  loadCommentsTable(1);
}

// Load Comments for Table
async function loadCommentsTable(page = 1) {
  if (!state.activeJobId) return;

  state.tablePage = page;
  const langParam = state.activeLangFilter;
  const searchParam = state.searchQuery;

  const url = `/api/jobs/${state.activeJobId}/comments?page=${page}&limit=${state.tableLimit}&language=${langParam}&search=${encodeURIComponent(searchParam)}`;

  try {
    const res = await fetch(url);
    const result = await res.json();
    if (!res.ok) return;

    state.currentComments = result.data;
    state.totalTableRows = result.total;

    // Update Stats Ribbon & Pill Counters
    if (result.stats) {
      elements.statTotal.textContent = result.stats.total_in_job;
      elements.statBangla.textContent = result.stats.bangla;
      elements.statEnglish.textContent = result.stats.english;
      elements.statMixed.textContent = result.stats.mixed;

      elements.pillAllCount.textContent = result.stats.total_in_job;
      elements.pillBnCount.textContent = result.stats.bangla;
      elements.pillEnCount.textContent = result.stats.english;
      elements.pillMixedCount.textContent = result.stats.mixed;
    }

    renderTableRows(result.data, page, result.total);
    renderPagination(page, result.total);
  } catch (err) {
    console.error('Failed to load comments table:', err);
  }
}

// Render Table Rows
function renderTableRows(comments, page, total) {
  const tbody = elements.commentsTableBody;
  tbody.innerHTML = '';

  if (!comments || comments.length === 0) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="8">
          <div class="empty-state">
            <div class="empty-icon">🔍</div>
            <h3>No matching comments found</h3>
            <p>Try adjusting your search query or language filter.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  const startIdx = (page - 1) * state.tableLimit;

  comments.forEach((c, idx) => {
    const row = document.createElement('tr');

    const isReply = c.Type === 'REPLY' || c.is_reply;
    const typeLabel = isReply ? 'REPLY' : 'MAIN COMMENT';
    const typeBadgeClass = isReply ? 'badge-type-reply' : 'badge-type-main';
    const author = c.Author || c.author || 'Anonymous';
    const commentText = c.Comment || c.text || c.cleaned_text || '';
    const replyingTo = c.Replying_To || c.replying_to || (isReply ? (c.parent_author || 'Parent') : '-');
    const likes = c.Likes !== undefined ? c.Likes : (c.likes || 0);
    const pubAt = c.Published_At || c.published_at || c.timestamp || '-';

    row.innerHTML = `
      <td style="color:var(--text-dim);font-family:var(--font-mono);">${startIdx + idx + 1}</td>
      <td><span class="${typeBadgeClass}">${typeLabel}</span></td>
      <td>
        <span class="comment-author-name">${escapeHtml(author)}</span>
      </td>
      <td>
        <div class="comment-text-box">${escapeHtml(commentText)}</div>
      </td>
      <td style="color:var(--text-muted);font-family:var(--font-mono);font-size:12px;">
        ${replyingTo !== '-' ? `<span style="color:#60a5fa;font-weight:600;">${escapeHtml(replyingTo)}</span>` : '-'}
      </td>
      <td style="font-family:var(--font-mono);text-align:right;">${likes}</td>
      <td style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);">${escapeHtml(pubAt)}</td>
      <td>
        <button class="btn btn-sm btn-secondary btn-copy" data-text="${escapeHtml(commentText)}" title="Copy comment">
          📋 Copy
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });

  // Attach copy listeners
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const text = btn.dataset.text;
      navigator.clipboard.writeText(text).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = '✓ Copied';
        setTimeout(() => btn.innerHTML = orig, 1500);
      });
    });
  });
}

// Render Pagination
function renderPagination(page, total) {
  if (total <= state.tableLimit) {
    elements.tablePagination.style.display = 'none';
    return;
  }

  elements.tablePagination.style.display = 'flex';
  const totalPages = Math.ceil(total / state.tableLimit) || 1;
  const start = (page - 1) * state.tableLimit + 1;
  const end = Math.min(page * state.tableLimit, total);

  elements.paginationInfo.textContent = `Showing ${start}-${end} of ${total} comments`;
  elements.pageCurrent.textContent = `Page ${page} of ${totalPages}`;

  elements.btnPagePrev.disabled = page <= 1;
  elements.btnPageNext.disabled = page >= totalPages;
}

// Download Exports
function triggerExport(format) {
  if (!state.activeJobId) {
    alert('Please run a scraping job first.');
    return;
  }
  const downloadUrl = `/api/export/${state.activeJobId}/${format}`;
  window.location.href = downloadUrl;
}

// Sessions & Auth Modal
async function checkSessionStatuses() {
  try {
    const res = await fetch('/api/sessions/status');
    const data = await res.json();
    updateSessionBadges(data);
  } catch (e) {
    console.warn('Session check failed:', e);
  }
}

function updateSessionBadges(data) {
  if (data.facebook_logged_in) {
    elements.fbSessionBadge.textContent = 'Connected ✓';
    elements.fbSessionBadge.className = 'session-badge-status connected';
  } else {
    elements.fbSessionBadge.textContent = 'Not Connected';
    elements.fbSessionBadge.className = 'session-badge-status';
  }

  if (data.instagram_logged_in) {
    elements.igSessionBadge.textContent = 'Connected ✓';
    elements.igSessionBadge.className = 'session-badge-status connected';
  } else {
    elements.igSessionBadge.textContent = 'Not Connected';
    elements.igSessionBadge.className = 'session-badge-status';
  }

  if (elements.twitterSessionBadge) {
    if (data.twitter_logged_in) {
      elements.twitterSessionBadge.textContent = 'Connected ✓';
      elements.twitterSessionBadge.className = 'session-badge-status connected';
    } else {
      elements.twitterSessionBadge.textContent = 'Not Connected';
      elements.twitterSessionBadge.className = 'session-badge-status';
    }
  }

  if (data.reddit_api_configured) {
    elements.inputRedditClientId.placeholder = 'Reddit API Configured ✓';
  }
}

async function triggerBrowserLogin(platform) {
  appendTerminalLog(`Opening Chromium browser for ${platform} login...`, 'system');
  try {
    const res = await fetch('/api/sessions/login-interactive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: platform })
    });
    const data = await res.json();
    alert(data.message);
  } catch (e) {
    alert('Failed to launch browser login: ' + e.message);
  }
}

// Utilities
function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return (text || '').replace(/[&<>"']/g, m => map[m]);
}

// Event Listeners
function setupEventListeners() {
  // Platform selection cards
  elements.platformCards.forEach(card => {
    card.addEventListener('click', () => {
      updatePlatformSelection(card.dataset.platform);
    });
  });

  // URL input auto-detect
  elements.inputUrl.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (!val) {
      elements.detectedBadge.style.display = 'none';
      return;
    }
    const detected = detectPlatform(val);
    if (detected) {
      elements.detectedBadge.textContent = detected.toUpperCase();
      elements.detectedBadge.style.display = 'inline-block';
      updatePlatformSelection(detected);
    } else {
      elements.detectedBadge.style.display = 'none';
    }
  });

  elements.btnClearUrl.addEventListener('click', () => {
    elements.inputUrl.value = '';
    elements.detectedBadge.style.display = 'none';
    elements.inputUrl.focus();
  });

  // Single / Batch Mode
  elements.btnModeSingle.addEventListener('click', () => {
    elements.btnModeSingle.classList.add('active');
    elements.btnModeBatch.classList.remove('active');
    elements.groupSingle.style.display = 'block';
    elements.groupBatch.style.display = 'none';
  });

  elements.btnModeBatch.addEventListener('click', () => {
    elements.btnModeBatch.classList.add('active');
    elements.btnModeSingle.classList.remove('active');
    elements.groupSingle.style.display = 'none';
    elements.groupBatch.style.display = 'block';
  });

  // Scrape action buttons
  elements.btnStartScrape.addEventListener('click', startScraping);
  elements.btnStopScrape.addEventListener('click', stopScraping);

  // Terminal clear
  elements.btnClearTerminal.addEventListener('click', () => {
    elements.terminalLogs.innerHTML = '';
  });

  // Export buttons
  elements.btnExportCsv.addEventListener('click', () => triggerExport('csv'));
  elements.btnExportExcel.addEventListener('click', () => triggerExport('excel'));
  elements.btnExportJson.addEventListener('click', () => triggerExport('json'));

  // Table search & filter
  let searchTimer;
  elements.inputSearchTable.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.searchQuery = e.target.value.trim();
      loadCommentsTable(1);
    }, 300);
  });

  // Language filter pills
  elements.langPills.forEach(pill => {
    pill.addEventListener('click', () => {
      elements.langPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeLangFilter = pill.dataset.lang;
      loadCommentsTable(1);
    });
  });

  // Pagination
  elements.btnPagePrev.addEventListener('click', () => {
    if (state.tablePage > 1) loadCommentsTable(state.tablePage - 1);
  });
  elements.btnPageNext.addEventListener('click', () => {
    loadCommentsTable(state.tablePage + 1);
  });

  // Modal open/close
  const openSessionModal = () => {
    checkSessionStatuses();
    elements.modalSessions.style.display = 'flex';
  };

  elements.btnOpenSessions.addEventListener('click', openSessionModal);
  if (elements.btnQuickSession) {
    elements.btnQuickSession.addEventListener('click', openSessionModal);
  }
  elements.btnCloseModal.addEventListener('click', () => {
    elements.modalSessions.style.display = 'none';
  });
  elements.modalSessions.addEventListener('click', (e) => {
    if (e.target === elements.modalSessions) {
      elements.modalSessions.style.display = 'none';
    }
  });

  // Interactive browser logins
  elements.btnLoginFb.addEventListener('click', () => triggerBrowserLogin('facebook'));
  elements.btnLoginIg.addEventListener('click', () => triggerBrowserLogin('instagram'));
  if (elements.btnLoginTwitter) {
    elements.btnLoginTwitter.addEventListener('click', () => triggerBrowserLogin('twitter'));
  }

  // Toggle manual cookie rows
  elements.btnToggleFbCookies.addEventListener('click', () => {
    elements.fbCookieRow.style.display = elements.fbCookieRow.style.display === 'none' ? 'flex' : 'none';
  });
  elements.btnToggleIgCookies.addEventListener('click', () => {
    elements.igCookieRow.style.display = elements.igCookieRow.style.display === 'none' ? 'flex' : 'none';
  });
  if (elements.btnToggleTwitterCookies) {
    elements.btnToggleTwitterCookies.addEventListener('click', () => {
      elements.twitterCookieRow.style.display = elements.twitterCookieRow.style.display === 'none' ? 'flex' : 'none';
    });
  }

  // Save manual cookies
  elements.btnSaveFbCookies.addEventListener('click', async () => {
    const raw = elements.inputFbCookies.value.trim();
    if (!raw) return alert('Please enter cookie string.');
    const res = await fetch('/api/sessions/save-cookies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'facebook', cookies: raw })
    });
    const d = await res.json();
    alert(d.message);
    checkSessionStatuses();
  });

  elements.btnSaveIgCookies.addEventListener('click', async () => {
    const raw = elements.inputIgCookies.value.trim();
    if (!raw) return alert('Please enter cookie string.');
    const res = await fetch('/api/sessions/save-cookies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'instagram', cookies: raw })
    });
    const d = await res.json();
    alert(d.message);
    checkSessionStatuses();
  });

  if (elements.btnSaveTwitterCookies) {
    elements.btnSaveTwitterCookies.addEventListener('click', async () => {
      const raw = elements.inputTwitterCookies.value.trim();
      if (!raw) return alert('Please enter cookie string.');
      const res = await fetch('/api/sessions/save-cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: 'twitter', cookies: raw })
      });
      const d = await res.json();
      alert(d.message);
      checkSessionStatuses();
    });
  }

  // Save Reddit API keys
  elements.btnSaveRedditKeys.addEventListener('click', async () => {
    const cid = elements.inputRedditClientId.value.trim();
    const csec = elements.inputRedditClientSecret.value.trim();
    if (!cid || !csec) return alert('Please enter both client ID and client secret.');
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reddit_client_id: cid, reddit_client_secret: csec })
    });
    const d = await res.json();
    alert(d.message);
    checkSessionStatuses();
  });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  setupEventListeners();
  checkSessionStatuses();
});

/**
 * Frontend JavaScript for Indian Stock Extractor AI.
 * Handles SSE live progress, recommendation rendering, filtering, exports, and gallery.
 */

let currentVideoReport = null;
let currentActionFilter = 'ALL';
let currentSectorFilter = 'ALL';
let eventSource = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  updateApiKeyStatusBadge();
  loadGalleryCount();
  loadStorageStats();
});

// -------------------------------------------------------------
// Storage & Free-Tier Quota (500 MB) Management
// -------------------------------------------------------------
async function loadStorageStats() {
  try {
    const res = await fetch('/api/system/storage');
    if (!res.ok) return;
    const stats = await res.json();

    // Update navbar badge
    const navText = document.getElementById('navStorageText');
    if (navText) {
      navText.innerText = `DB: ${stats.total_used_mb}MB (${stats.free_tier_percent_used}%)`;
    }

    // Update modal elements
    const dbEngine = document.getElementById('modalStorageDbEngine');
    if (dbEngine) dbEngine.innerText = stats.database_engine || 'Neon PostgreSQL';

    const pctText = document.getElementById('modalStoragePct');
    if (pctText) pctText.innerText = `${stats.free_tier_percent_used}% Used`;

    const bar = document.getElementById('modalStorageBar');
    if (bar) bar.style.width = `${Math.min(100, Math.max(2, stats.free_tier_percent_used))}%`;

    const usedMb = document.getElementById('modalStorageUsedMb');
    if (usedMb) usedMb.innerText = `${stats.total_used_mb} MB`;

    const freeMb = document.getElementById('modalStorageFreeMb');
    if (freeMb) freeMb.innerText = `${stats.free_tier_remaining_mb} MB`;

  } catch (err) {
    console.warn("Could not load storage stats:", err);
  }
}

function openStorageModal() {
  loadStorageStats();
  document.getElementById('storageModal').classList.remove('hidden');
}

function closeStorageModal() {
  document.getElementById('storageModal').classList.add('hidden');
}

async function triggerManualPrune() {
  const btn = document.getElementById('manualPruneBtn');
  const status = document.getElementById('pruneStatusText');
  if (btn) btn.disabled = true;
  if (status) status.innerText = "Pruning expired data & running VACUUM...";

  try {
    const res = await fetch('/api/system/prune?days=15', { method: 'POST' });
    const data = await res.json();
    if (status) {
      status.innerText = `Purged ${data.deleted_videos} videos (${data.deleted_recommendations} calls). VACUUM complete.`;
    }
    loadStorageStats();
    loadGalleryCount();
    if (!document.getElementById('gallerySection').classList.contains('hidden')) {
      loadGalleryVideos();
    }
  } catch (err) {
    if (status) status.innerText = `Prune error: ${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// -------------------------------------------------------------
// API Key (BYOK) Management
// -------------------------------------------------------------
function getSavedApiKey() {
  return localStorage.getItem('gemini_api_key') || '';
}

function updateApiKeyStatusBadge() {
  const key = getSavedApiKey();
  const statusEl = document.getElementById('keyStatusText');
  if (key && key.trim()) {
    statusEl.innerHTML = '<span class="text-emerald-400 font-semibold">● Custom Key</span>';
  } else {
    statusEl.innerText = 'API Key';
  }
}

function openApiKeyModal() {
  document.getElementById('apiKeyInput').value = getSavedApiKey();
  document.getElementById('apiKeyModal').classList.remove('hidden');
}

function closeApiKeyModal() {
  document.getElementById('apiKeyModal').classList.add('hidden');
}

function saveApiKey() {
  const key = document.getElementById('apiKeyInput').value.trim();
  if (key) {
    localStorage.setItem('gemini_api_key', key);
  } else {
    localStorage.removeItem('gemini_api_key');
  }
  updateApiKeyStatusBadge();
  closeApiKeyModal();
}

function clearApiKey() {
  localStorage.removeItem('gemini_api_key');
  document.getElementById('apiKeyInput').value = '';
  updateApiKeyStatusBadge();
  closeApiKeyModal();
}

function setSampleUrl(url) {
  document.getElementById('urlInput').value = url;
}

// -------------------------------------------------------------
// View Switching
// -------------------------------------------------------------
function showSearchView() {
  document.getElementById('heroSection').classList.remove('hidden');
  document.getElementById('gallerySection').classList.add('hidden');
  if (currentVideoReport) {
    document.getElementById('resultsSection').classList.remove('hidden');
  }
}

function toggleGallery() {
  const gallery = document.getElementById('gallerySection');
  const hero = document.getElementById('heroSection');
  const results = document.getElementById('resultsSection');

  if (gallery.classList.contains('hidden')) {
    gallery.classList.remove('hidden');
    hero.classList.add('hidden');
    results.classList.add('hidden');
    loadGalleryVideos();
  } else {
    showSearchView();
  }
}

// -------------------------------------------------------------
// Live Extraction Pipeline (Server-Sent Events)
// -------------------------------------------------------------
function handleExtractSubmit(e) {
  e.preventDefault();
  const url = document.getElementById('urlInput').value.trim();
  if (!url) return;

  const userKey = getSavedApiKey();

  // Reset & show progress section
  document.getElementById('resultsSection').classList.add('hidden');
  document.getElementById('progressSection').classList.remove('hidden');
  document.getElementById('submitBtn').disabled = true;
  document.getElementById('submitBtn').classList.add('opacity-50');

  updateProgress(5, "Connecting to extraction stream...", "step-cache");

  if (eventSource) {
    eventSource.close();
  }

  // Construct SSE URL
  let sseUrl = `/api/stream-extract?url=${encodeURIComponent(url)}`;
  if (userKey) {
    sseUrl += `&api_key=${encodeURIComponent(userKey)}`;
  }

  eventSource = new EventSource(sseUrl);

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const phase = payload.phase;
      const status = payload.status;
      const progress = payload.progress || 10;

      let activeStepId = "step-cache";
      if (phase === "cache_check") activeStepId = "step-cache";
      else if (phase === "metadata") activeStepId = "step-meta";
      else if (phase === "transcript") activeStepId = "step-transcript";
      else if (phase === "llm_analyze") activeStepId = "step-ai";
      else if (phase === "market_validate" || phase === "db_save") activeStepId = "step-db";

      updateProgress(progress, status, activeStepId);

      if (phase === "completed") {
        eventSource.close();
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('submitBtn').classList.remove('opacity-50');

        setTimeout(() => {
          document.getElementById('progressSection').classList.add('hidden');
          renderVideoReport(payload.data);
          loadGalleryCount();
        }, 600);
      } else if (phase === "error") {
        eventSource.close();
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('submitBtn').classList.remove('opacity-50');
        updateProgress(0, `Error: ${payload.error || status}`, activeStepId, true);
      }
    } catch (err) {
      console.error("Failed to parse SSE payload:", err);
    }
  };

  eventSource.onerror = (err) => {
    console.error("SSE Connection error:", err);
    eventSource.close();
    document.getElementById('submitBtn').disabled = false;
    document.getElementById('submitBtn').classList.remove('opacity-50');
    updateProgress(0, "Error: Lost connection to server or extraction timed out.", null, true);
  };
}

function updateProgress(percent, msg, activeStepId, isError = false) {
  const bar = document.getElementById('progressBar');
  const pctText = document.getElementById('progressPercent');
  const statusMsg = document.getElementById('liveStatusMsg');

  bar.style.width = `${percent}%`;
  pctText.innerText = `${percent}%`;
  statusMsg.innerText = msg;

  if (isError) {
    statusMsg.className = "text-rose-400";
    bar.className = "bg-rose-500 h-2.5 rounded-full";
    return;
  } else {
    statusMsg.className = "text-emerald-400";
    bar.className = "bg-gradient-to-r from-emerald-500 to-teal-400 h-2.5 rounded-full transition-all duration-300";
  }

  // Highlight steps
  const steps = ["step-cache", "step-meta", "step-transcript", "step-ai", "step-db"];
  let foundActive = false;

  steps.forEach(sid => {
    const el = document.getElementById(sid);
    if (!el) return;

    if (sid === activeStepId) {
      foundActive = true;
      el.className = "p-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 font-semibold pulse-glow";
    } else if (!foundActive) {
      el.className = "p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200";
    } else {
      el.className = "p-2 rounded-lg bg-slate-800/40 border border-slate-700/40 text-slate-500";
    }
  });
}

// -------------------------------------------------------------
// Report Rendering & Filtering
// -------------------------------------------------------------
function renderVideoReport(report) {
  currentVideoReport = report;

  // Header information
  document.getElementById('videoTitle').innerText = report.title || 'YouTube Video';
  document.getElementById('channelName').innerText = report.channel || 'Unknown Channel';
  document.getElementById('engineBadge').innerText = report.extraction_engine || 'Gemini 3.6 Flash';

  const thumbUrl = report.thumbnail_url || `https://i.ytimg.com/vi/${report.video_id}/hqdefault.jpg`;
  document.getElementById('videoThumb').src = thumbUrl;
  document.getElementById('videoUrlLink').href = report.video_url || `https://www.youtube.com/watch?v=${report.video_id}`;
  document.getElementById('watchLink').href = report.video_url || `https://www.youtube.com/watch?v=${report.video_id}`;

  // Metrics
  const recs = report.recommendations || [];
  document.getElementById('statTotal').innerText = recs.length;
  document.getElementById('statBuy').innerText = report.buy_count || 0;
  document.getElementById('statHold').innerText = report.hold_count || 0;
  document.getElementById('statSell').innerText = report.sell_count || 0;
  document.getElementById('tableCountBadge').innerText = `${recs.length} Calls`;

  // Sector breakdown pills & table
  currentSectorFilter = 'ALL';
  renderSectorPills(recs);
  filterRecommendations();

  // Reveal results
  document.getElementById('resultsSection').classList.remove('hidden');
  document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function renderSectorPills(recommendations) {
  const container = document.getElementById('sectorPillsList');
  if (!container) return;
  container.innerHTML = '';

  if (!recommendations || recommendations.length === 0) {
    document.getElementById('sectorBreakdownContainer').classList.add('hidden');
    return;
  }
  document.getElementById('sectorBreakdownContainer').classList.remove('hidden');

  // Count per sector
  const counts = {};
  recommendations.forEach(r => {
    const s = r.sector || 'Diversified / Other';
    counts[s] = (counts[s] || 0) + 1;
  });

  // "All" pill
  const allBtn = document.createElement('button');
  allBtn.className = currentSectorFilter === 'ALL'
    ? "px-2.5 py-1 rounded-lg text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
    : "px-2.5 py-1 rounded-lg text-xs text-slate-400 hover:text-white bg-slate-900 border border-slate-800 transition";
  allBtn.innerText = `All (${recommendations.length})`;
  allBtn.onclick = () => setSectorFilter('ALL');
  container.appendChild(allBtn);

  // Sector-specific pills sorted by count descending
  const sortedSectors = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  sortedSectors.forEach(sector => {
    const btn = document.createElement('button');
    const isSelected = currentSectorFilter === sector;
    btn.className = isSelected
      ? "px-2.5 py-1 rounded-lg text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
      : "px-2.5 py-1 rounded-lg text-xs text-slate-400 hover:text-white bg-slate-900 border border-slate-800 transition";
    btn.innerHTML = `${sector} <span class="mono opacity-70">(${counts[sector]})</span>`;
    btn.onclick = () => setSectorFilter(sector);
    container.appendChild(btn);
  });
}

function setSectorFilter(sector) {
  currentSectorFilter = sector;
  if (currentVideoReport && currentVideoReport.recommendations) {
    renderSectorPills(currentVideoReport.recommendations);
  }
  filterRecommendations();
}

function setActionFilter(action) {
  currentActionFilter = action;

  ['ALL', 'BUY', 'HOLD', 'SELL'].forEach(a => {
    const btn = document.getElementById(`filter-${a}`);
    if (a === action) {
      btn.className = "px-2.5 py-1 rounded bg-slate-800 font-semibold text-white";
    } else {
      btn.className = "px-2.5 py-1 rounded text-slate-400 hover:text-white";
    }
  });

  filterRecommendations();
}

function filterRecommendations() {
  if (!currentVideoReport || !currentVideoReport.recommendations) return;

  const search = document.getElementById('tableSearchInput').value.toLowerCase().trim();
  const tbody = document.getElementById('recommendationsTableBody');
  tbody.innerHTML = '';

  const filtered = currentVideoReport.recommendations.filter(r => {
    // Action filter
    const act = (r.action || '').toUpperCase();
    if (currentActionFilter === 'BUY' && !act.includes('BUY') && !act.includes('ACCUMULATE')) return false;
    if (currentActionFilter === 'HOLD' && !act.includes('HOLD') && !act.includes('WATCH')) return false;
    if (currentActionFilter === 'SELL' && !act.includes('SELL') && !act.includes('AVOID')) return false;

    // Sector filter
    if (currentSectorFilter !== 'ALL' && (r.sector || 'Diversified / Other') !== currentSectorFilter) return false;

    // Text search
    if (search) {
      const matchTicker = (r.ticker || '').toLowerCase().includes(search);
      const matchSector = (r.sector || '').toLowerCase().includes(search);
      const matchAnalyst = (r.analyst || '').toLowerCase().includes(search);
      const matchQuote = (r.source_quote || '').toLowerCase().includes(search);
      if (!matchTicker && !matchSector && !matchAnalyst && !matchQuote) return false;
    }

    return true;
  });

  document.getElementById('tableCountBadge').innerText = `${filtered.length} Calls`;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="text-center py-8 text-slate-500 text-sm">
          No stock recommendations match the current filter.
        </td>
      </tr>
    `;
    return;
  }

  filtered.forEach(r => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-800/40 transition";

    // Action Badge
    let actionBadge = `<span class="px-2 py-0.5 rounded text-xs font-bold bg-slate-800 text-slate-300">${r.action}</span>`;
    const actUpper = (r.action || '').toUpperCase();
    if (actUpper.includes('BUY') || actUpper.includes('ACCUMULATE')) {
      actionBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${r.action}</span>`;
    } else if (actUpper.includes('SELL') || actUpper.includes('AVOID')) {
      actionBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">${r.action}</span>`;
    } else if (actUpper.includes('HOLD') || actUpper.includes('WATCH')) {
      actionBadge = `<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">${r.action}</span>`;
    }

    // Sector Badge (Interactive filter button)
    const sectorVal = r.sector || 'Diversified / Other';
    const sectorBadge = `<button onclick="setSectorFilter('${sectorVal.replace(/'/g, "\\'")}')" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800 text-cyan-300 hover:bg-slate-700 border border-slate-700/80 transition cursor-pointer" title="Click to filter by ${sectorVal}">${sectorVal}</button>`;

    // Video Timestamp Link
    let timeHtml = `<span class="mono text-xs text-slate-400">${r.timestamp_formatted || '00:00'}</span>`;
    if (r.timestamp_url) {
      timeHtml = `
        <a href="${r.timestamp_url}" target="_blank" class="inline-flex items-center space-x-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 font-mono text-xs transition">
          <svg class="w-3 h-3 text-red-500" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          <span>${r.timestamp_formatted}</span>
        </a>
      `;
    }

    // Stock Ticker with Dialog Modal (click) & Hover Card (preview)
    const tickerName = r.ticker || 'N/A';
    const targetEsc = (r.target || '').replace(/'/g, "\\'");
    const slEsc = (r.stop_loss || '').replace(/'/g, "\\'");
    const actionEsc = (r.action || '').replace(/'/g, "\\'");
    const analystEsc = (r.analyst || '').replace(/'/g, "\\'");
    const horizonEsc = (r.horizon || '').replace(/'/g, "\\'");
    const quoteEsc = (r.source_quote || '').replace(/'/g, "\\'");

    const tickerHtml = `
      <button 
        type="button"
        class="stock-ticker-pill px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-emerald-950/80 border border-slate-700 hover:border-emerald-500/60 cursor-pointer transition inline-flex items-center space-x-1.5 font-bold mono text-emerald-400 group shadow-sm active:scale-95"
        onmouseenter="showStockHoverCard(event, '${tickerName}', '${targetEsc}', '${slEsc}')"
        onmouseleave="startHideHoverCardTimer()"
        onclick="openStockModal(event, '${tickerName}', '${targetEsc}', '${slEsc}', '${actionEsc}', '${analystEsc}', '${horizonEsc}', '${quoteEsc}')"
        title="Click to open full fundamentals dialog (or hover for preview)"
      >
        <span>${tickerName}</span>
        <svg class="w-3.5 h-3.5 text-emerald-400/70 group-hover:text-emerald-300 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
      </button>
    `;

    tr.innerHTML = `
      <td class="px-4 py-3.5 whitespace-nowrap">${tickerHtml}</td>
      <td class="px-4 py-3.5 text-center whitespace-nowrap">${actionBadge}</td>
      <td class="px-4 py-3.5 whitespace-nowrap">${sectorBadge}</td>
      <td class="px-4 py-3.5 text-slate-300 whitespace-nowrap">${r.analyst || 'N/A'}</td>
      <td class="px-4 py-3.5 mono text-rose-400 whitespace-nowrap">${r.stop_loss || 'N/A'}</td>
      <td class="px-4 py-3.5 mono text-emerald-400 font-bold whitespace-nowrap">${r.target || 'N/A'}</td>
      <td class="px-4 py-3.5 text-slate-400 text-xs whitespace-nowrap">${r.horizon || 'N/A'}</td>
      <td class="px-4 py-3.5 text-center whitespace-nowrap">${timeHtml}</td>
      <td class="px-4 py-3.5 text-slate-400 text-xs max-w-xs italic line-clamp-2 hover:line-clamp-none transition" title="${r.source_quote || ''}">
        "${r.source_quote || 'N/A'}"
      </td>
    `;

    tbody.appendChild(tr);
  });
}

// -------------------------------------------------------------
// Export Downloads (.xlsx, .md, .csv, .json)
// -------------------------------------------------------------
function downloadExport(format) {
  if (!currentVideoReport || !currentVideoReport.video_id) {
    alert("No active report loaded to download.");
    return;
  }
  const url = `/api/export/${currentVideoReport.video_id}?format=${format}`;
  window.location.href = url;
}

// -------------------------------------------------------------
// Gallery / Past Analyses Management
// -------------------------------------------------------------
async function loadGalleryCount() {
  try {
    const res = await fetch('/api/videos?limit=1');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('galleryCountBadge').innerText = data.count || 0;
    }
  } catch (e) {}
}

async function loadGalleryVideos() {
  const grid = document.getElementById('galleryGrid');
  grid.innerHTML = '<div class="col-span-3 text-center py-12 text-slate-400">Loading stored reports from database...</div>';

  try {
    const res = await fetch('/api/videos?limit=30');
    if (!res.ok) throw new Error("Failed to fetch gallery");

    const data = await res.json();
    const videos = data.videos || [];

    if (videos.length === 0) {
      grid.innerHTML = `
        <div class="col-span-3 text-center py-12 text-slate-500">
          No reports saved in database yet. Analyze a YouTube video to get started!
        </div>
      `;
      return;
    }

    grid.innerHTML = '';
    videos.forEach(v => {
      const card = document.createElement('div');
      card.className = "p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition shadow-lg flex flex-col justify-between";

      const thumb = v.thumbnail_url || `https://i.ytimg.com/vi/${v.video_id}/hqdefault.jpg`;
      const dateStr = v.created_at ? new Date(v.created_at).toLocaleDateString() : '';

      card.innerHTML = `
        <div>
          <div class="relative rounded-xl overflow-hidden mb-3.5 border border-slate-800 aspect-video">
            <img src="${thumb}" alt="${v.title}" class="w-full h-full object-cover" />
            <div class="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-[10px] mono text-emerald-400 font-bold">
              ${v.total_recommendations} Calls
            </div>
          </div>
          <div class="text-xs text-slate-400 font-medium mb-1">${v.channel} &bull; ${dateStr}</div>
          <h3 class="text-sm font-bold text-white line-clamp-2 mb-3">${v.title}</h3>
        </div>

        <div class="pt-3 border-t border-slate-800 flex items-center justify-between">
          <div class="flex items-center space-x-2 text-xs">
            <span class="text-emerald-400 font-bold">${v.buy_count} Buy</span>
            <span class="text-slate-600">&bull;</span>
            <span class="text-amber-400 font-bold">${v.hold_count} Hold</span>
            <span class="text-slate-600">&bull;</span>
            <span class="text-rose-400 font-bold">${v.sell_count} Sell</span>
          </div>
          <button onclick="loadSavedVideo('${v.video_id}')" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition">
            View Report
          </button>
        </div>
      `;

      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<div class="col-span-3 text-center py-12 text-rose-400">Failed to load reports: ${err.message}</div>`;
  }
}

async function loadSavedVideo(videoId) {
  try {
    const res = await fetch(`/api/videos/${videoId}`);
    if (!res.ok) throw new Error("Could not load report");
    const data = await res.json();
    showSearchView();
    renderVideoReport(data);
  } catch (err) {
    alert("Error loading video report: " + err.message);
  }
}

// -------------------------------------------------------------
// Live Stock Dialog Modal & Hover Preview (CMP, Fundamentals, Sparkline)
// -------------------------------------------------------------
const stockQuoteClientCache = {};
let hoverHideTimer = null;
let isHoverCardPinned = false;
let currentHoverTicker = null;

// Fix hover card positioning using strict viewport coordinates (no scroll offset)
function showStockHoverCard(event, ticker, targetStr, slStr) {
  // Do not pop up hover card if the full modal dialog is currently open
  const modal = document.getElementById('stockModal');
  if (modal && !modal.classList.contains('hidden')) return;

  if (isHoverCardPinned && currentHoverTicker === ticker) return;
  if (hoverHideTimer) {
    clearTimeout(hoverHideTimer);
    hoverHideTimer = null;
  }

  currentHoverTicker = ticker;
  const card = document.getElementById('stockHoverCard');
  if (!card) return;

  // Position card near trigger button relative to the viewport
  const rect = event.currentTarget.getBoundingClientRect();
  const cardWidth = 320;
  const cardHeight = 310;

  // Viewport-relative horizontal positioning
  let left = rect.left;
  if (left + cardWidth > window.innerWidth - 16) {
    left = window.innerWidth - cardWidth - 16;
  }
  if (left < 16) left = 16;

  // Viewport-relative vertical positioning
  let top = rect.bottom + 8;
  if (top + cardHeight > window.innerHeight - 12) {
    top = Math.max(12, rect.top - cardHeight - 8);
  }

  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
  card.classList.remove('hidden');

  // Populate immediate known data
  document.getElementById('hoverTicker').innerText = ticker;
  document.getElementById('hoverName').innerText = "Fetching live quote...";
  document.getElementById('hoverCmp').innerHTML = '<span class="text-xs text-slate-400 animate-pulse">Loading...</span>';
  document.getElementById('hoverChange').innerText = "";
  document.getElementById('hoverSparkline').innerHTML = '<div class="text-[10px] text-slate-500 animate-pulse">Loading 30-day trend...</div>';

  // Check client cache
  if (stockQuoteClientCache[ticker]) {
    renderHoverCardData(stockQuoteClientCache[ticker], targetStr, slStr);
    return;
  }

  // Fetch from backend API
  fetch(`/api/stocks/${encodeURIComponent(ticker)}/quote`)
    .then(res => res.ok ? res.json() : Promise.reject(new Error("Failed to load quote")))
    .then(data => {
      stockQuoteClientCache[ticker] = data;
      if (currentHoverTicker === ticker) {
        renderHoverCardData(data, targetStr, slStr);
      }
    })
    .catch(err => {
      if (currentHoverTicker === ticker) {
        document.getElementById('hoverName').innerText = "Quote unavailable";
        document.getElementById('hoverCmp').innerText = "N/A";
        document.getElementById('hoverSparkline').innerHTML = '<div class="text-[10px] text-slate-600">No chart data</div>';
      }
    });
}

function renderHoverCardData(quote, targetStr, slStr) {
  document.getElementById('hoverTicker').innerText = quote.ticker || '';
  document.getElementById('hoverName').innerText = quote.name || quote.ticker;
  document.getElementById('hoverSector').innerText = quote.sector || 'Diversified / Other';
  document.getElementById('hoverExchange').innerText = quote.exchange || 'NSE';

  // CMP & Change
  if (quote.cmp !== null && quote.cmp !== undefined) {
    document.getElementById('hoverCmp').innerText = `₹${quote.cmp.toLocaleString('en-IN')}`;
    const chgPct = quote.change_percent || 0.0;
    const isUp = chgPct >= 0;
    const chgSign = isUp ? '+' : '';
    const chgClass = isUp ? 'text-emerald-400' : 'text-rose-400';
    document.getElementById('hoverChange').className = `text-[11px] font-bold mono ${chgClass}`;
    document.getElementById('hoverChange').innerText = `${chgSign}${chgPct.toFixed(2)}% (${chgSign}₹${(quote.change || 0).toFixed(2)})`;
  } else {
    document.getElementById('hoverCmp').innerText = "Unlisted";
    document.getElementById('hoverChange').innerText = "Pre-IPO / Private";
    document.getElementById('hoverChange').className = "text-[11px] font-medium text-slate-400";
  }

  // Upside Potential calculation
  const upsideContainer = document.getElementById('hoverUpsideContainer');
  const upsideBadge = document.getElementById('hoverUpsideBadge');
  const gaugeCmp = document.getElementById('hoverGaugeCmp');
  const gaugeTarget = document.getElementById('hoverGaugeTarget');

  const targetClean = (targetStr || '').replace(/[^0-9.]/g, '');
  const targetNum = parseFloat(targetClean);

  if (quote.cmp && !isNaN(targetNum) && targetNum > 0) {
    const upsidePct = (((targetNum - quote.cmp) / quote.cmp) * 100);
    const isUpside = upsidePct >= 0;
    const sign = isUpside ? '+' : '';
    upsideBadge.innerText = `${sign}${upsidePct.toFixed(1)}% ${isUpside ? 'Upside' : 'Downside'}`;
    upsideBadge.className = `font-bold mono ${isUpside ? 'text-emerald-400' : 'text-rose-400'}`;
    gaugeCmp.innerText = `₹${quote.cmp.toLocaleString('en-IN')}`;
    gaugeTarget.innerText = `₹${targetNum.toLocaleString('en-IN')}`;
    upsideContainer.classList.remove('hidden');
  } else {
    upsideContainer.classList.add('hidden');
  }

  // Sparkline Chart
  const sparklineEl = document.getElementById('hoverSparkline');
  if (quote.sparkline && quote.sparkline.length > 1) {
    const isPositive = (quote.change_percent || 0) >= 0;
    sparklineEl.innerHTML = generateSparklineSvg(quote.sparkline, isPositive, 280, 40);
  } else {
    sparklineEl.innerHTML = '<div class="text-[10px] text-slate-500">No recent trend history</div>';
  }

  // 6 Fundamentals
  document.getElementById('hoverPe').innerText = quote.pe_ratio !== null && quote.pe_ratio !== undefined ? quote.pe_ratio : '--';
  document.getElementById('hoverPb').innerText = quote.pb_ratio !== null && quote.pb_ratio !== undefined ? quote.pb_ratio : '--';
  document.getElementById('hoverDivYield').innerText = quote.dividend_yield !== null && quote.dividend_yield !== undefined ? `${quote.dividend_yield}%` : '--';
  document.getElementById('hoverMcap').innerText = quote.market_cap_cr !== null && quote.market_cap_cr !== undefined ? `₹${quote.market_cap_cr.toLocaleString('en-IN')} Cr` : '--';
  document.getElementById('hover52High').innerText = quote.week_52_high !== null && quote.week_52_high !== undefined ? `₹${quote.week_52_high.toLocaleString('en-IN')}` : '--';
  document.getElementById('hover52Low').innerText = quote.week_52_low !== null && quote.week_52_low !== undefined ? `₹${quote.week_52_low.toLocaleString('en-IN')}` : '--';
}

function startHideHoverCardTimer() {
  if (isHoverCardPinned) return;
  hoverHideTimer = setTimeout(() => {
    hideStockHoverCard();
  }, 280);
}

function keepHoverCard() {
  if (hoverHideTimer) {
    clearTimeout(hoverHideTimer);
    hoverHideTimer = null;
  }
}

function hideStockHoverCard(force = false) {
  if (isHoverCardPinned && !force) return;
  const card = document.getElementById('stockHoverCard');
  if (card) {
    card.classList.add('hidden');
  }
  isHoverCardPinned = false;
  currentHoverTicker = null;
}

// -------------------------------------------------------------
// Interactive Stock Details Modal Dialog (Triggered on Ticker Click)
// -------------------------------------------------------------
function openStockModal(event, ticker, targetStr, slStr, actionStr, analystStr, horizonStr, quoteStr) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  // Dismiss floating hover card so it doesn't overlap modal
  hideStockHoverCard(true);

  const modal = document.getElementById('stockModal');
  if (!modal) return;

  // Header data
  document.getElementById('modalTicker').innerText = ticker || 'N/A';
  document.getElementById('modalName').innerText = "Fetching live quote...";
  document.getElementById('modalSector').innerText = "Loading sector...";
  document.getElementById('modalExchange').innerText = "NSE";

  // Recommendation call context from video
  const actUpper = (actionStr || '').toUpperCase();
  let actClass = "bg-slate-800 text-slate-300 border-slate-700";
  if (actUpper.includes('BUY') || actUpper.includes('ACCUMULATE')) {
    actClass = "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
  } else if (actUpper.includes('SELL') || actUpper.includes('AVOID')) {
    actClass = "bg-rose-500/15 text-rose-400 border-rose-500/30";
  } else if (actUpper.includes('HOLD') || actUpper.includes('WATCH')) {
    actClass = "bg-amber-500/15 text-amber-400 border-amber-500/30";
  }
  const modalActionBadge = document.getElementById('modalActionBadge');
  if (modalActionBadge) {
    modalActionBadge.className = `px-2.5 py-0.5 rounded-full text-xs font-bold border ${actClass}`;
    modalActionBadge.innerText = actionStr || 'N/A';
  }

  document.getElementById('modalTarget').innerText = targetStr || 'N/A';
  document.getElementById('modalStopLoss').innerText = slStr || 'N/A';
  document.getElementById('modalCmpSmall').innerText = '...';

  const analystLabel = document.getElementById('modalAnalystLabel');
  if (analystLabel) analystLabel.innerText = analystStr ? `${analystStr}:` : 'Analyst:';
  const quoteText = document.getElementById('modalQuoteText');
  if (quoteText) quoteText.innerText = quoteStr ? `"${quoteStr}"` : 'No direct quote captured.';

  // External links
  const tvLink = document.getElementById('modalTradingViewLink');
  if (tvLink) tvLink.href = `https://in.tradingview.com/symbols/NSE-${encodeURIComponent(ticker)}/`;
  const gfLink = document.getElementById('modalGoogleFinanceLink');
  if (gfLink) gfLink.href = `https://www.google.com/finance/quote/${encodeURIComponent(ticker)}:NSE`;

  // Reset live fields to loading state
  document.getElementById('modalCmp').innerHTML = '<span class="animate-pulse text-slate-400 text-lg">Loading CMP...</span>';
  document.getElementById('modalChange').innerText = "";
  document.getElementById('modalPrevClose').innerText = "Prev: --";
  document.getElementById('modalUpsideBadge').innerText = "Calculating potential...";
  document.getElementById('modalSparkline').innerHTML = '<div class="text-xs text-slate-500 animate-pulse">Loading 30-day price trend...</div>';
  document.getElementById('modal30dLow').innerText = '--';
  document.getElementById('modal30dHigh').innerText = '--';

  ['modalPe', 'modalPb', 'modalDivYield', 'modalMcap', 'modal52High', 'modal52Low'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerText = '--';
  });

  // Reveal modal dialog
  modal.classList.remove('hidden');

  // Check client cache first for instant rendering
  if (stockQuoteClientCache[ticker]) {
    renderStockModalData(stockQuoteClientCache[ticker], targetStr, slStr);
    return;
  }

  // Fetch live quote and fundamentals from backend
  fetch(`/api/stocks/${encodeURIComponent(ticker)}/quote`)
    .then(res => res.ok ? res.json() : Promise.reject(new Error("Failed to load quote")))
    .then(quote => {
      stockQuoteClientCache[ticker] = quote;
      renderStockModalData(quote, targetStr, slStr);
    })
    .catch(err => {
      document.getElementById('modalName').innerText = "Quote unavailable";
      document.getElementById('modalCmp').innerText = "N/A";
      document.getElementById('modalChange').innerText = "Unlisted / Offline";
      document.getElementById('modalSparkline').innerHTML = '<div class="text-xs text-slate-600">No chart data available</div>';
    });
}

function renderStockModalData(quote, targetStr, slStr) {
  document.getElementById('modalTicker').innerText = quote.ticker || '';
  document.getElementById('modalName').innerText = quote.name || quote.ticker;
  document.getElementById('modalSector').innerText = quote.sector || 'Diversified / Other';
  document.getElementById('modalExchange').innerText = quote.exchange || 'NSE';

  // CMP & Day's Change
  if (quote.cmp !== null && quote.cmp !== undefined) {
    document.getElementById('modalCmp').innerText = `₹${quote.cmp.toLocaleString('en-IN')}`;
    document.getElementById('modalCmpSmall').innerText = `₹${quote.cmp.toLocaleString('en-IN')}`;
    const chgPct = quote.change_percent || 0.0;
    const isUp = chgPct >= 0;
    const chgSign = isUp ? '+' : '';
    const chgClass = isUp ? 'text-emerald-400' : 'text-rose-400';
    document.getElementById('modalChange').className = `text-base font-bold mono ${chgClass}`;
    document.getElementById('modalChange').innerText = `${chgSign}${chgPct.toFixed(2)}% (${chgSign}₹${(quote.change || 0).toFixed(2)})`;
    if (quote.previous_close) {
      document.getElementById('modalPrevClose').innerText = `Prev Close: ₹${quote.previous_close.toLocaleString('en-IN')}`;
    } else {
      document.getElementById('modalPrevClose').innerText = `Prev: --`;
    }
  } else {
    document.getElementById('modalCmp').innerText = "Unlisted";
    document.getElementById('modalCmpSmall').innerText = "N/A";
    document.getElementById('modalChange').innerText = "Pre-IPO / Private";
    document.getElementById('modalChange').className = "text-sm font-medium text-slate-400";
    document.getElementById('modalPrevClose').innerText = "";
  }

  // Target Upside Potential calculation
  const targetClean = (targetStr || '').replace(/[^0-9.]/g, '');
  const targetNum = parseFloat(targetClean);
  const upsideBadge = document.getElementById('modalUpsideBadge');

  if (quote.cmp && !isNaN(targetNum) && targetNum > 0) {
    const upsidePct = (((targetNum - quote.cmp) / quote.cmp) * 100);
    const isUpside = upsidePct >= 0;
    const sign = isUpside ? '+' : '';
    upsideBadge.innerText = `${sign}${upsidePct.toFixed(1)}% ${isUpside ? 'Upside' : 'Downside'} Potential`;
    upsideBadge.className = `text-xs font-bold mono ${isUpside ? 'text-emerald-400' : 'text-rose-400'}`;
  } else {
    upsideBadge.innerText = "Target N/A";
    upsideBadge.className = "text-xs font-medium mono text-slate-400";
  }

  // 30-Day SVG Sparkline Chart with Range Min/Max
  const sparklineEl = document.getElementById('modalSparkline');
  const lowEl = document.getElementById('modal30dLow');
  const highEl = document.getElementById('modal30dHigh');

  if (quote.sparkline && quote.sparkline.length > 1) {
    const isPositive = (quote.change_percent || 0) >= 0;
    sparklineEl.innerHTML = generateSparklineSvg(quote.sparkline, isPositive, 440, 56);
    const minP = Math.min(...quote.sparkline);
    const maxP = Math.max(...quote.sparkline);
    if (lowEl) lowEl.innerText = `₹${minP.toLocaleString('en-IN')}`;
    if (highEl) highEl.innerText = `₹${maxP.toLocaleString('en-IN')}`;
  } else {
    sparklineEl.innerHTML = '<div class="text-xs text-slate-500">No historical trend available</div>';
    if (lowEl) lowEl.innerText = '--';
    if (highEl) highEl.innerText = '--';
  }

  // 6 Valuation Fundamentals
  document.getElementById('modalPe').innerText = (quote.pe_ratio !== null && quote.pe_ratio !== undefined) ? quote.pe_ratio : '--';
  document.getElementById('modalPb').innerText = (quote.pb_ratio !== null && quote.pb_ratio !== undefined) ? quote.pb_ratio : '--';
  document.getElementById('modalDivYield').innerText = (quote.dividend_yield !== null && quote.dividend_yield !== undefined) ? `${quote.dividend_yield}%` : '--';
  document.getElementById('modalMcap').innerText = (quote.market_cap_cr !== null && quote.market_cap_cr !== undefined) ? `₹${quote.market_cap_cr.toLocaleString('en-IN')} Cr` : '--';
  document.getElementById('modal52High').innerText = (quote.week_52_high !== null && quote.week_52_high !== undefined) ? `₹${quote.week_52_high.toLocaleString('en-IN')}` : '--';
  document.getElementById('modal52Low').innerText = (quote.week_52_low !== null && quote.week_52_low !== undefined) ? `₹${quote.week_52_low.toLocaleString('en-IN')}` : '--';
}

function closeStockModal() {
  const modal = document.getElementById('stockModal');
  if (modal) modal.classList.add('hidden');
}

function handleStockModalBackdropClick(event) {
  if (event.target && event.target.id === 'stockModal') {
    closeStockModal();
  }
}

// -------------------------------------------------------------
// SVG Sparkline Chart Generator
// -------------------------------------------------------------
function generateSparklineSvg(prices, isPositive = true, w = 280, h = 40) {
  if (!prices || prices.length < 2) return '';
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = (max - min) || 1;
  const padding = 3;

  const points = prices.map((p, idx) => {
    const x = padding + (idx / (prices.length - 1)) * (w - 2 * padding);
    const y = h - padding - ((p - min) / range) * (h - 2 * padding);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const strokeColor = isPositive ? "#34d399" : "#f87171";
  const gradId = `sparkGrad-${Math.random().toString(36).substring(2, 8)}`;
  const firstX = padding;
  const lastX = w - padding;
  const bottomY = h;
  const areaPath = `M ${firstX},${bottomY} L ${points.join(' L ')} L ${lastX},${bottomY} Z`;

  return `
    <svg viewBox="0 0 ${w} ${h}" class="w-full h-full overflow-visible">
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.25"/>
          <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="${areaPath}" fill="url(#${gradId})" />
      <polyline fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${points.join(' ')}" />
    </svg>
  `;
}

// Dismiss pinned hover card when clicking outside
document.addEventListener('click', (e) => {
  const card = document.getElementById('stockHoverCard');
  if (card && !card.classList.contains('hidden') && !card.contains(e.target)) {
    hideStockHoverCard(true);
  }
});

// Escape key dismisses open modals & hover card
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeStockModal();
    hideStockHoverCard(true);
    closeStorageModal();
    closeApiKeyModal();
  }
});


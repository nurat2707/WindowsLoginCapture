/**
 * app.js
 * Frontend controller for Windows Login Capture - Google Photos styled UI.
 * Connects directly to Python backend via pywebview JS API.
 */

let allIncidents = [];
let currentFiltered = [];
let currentLightboxIndex = 0;
let isSettingsUnlocked = false;
let pendingPinAction = null; // Callback when PIN is verified

// Wait for pywebview API to be ready
window.addEventListener('pywebviewready', () => {
  initApp();
});

// Fallback for browser preview/testing
document.addEventListener('DOMContentLoaded', () => {
  if (!window.pywebview) {
    console.log("Running in standard browser (pywebview API not yet attached)");
    setTimeout(initApp, 400);
  }
});

let appInitialized = false;

async function initApp() {
  if (appInitialized) return;
  appInitialized = true;

  initPinBoxes();
  await refreshServiceStatus();
  await loadIncidents();
  await loadSettingsData();

  // Search filter listener
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', handleSearch);
  }

  // Keyboard navigation for Lightbox & PIN
  document.addEventListener('keydown', (e) => {
    const lightbox = document.getElementById('lightboxModal');
    if (lightbox && lightbox.style.display !== 'none') {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft') prevIncident();
      if (e.key === 'ArrowRight') nextIncident();
    }

    const pinModal = document.getElementById('pinModal');
    if (pinModal && pinModal.style.display !== 'none') {
      if (e.key === 'Escape') closePinModal();
      if (e.key === 'Enter') submitPin();
    }
  });

  // Service toggle click listener
  const servicePill = document.getElementById('servicePill');
  if (servicePill) {
    servicePill.addEventListener('click', requestServiceToggle);
  }

  // Header double-click to maximize/restore cleanly
  const header = document.querySelector('.app-header');
  if (header) {
    header.addEventListener('dblclick', (e) => {
      if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON' && !e.target.closest('button') && !e.target.closest('.service-pill')) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_maximize) {
          window.pywebview.api.toggle_maximize();
        }
      }
    });
  }

  // Reload dynamically when user unlocks PC or focuses window
  window.addEventListener('focus', async () => {
    await loadIncidents();
    await refreshServiceStatus();
  });

  document.addEventListener('visibilitychange', async () => {
    if (!document.hidden) {
      await loadIncidents();
      await refreshServiceStatus();
    }
  });

  // Background silent polling every 2.5s - NO MORE MANUAL REFRESH NEEDED!
  setInterval(async () => {
    const lightbox = document.getElementById('lightboxModal');
    const pinModal = document.getElementById('pinModal');
    const isModalOpen = (lightbox && lightbox.style.display !== 'none') || 
                        (pinModal && pinModal.style.display !== 'none');
    if (!isModalOpen) {
      await pollIncidentsSilently();
    }
  }, 2500);
}

async function pollIncidentsSilently() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const fresh = await window.pywebview.api.get_incidents();
    if (!fresh || !Array.isArray(fresh)) return;

    let changed = false;
    if (fresh.length !== allIncidents.length) {
      changed = true;
    } else if (fresh.length > 0 && allIncidents.length > 0) {
      if (fresh[0].id !== allIncidents[0].id) {
        changed = true;
      } else {
        for (let i = 0; i < fresh.length; i++) {
          if (fresh[i].reviewed_by_user !== allIncidents[i].reviewed_by_user ||
              fresh[i].city !== allIncidents[i].city) {
            changed = true;
            break;
          }
        }
      }
    }

    if (changed) {
      allIncidents = fresh;
      populateDropdowns(allIncidents);
      applyAllFilters();
      checkBreachBanner(allIncidents);
    }
  } catch (err) {
    console.error("Silent poll error:", err);
  }
}

// ================= NAVIGATION =================
function switchTab(tabName) {
  const btnGallery = document.getElementById('tabGalleryBtn');
  const btnSettings = document.getElementById('tabSettingsBtn');
  const viewGallery = document.getElementById('viewGallery');
  const viewSettings = document.getElementById('viewSettings');

  if (tabName === 'gallery') {
    btnGallery.classList.add('active');
    btnSettings.classList.remove('active');
    viewGallery.classList.add('active');
    viewSettings.classList.remove('active');
  } else if (tabName === 'settings') {
    btnGallery.classList.remove('active');
    btnSettings.classList.add('active');
    viewGallery.classList.remove('active');
    viewSettings.classList.add('active');
    loadSettingsData();
  }
}

function requestSettingsAccess() {
  if (isSettingsUnlocked) {
    switchTab('settings');
    return;
  }

  // Check if PIN exists
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.has_pin().then((hasPin) => {
      if (!hasPin) {
        isSettingsUnlocked = true;
        switchTab('settings');
      } else {
        openPinModal(
          "Unlock Settings",
          "Enter your Master PIN to view and modify security settings.",
          () => {
            isSettingsUnlocked = true;
            switchTab('settings');
          }
        );
      }
    });
  } else {
    switchTab('settings');
  }
}

// ================= LOAD & RENDER INCIDENTS =================
async function loadIncidents() {
  try {
    if (window.pywebview && window.pywebview.api) {
      allIncidents = await window.pywebview.api.get_incidents();
    } else {
      allIncidents = [];
    }
  } catch (err) {
    console.error("Error loading incidents:", err);
    allIncidents = [];
  }

  currentFiltered = [...allIncidents];
  populateDropdowns(allIncidents);
  applyAllFilters();
  checkBreachBanner(allIncidents);
}

function renderGallery(incidents) {
  const container = document.getElementById('timelineContainer');
  const emptyState = document.getElementById('emptyState');
  const totalCountLbl = document.getElementById('totalIncidentsCount');
  const emptyTitle = document.getElementById('emptyStateTitle');
  const emptyDesc = document.getElementById('emptyStateDesc');
  const emptyResetBtn = document.getElementById('emptyStateResetBtn');

  // Clear timeline (keep empty state)
  container.querySelectorAll('.timeline-group').forEach(el => el.remove());

  if (incidents.length === 0) {
    emptyState.style.display = 'flex';
    if (allIncidents.length > 0) {
      if (emptyTitle) emptyTitle.textContent = "No Matching Incidents";
      if (emptyDesc) emptyDesc.textContent = "No intruder events match your selected date or filter criteria.";
      if (emptyResetBtn) emptyResetBtn.style.display = 'inline-flex';
    } else {
      if (emptyTitle) emptyTitle.textContent = "Everything is Secure";
      if (emptyDesc) emptyDesc.textContent = "No unauthorized login attempts have been recorded on this machine.";
      if (emptyResetBtn) emptyResetBtn.style.display = 'none';
    }
    return;
  }
  emptyState.style.display = 'none';

  // Group by relative date (e.g. Today, Yesterday, or exact Date)
  const groups = groupIncidentsByDate(incidents);

  for (const [groupTitle, groupItems] of Object.entries(groups)) {
    const groupEl = document.createElement('div');
    groupEl.className = 'timeline-group';

    const headerEl = document.createElement('div');
    headerEl.className = 'timeline-header';
    headerEl.innerHTML = `
      <span>${groupTitle}</span>
      <span class="incident-count-tag">• ${groupItems.length} attempt${groupItems.length === 1 ? '' : 's'}</span>
    `;
    groupEl.appendChild(headerEl);

    const gridEl = document.createElement('div');
    gridEl.className = 'photo-grid';

    groupItems.forEach((item) => {
      const card = createPhotoCard(item);
      gridEl.appendChild(card);
    });

    groupEl.appendChild(gridEl);
    container.appendChild(groupEl);
  }
}

function createPhotoCard(item) {
  const card = document.createElement('div');
  card.className = 'photo-card';

  // Format time (e.g. 10:15 PM)
  const timeStr = formatShortTime(item.detected_at);

  let imgMarkup = '';
  if (item.image_base64) {
    imgMarkup = `<img src="data:image/jpeg;base64,${item.image_base64}" alt="Intruder Photo" loading="lazy" />`;
  } else {
    imgMarkup = `
      <div class="no-img-placeholder">
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19 4h-3.5L14 2H10L8.5 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
        </svg>
        <span>No photo captured</span>
      </div>`;
  }

  const unreviewedBadge = (!item.reviewed_by_user)
    ? `<span class="unreviewed-badge">New</span>`
    : '';

  card.innerHTML = `
    ${imgMarkup}
    <div class="photo-overlay">
      <div class="overlay-top">
        <span class="time-chip">${timeStr}</span>
        ${unreviewedBadge}
      </div>
      <div class="overlay-bottom">
        <span class="user-badge">${item.username || 'Standard Account'}</span>
        <span class="location-chip">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          ${item.city || 'Offline / Unknown'}
        </span>
      </div>
    </div>
  `;

  card.addEventListener('click', () => {
    openLightboxByItem(item);
  });

  return card;
}

// ================= DATE GROUPING UTILITY =================
function groupIncidentsByDate(incidents) {
  const groups = {};
  const todayStr = new Date().toDateString();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();

  incidents.forEach(item => {
    let d;
    try {
      d = new Date(item.detected_at.replace(" ", "T"));
    } catch {
      d = new Date();
    }
    const itemDateStr = d.toDateString();

    let label = itemDateStr;
    if (itemDateStr === todayStr) {
      label = "Today";
    } else if (itemDateStr === yesterdayStr) {
      label = "Yesterday";
    } else {
      label = d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
    }

    if (!groups[label]) groups[label] = [];
    groups[label].push(item);
  });

  return groups;
}

function formatShortTime(isoOrStr) {
  try {
    const d = new Date(isoOrStr.replace(" ", "T"));
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
  } catch {
    return isoOrStr.split(" ")[1] || isoOrStr;
  }
}

// ================= FILTERING & SEARCH ENGINE (Google Photos style) =================
let activeDateFilter = 'all'; // 'all', 'today', 'yesterday', 'week', 'month', 'custom'
let activeUserFilter = 'all';
let activeCityFilter = 'all';
let activeUnreviewedOnly = false;
let customDateRange = { start: null, end: null };

function populateDropdowns(incidents) {
  // 1. Account Dropdown
  const userSelect = document.getElementById('userFilterSelect');
  if (userSelect) {
    const currentVal = userSelect.value;
    userSelect.innerHTML = '<option value="all">All Accounts</option>';
    const users = new Set();
    incidents.forEach(i => {
      if (i.username) users.add(i.username);
    });
    users.forEach(u => {
      const opt = document.createElement('option');
      opt.value = u;
      opt.textContent = u;
      userSelect.appendChild(opt);
    });
    if (users.has(currentVal)) {
      userSelect.value = currentVal;
    }
  }

  // 2. Location Dropdown
  const citySelect = document.getElementById('cityFilterSelect');
  if (citySelect) {
    const currentVal = citySelect.value;
    citySelect.innerHTML = '<option value="all">All Locations</option>';
    const cities = new Set();
    incidents.forEach(i => {
      if (i.city && i.city !== 'Unknown') cities.add(i.city);
    });
    cities.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      citySelect.appendChild(opt);
    });
    if (cities.has(currentVal)) {
      citySelect.value = currentVal;
    }
  }
}

function setDateFilter(type, btnEl) {
  activeDateFilter = type;
  
  // Update chip active classes
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  // Close custom popover if picking preset
  const popover = document.getElementById('datePopover');
  if (popover && type !== 'custom') {
    popover.style.display = 'none';
    document.getElementById('customDateChipLabel').textContent = 'Custom Range';
    customDateRange = { start: null, end: null };
  }

  applyAllFilters();
}

function toggleCustomDatePicker(e) {
  if (e) e.stopPropagation();
  const popover = document.getElementById('datePopover');
  const chip = document.getElementById('chipCustom');
  if (!popover || !chip) return;
  
  const isHidden = popover.style.display === 'none' || !popover.style.display;
  if (isHidden) {
    const filterBar = document.querySelector('.filter-bar');
    if (filterBar) {
      const chipRect = chip.getBoundingClientRect();
      const barRect = filterBar.getBoundingClientRect();
      const offsetLeft = chipRect.left - barRect.left;
      popover.style.left = `${Math.max(10, offsetLeft)}px`;
    }
    popover.style.display = 'block';
  } else {
    popover.style.display = 'none';
  }
}

function applyCustomDateRange() {
  const startVal = document.getElementById('startDateInput').value;
  const endVal = document.getElementById('endDateInput').value;

  if (!startVal && !endVal) {
    setDateFilter('all', document.getElementById('chipAll'));
    return;
  }

  customDateRange.start = startVal ? new Date(startVal + 'T00:00:00') : null;
  customDateRange.end = endVal ? new Date(endVal + 'T23:59:59') : null;

  activeDateFilter = 'custom';
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  document.getElementById('chipCustom').classList.add('active');

  // Format label: e.g. "Sep 1 – Sep 26" or "From Sep 1"
  let label = "Custom Range";
  if (startVal && endVal) {
    const sFmt = new Date(startVal + 'T00:00:00').toLocaleDateString([], { month: 'short', day: 'numeric' });
    const eFmt = new Date(endVal + 'T00:00:00').toLocaleDateString([], { month: 'short', day: 'numeric' });
    label = `${sFmt} – ${eFmt}`;
  } else if (startVal) {
    const sFmt = new Date(startVal + 'T00:00:00').toLocaleDateString([], { month: 'short', day: 'numeric' });
    label = `From ${sFmt}`;
  } else if (endVal) {
    const eFmt = new Date(endVal + 'T00:00:00').toLocaleDateString([], { month: 'short', day: 'numeric' });
    label = `Until ${eFmt}`;
  }
  document.getElementById('customDateChipLabel').textContent = label;

  document.getElementById('datePopover').style.display = 'none';
  applyAllFilters();
}

function clearCustomDateRange() {
  document.getElementById('startDateInput').value = '';
  document.getElementById('endDateInput').value = '';
  document.getElementById('datePopover').style.display = 'none';
  setDateFilter('all', document.getElementById('chipAll'));
}

function onUserFilterChange() {
  const sel = document.getElementById('userFilterSelect');
  activeUserFilter = sel ? sel.value : 'all';
  applyAllFilters();
}

function onCityFilterChange() {
  const sel = document.getElementById('cityFilterSelect');
  activeCityFilter = sel ? sel.value : 'all';
  applyAllFilters();
}

function toggleUnreviewedFilter() {
  activeUnreviewedOnly = !activeUnreviewedOnly;
  const chip = document.getElementById('chipUnreviewedOnly');
  if (chip) {
    chip.classList.toggle('active', activeUnreviewedOnly);
  }
  applyAllFilters();
}

function handleSearch(e) {
  applyAllFilters();
}

function applyAllFilters() {
  const searchInput = document.getElementById('searchInput');
  const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  currentFiltered = allIncidents.filter(item => {
    // 1. Text Search Filter (User, City, IP, or Timestamp)
    if (query) {
      const u = (item.username || '').toLowerCase();
      const c = (item.city || '').toLowerCase();
      const ip = (item.public_ip || '').toLowerCase();
      const t = (item.detected_at || '').toLowerCase();
      if (!u.includes(query) && !c.includes(query) && !ip.includes(query) && !t.includes(query)) {
        return false;
      }
    }

    // 2. Account Filter
    if (activeUserFilter !== 'all') {
      if (item.username !== activeUserFilter) {
        return false;
      }
    }

    // 3. Location / City Filter
    if (activeCityFilter !== 'all') {
      if (item.city !== activeCityFilter) {
        return false;
      }
    }

    // 4. Unreviewed Only Filter
    if (activeUnreviewedOnly) {
      if (item.reviewed_by_user) {
        return false;
      }
    }

    // 5. Date Filter
    let itemDate;
    try {
      itemDate = new Date(item.detected_at.replace(' ', 'T'));
    } catch {
      itemDate = new Date();
    }
    const itemDay = new Date(itemDate.getFullYear(), itemDate.getMonth(), itemDate.getDate()).getTime();

    if (activeDateFilter === 'today') {
      if (itemDay !== today.getTime()) return false;
    } else if (activeDateFilter === 'yesterday') {
      if (itemDay !== yesterday.getTime()) return false;
    } else if (activeDateFilter === 'week') {
      if (itemDate < sevenDaysAgo) return false;
    } else if (activeDateFilter === 'month') {
      if (itemDate < thirtyDaysAgo) return false;
    } else if (activeDateFilter === 'custom') {
      if (customDateRange.start && itemDate < customDateRange.start) return false;
      if (customDateRange.end && itemDate > customDateRange.end) return false;
    }

    return true;
  });

  // Dynamic Count label (e.g. "2 of 4 Incidents" when filtered)
  const totalCountLbl = document.getElementById('totalIncidentsCount');
  const isFiltered = (activeDateFilter !== 'all' || activeUserFilter !== 'all' || activeCityFilter !== 'all' || activeUnreviewedOnly || query);
  
  if (totalCountLbl) {
    if (isFiltered) {
      totalCountLbl.textContent = `${currentFiltered.length} of ${allIncidents.length} Incident${allIncidents.length === 1 ? '' : 's'}`;
    } else {
      totalCountLbl.textContent = `${allIncidents.length} Incident${allIncidents.length === 1 ? '' : 's'}`;
    }
  }

  // Show/Hide Reset Filters button if any filter is active
  const resetBtn = document.getElementById('btnResetFilters');
  if (resetBtn) {
    resetBtn.style.display = isFiltered ? 'inline-flex' : 'none';
  }

  renderGallery(currentFiltered);
}

function resetAllFilters() {
  activeDateFilter = 'all';
  activeUserFilter = 'all';
  activeCityFilter = 'all';
  activeUnreviewedOnly = false;
  customDateRange = { start: null, end: null };

  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = '';

  const userSelect = document.getElementById('userFilterSelect');
  if (userSelect) userSelect.value = 'all';

  const citySelect = document.getElementById('cityFilterSelect');
  if (citySelect) citySelect.value = 'all';

  const unrevChip = document.getElementById('chipUnreviewedOnly');
  if (unrevChip) unrevChip.classList.remove('active');

  const customLabel = document.getElementById('customDateChipLabel');
  if (customLabel) customLabel.textContent = 'Custom Range';

  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  const chipAll = document.getElementById('chipAll');
  if (chipAll) chipAll.classList.add('active');

  const popover = document.getElementById('datePopover');
  if (popover) popover.style.display = 'none';

  applyAllFilters();
}

// ================= LIGHTBOX VIEWER =================
function openLightboxByItem(item) {
  const idx = currentFiltered.findIndex(i => i.id === item.id);
  currentLightboxIndex = idx >= 0 ? idx : 0;
  showLightbox();
}

function showLightbox() {
  const item = currentFiltered[currentLightboxIndex];
  if (!item) return;

  const modal = document.getElementById('lightboxModal');
  const imgEl = document.getElementById('lightboxImg');
  const counterEl = document.getElementById('lightboxCounter');
  const metaRec = document.getElementById('metaRecordNumber');
  const metaTime = document.getElementById('metaTimestamp');
  const metaRel = document.getElementById('metaRelativeTime');
  const metaUser = document.getElementById('metaTargetUser');
  const metaLoc = document.getElementById('metaLocation');
  const metaIP = document.getElementById('metaIP');
  const metaAcc = document.getElementById('metaAccuracy');
  const btnMapsLink = document.getElementById('btnMapsLink');
  const metaMapsBtn = document.getElementById('metaMapsBtn');

  // Photo
  if (item.image_base64) {
    imgEl.src = `data:image/jpeg;base64,${item.image_base64}`;
    imgEl.style.display = 'block';
  } else {
    imgEl.style.display = 'none';
  }

  // Meta info
  counterEl.textContent = `${currentLightboxIndex + 1} of ${currentFiltered.length}`;
  metaRec.textContent = `#${item.record_number || item.id}`;
  metaTime.textContent = item.detected_at;
  metaRel.textContent = getRelativeTime(item.detected_at);
  metaUser.textContent = item.username || 'Standard Account';
  metaLoc.textContent = item.city ? `${item.city}, ${item.country || ''}` : 'Location Offline / Unknown';
  metaIP.textContent = `Public IP: ${item.public_ip || 'Offline'}`;
  metaAcc.textContent = item.accuracy_m ? `Accuracy: ~${item.accuracy_m}m (Wi-Fi)` : `Provider: IP Geolocation`;

  // Maps Link
  if (item.maps_url) {
    btnMapsLink.style.display = 'flex';
    btnMapsLink.onclick = () => window.open(item.maps_url, '_blank');
    metaMapsBtn.href = item.maps_url;
    metaMapsBtn.style.display = 'flex';
  } else {
    btnMapsLink.style.display = 'none';
    metaMapsBtn.style.display = 'none';
  }

  modal.style.display = 'flex';

  // Mark as reviewed if unreviewed
  if (!item.reviewed_by_user && window.pywebview && window.pywebview.api) {
    window.pywebview.api.acknowledge_incident(item.id).then(() => {
      item.reviewed_by_user = 1;
      checkBreachBanner(allIncidents);
    });
  }
}

function closeLightbox() {
  document.getElementById('lightboxModal').style.display = 'none';
}

function prevIncident() {
  if (currentLightboxIndex > 0) {
    currentLightboxIndex--;
    showLightbox();
  }
}

function nextIncident() {
  if (currentLightboxIndex < currentFiltered.length - 1) {
    currentLightboxIndex++;
    showLightbox();
  }
}

function openPhotoDirectly() {
  const item = currentFiltered[currentLightboxIndex];
  if (item && item.image_path && window.pywebview && window.pywebview.api) {
    window.pywebview.api.open_file_in_os(item.image_path);
  }
}

function getRelativeTime(dateStr) {
  try {
    const d = new Date(dateStr.replace(" ", "T"));
    const diffSec = Math.floor((new Date() - d) / 1000);
    if (diffSec < 60) return "Just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} minutes ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hours ago`;
    return `${Math.floor(diffSec / 86400)} days ago`;
  } catch {
    return "";
  }
}

// ================= BREACH ALERT BANNER =================
function checkBreachBanner(incidents) {
  const banner = document.getElementById('breachAlertBanner');
  const unreviewed = incidents.filter(i => !i.reviewed_by_user);

  if (unreviewed.length > 0) {
    banner.style.display = 'flex';
    document.getElementById('breachBannerTitle').textContent = `🚨 ${unreviewed.length} Unauthorized Login Attempt${unreviewed.length === 1 ? '' : 's'} Detected!`;
    document.getElementById('breachBannerDesc').textContent = `Latest attempt on ${unreviewed[0].detected_at} (${unreviewed[0].username || 'User'}).`;
  } else {
    banner.style.display = 'none';
  }
}

function openLatestBreach() {
  const unreviewed = allIncidents.filter(i => !i.reviewed_by_user);
  if (unreviewed.length > 0) {
    openLightboxByItem(unreviewed[0]);
  }
}

async function acknowledgeAllBreaches() {
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.acknowledge_all();
  }
  allIncidents.forEach(i => i.reviewed_by_user = 1);
  checkBreachBanner(allIncidents);
  renderGallery(currentFiltered);
  showToast("All security alerts marked as reviewed.");
}

// ================= SERVICE STATUS & TOGGLE =================
async function refreshServiceStatus() {
  const dot = document.getElementById('serviceDot');
  const label = document.getElementById('serviceLabel');
  const switchBox = document.getElementById('serviceSwitch');

  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.get_service_status();
      if (res.status === 'RUNNING') {
        dot.className = 'status-dot active';
        label.textContent = 'Protection Active';
        switchBox.className = 'switch-mini active';
      } else if (res.status === 'STOPPED') {
        dot.className = 'status-dot paused';
        label.textContent = 'Protection Paused';
        switchBox.className = 'switch-mini';
      } else {
        dot.className = 'status-dot paused';
        label.textContent = 'Standalone Mode';
        switchBox.className = 'switch-mini';
      }
    } catch {
      label.textContent = 'Active (Local)';
      dot.className = 'status-dot active';
      switchBox.className = 'switch-mini active';
    }
  } else {
    label.textContent = 'Active (Mock)';
    dot.className = 'status-dot active';
    switchBox.className = 'switch-mini active';
  }
}

function requestServiceToggle() {
  openPinModal(
    "Windows Service Control",
    "Enter Master PIN to toggle background intruder protection.",
    async (pin) => {
      try {
        const res = await window.pywebview.api.toggle_service(pin);
        if (res.success) {
          showToast(res.message);
          refreshServiceStatus();
        } else {
          showToast(res.message || "Failed to toggle service.");
        }
      } catch (err) {
        showToast("Error toggling service: " + err);
      }
    }
  );
}

// ================= SETTINGS MANAGEMENT =================
async function loadSettingsData() {
  if (!window.pywebview || !window.pywebview.api) return;

  try {
    const data = await window.pywebview.api.get_settings_bundle();
    
    // Fill settings inputs
    const settings = data.settings || {};
    document.getElementById('retentionSelect').value = settings.retention_days || '30';
    document.getElementById('quotaSelect').value = settings.storage_max_mb || '500';
    document.getElementById('alertEmailInput').value = settings.alert_email || '';
    document.getElementById('smtpUserInput').value = settings.smtp_user || '';
    document.getElementById('smtpPassInput').value = settings.smtp_password || '';

    // Storage Meter
    const stats = data.storage || {};
    const usedMb = stats.used_mb || 0;
    const maxMb = stats.max_mb || 500;
    const pct = stats.percent_used || 0;
    const photos = stats.photo_count || 0;

    document.getElementById('meterUsedText').textContent = `${usedMb} MB used`;
    document.getElementById('meterCapText').textContent = `of ${maxMb} MB`;
    document.getElementById('meterBarFill').style.width = `${Math.min(pct, 100)}%`;
    document.getElementById('meterPhotosCount').textContent = `${photos} Photos captured`;
    document.getElementById('storageSummaryPill').textContent = `${usedMb} MB Used`;
  } catch (err) {
    console.error("Error loading settings bundle:", err);
  }
}

async function saveSettings() {
  const newPin = document.getElementById('newPinInput').value.trim();
  if (newPin && newPin.length < 4) {
    showToast("Master PIN must be at least 4 digits.");
    return;
  }

  const payload = {
    retention_days: document.getElementById('retentionSelect').value,
    storage_max_mb: document.getElementById('quotaSelect').value,
    alert_email: document.getElementById('alertEmailInput').value.trim(),
    smtp_user: document.getElementById('smtpUserInput').value.trim(),
    smtp_password: document.getElementById('smtpPassInput').value.trim(),
    new_pin: newPin
  };

  try {
    const res = await window.pywebview.api.save_settings(payload);
    if (res.success) {
      document.getElementById('newPinInput').value = '';
      showToast("✓ Settings updated successfully!");
      loadSettingsData();
    } else {
      showToast(res.message || "Failed to save settings.");
    }
  } catch (err) {
    showToast("Error saving settings: " + err);
  }
}

async function sendTestEmail() {
  const btn = document.getElementById('btnTestEmail');
  const originalHtml = btn.innerHTML;
  btn.innerHTML = `<span>Sending Test Email...</span>`;
  btn.style.pointerEvents = 'none';

  const payload = {
    alert_email: document.getElementById('alertEmailInput').value.trim(),
    smtp_user: document.getElementById('smtpUserInput').value.trim(),
    smtp_password: document.getElementById('smtpPassInput').value.trim()
  };

  try {
    const res = await window.pywebview.api.send_test_email(payload);
    if (res.success) {
      showToast("✓ Test alert email delivered! Check your inbox.");
    } else {
      showToast("❌ Email failed: " + (res.message || "Bad credentials"));
    }
  } catch (err) {
    showToast("Error: " + err);
  } finally {
    btn.innerHTML = originalHtml;
    btn.style.pointerEvents = 'auto';
  }
}

function togglePasswordVisibility(inputId) {
  const el = document.getElementById(inputId);
  if (el) {
    el.type = el.type === 'password' ? 'text' : 'password';
  }
}

// ================= PURGE HISTORY =================
function requestPurgeAccess() {
  openPinModal(
    "Purge All Incident Evidence",
    "Enter Master PIN to permanently erase all photos and database logs.",
    async (pin) => {
      try {
        const res = await window.pywebview.api.purge_all(pin);
        if (res.success) {
          showToast("All incident history and photos have been deleted.");
          loadIncidents();
          loadSettingsData();
        } else {
          showToast("Purge failed: Invalid Master PIN.");
        }
      } catch (err) {
        showToast("Error: " + err);
      }
    }
  );
}

// ================= PIN AUTH MODAL =================
function initPinBoxes() {
  const boxes = document.querySelectorAll('.pin-digit-box');
  boxes.forEach((box, idx) => {
    box.addEventListener('input', (e) => {
      const val = e.target.value;
      // Allow only numbers
      if (!/^\d$/.test(val)) {
        e.target.value = '';
        e.target.classList.remove('filled');
        return;
      }
      e.target.classList.add('filled');
      document.getElementById('pinErrorMsg').textContent = "";

      // Move to next box if available
      if (idx < boxes.length - 1) {
        boxes[idx + 1].focus();
      } else {
        // All digits entered: auto submit
        submitPin();
      }
    });

    box.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace') {
        if (box.value === '') {
          // If empty, move to previous and clear it
          if (idx > 0) {
            boxes[idx - 1].value = '';
            boxes[idx - 1].classList.remove('filled');
            boxes[idx - 1].focus();
          }
        } else {
          box.value = '';
          box.classList.remove('filled');
        }
        e.preventDefault();
      } else if (e.key === 'ArrowLeft' && idx > 0) {
        boxes[idx - 1].focus();
      } else if (e.key === 'ArrowRight' && idx < boxes.length - 1) {
        boxes[idx + 1].focus();
      }
    });

    box.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasted = (e.clipboardData || window.clipboardData).getData('text').trim();
      const digits = pasted.replace(/\D/g, '').split('');
      if (digits.length > 0) {
        boxes.forEach((b, i) => {
          if (i < digits.length) {
            b.value = digits[i];
            b.classList.add('filled');
          }
        });
        if (digits.length >= boxes.length) {
          boxes[boxes.length - 1].focus();
          submitPin();
        } else {
          boxes[digits.length].focus();
        }
      }
    });
  });
}

function openPinModal(title, desc, onVerifiedCallback) {
  pendingPinAction = onVerifiedCallback;
  document.getElementById('pinModalTitle').textContent = title || "Authentication Required";
  document.getElementById('pinModalDesc').textContent = desc || "Enter your Master PIN to proceed.";
  document.getElementById('pinErrorMsg').textContent = "";
  
  const boxes = document.querySelectorAll('.pin-digit-box');
  boxes.forEach(b => {
    b.value = "";
    b.classList.remove('filled');
  });
  
  document.getElementById('pinModal').style.display = 'flex';
  setTimeout(() => {
    if (boxes.length > 0) boxes[0].focus();
  }, 100);
}

function closePinModal() {
  document.getElementById('pinModal').style.display = 'none';
  pendingPinAction = null;
}

async function submitPin() {
  const boxes = document.querySelectorAll('.pin-digit-box');
  const errorMsg = document.getElementById('pinErrorMsg');
  const card = document.querySelector('.pin-modal-card');
  
  let enteredPin = "";
  boxes.forEach(b => enteredPin += b.value.trim());

  if (enteredPin.length < 4) {
    errorMsg.textContent = "Please enter your PIN (at least 4 digits).";
    return;
  }

  let isValid = false;
  if (window.pywebview && window.pywebview.api) {
    isValid = await window.pywebview.api.verify_pin(enteredPin);
  } else {
    isValid = (enteredPin === '1234'); // Mock fallback
  }

  if (isValid) {
    const action = pendingPinAction;
    closePinModal();
    if (action) action(enteredPin);
  } else {
    errorMsg.textContent = "Incorrect PIN. Try again.";
    card.classList.add('shake');
    boxes.forEach(b => {
      b.value = "";
      b.classList.remove('filled');
    });
    setTimeout(() => {
      card.classList.remove('shake');
      if (boxes.length > 0) boxes[0].focus();
    }, 400);
  }
}

// ================= TOAST NOTIFICATION =================
function showToast(msg) {
  const toast = document.getElementById('toastPill');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3500);
}

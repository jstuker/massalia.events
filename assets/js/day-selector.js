(function() {
  'use strict';

  const HASH_PREFIX = 'day-';
  const FRENCH_DAYS = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
  const FRENCH_DAYS_FULL = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];

  /**
   * Get today's date string (YYYY-MM-DD) in Europe/Paris timezone
   */
  function getParisTodayStr() {
    var parts = new Intl.DateTimeFormat('en', {
      timeZone: 'Europe/Paris',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    var year = parts.find(function(p) { return p.type === 'year'; }).value;
    var month = parts.find(function(p) { return p.type === 'month'; }).value;
    var day = parts.find(function(p) { return p.type === 'day'; }).value;
    return year + '-' + month + '-' + day;
  }

  /**
   * Get French day abbreviation from a YYYY-MM-DD date string
   */
  function getDayAbbrev(dateStr) {
    var parts = dateStr.split('-').map(Number);
    return FRENCH_DAYS[new Date(parts[0], parts[1] - 1, parts[2]).getDay()];
  }

  /**
   * Get French full day name from a YYYY-MM-DD date string
   */
  function getDayFull(dateStr) {
    var parts = dateStr.split('-').map(Number);
    return FRENCH_DAYS_FULL[new Date(parts[0], parts[1] - 1, parts[2]).getDay()];
  }

  /**
   * Correct "Aujourd'hui" label based on actual Paris time.
   * Hugo bakes the label at build time, which may be stale.
   */
  function correctTodayLabels() {
    var tabs = document.querySelectorAll('.day-tab');
    if (!tabs.length) return;

    var todayStr = getParisTodayStr();

    // Check if build-time "today" (first tab) is still correct
    if (tabs[0] && tabs[0].getAttribute('data-date') === todayStr) return;

    tabs.forEach(function(tab) {
      var tabDate = tab.getAttribute('data-date');
      var labelSpan = tab.querySelector('span:first-child');
      var ariaLabel = tab.getAttribute('aria-label') || '';

      if (tabDate === todayStr) {
        // This tab is the real today
        if (labelSpan) labelSpan.textContent = "Aujourd'hui";
        tab.setAttribute('aria-label', ariaLabel.replace(/^[^,]+/, "Aujourd'hui"));
      } else if (labelSpan && labelSpan.textContent.trim() === "Aujourd'hui") {
        // This tab was incorrectly labeled as today - restore day name
        var dayAbbrev = getDayAbbrev(tabDate);
        var dayFull = getDayFull(tabDate);
        labelSpan.textContent = dayAbbrev;
        tab.setAttribute('aria-label', ariaLabel.replace("Aujourd'hui", dayFull));
      }
    });
  }

  function initDaySelector() {
    var tabs = document.querySelectorAll('.day-tab');
    if (!tabs.length) return;

    // Correct "Aujourd'hui" labels before selecting default tab
    correctTodayLabels();

    // Handle click events
    tabs.forEach(function(tab) {
      tab.addEventListener('click', function() { selectDay(tab); });
    });

    // Handle keyboard navigation
    tabs.forEach(function(tab, index) {
      tab.addEventListener('keydown', function(e) {
        var targetIndex = index;

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          targetIndex = (index + 1) % tabs.length;
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          targetIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (e.key === 'Home') {
          e.preventDefault();
          targetIndex = 0;
        } else if (e.key === 'End') {
          e.preventDefault();
          targetIndex = tabs.length - 1;
        }

        if (targetIndex !== index) {
          tabs[targetIndex].focus();
          selectDay(tabs[targetIndex]);
        }
      });
    });

    // Check for hash on load, or default to real today
    var hash = window.location.hash.slice(1);
    if (hash.startsWith(HASH_PREFIX)) {
      var dateFromHash = hash.slice(HASH_PREFIX.length);
      var matchingTab = document.querySelector('.day-tab[data-date="' + dateFromHash + '"]');
      if (matchingTab) {
        selectDay(matchingTab, false);
      }
    } else {
      // Select real today's tab (may differ from build-time today)
      var todayStr = getParisTodayStr();
      var todayTab = document.querySelector('.day-tab[data-date="' + todayStr + '"]');
      if (todayTab && !todayTab.hasAttribute('data-active')) {
        selectDay(todayTab, false);
      }
    }
  }

  function selectDay(selectedTab, updateHash) {
    if (updateHash === undefined) updateHash = true;
    var tabs = document.querySelectorAll('.day-tab');
    var activeClass = 'bg-primary-500 text-white shadow-md';
    var inactiveClass = 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700';

    tabs.forEach(function(tab) {
      var isSelected = tab === selectedTab;

      // Update ARIA and tabindex (roving tabindex pattern)
      tab.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      tab.setAttribute('tabindex', isSelected ? '0' : '-1');

      // Update data attribute
      if (isSelected) {
        tab.setAttribute('data-active', 'true');
      } else {
        tab.removeAttribute('data-active');
      }

      // Update classes
      if (isSelected) {
        tab.classList.remove.apply(tab.classList, inactiveClass.split(' '));
        tab.classList.add.apply(tab.classList, activeClass.split(' '));
      } else {
        tab.classList.remove.apply(tab.classList, activeClass.split(' '));
        tab.classList.add.apply(tab.classList, inactiveClass.split(' '));
      }
    });

    // Update URL hash
    if (updateHash) {
      var date = selectedTab.getAttribute('data-date');
      history.replaceState(null, '', '#' + HASH_PREFIX + date);
    }

    // Dispatch custom event for other components to listen to
    var event = new CustomEvent('daySelected', {
      detail: {
        date: selectedTab.getAttribute('data-date'),
        dayIndex: parseInt(selectedTab.getAttribute('data-day-index'), 10)
      }
    });
    document.dispatchEvent(event);
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDaySelector);
  } else {
    initDaySelector();
  }
})();

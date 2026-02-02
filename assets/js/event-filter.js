(function() {
  'use strict';

  /**
   * Filter events by selected date and sort by start time
   * @param {string} selectedDate - Date in YYYY-MM-DD format
   */
  function filterEventsByDate(selectedDate) {
    var cardsContainer = document.querySelector('.event-cards-container .grid');
    var cards = Array.from(document.querySelectorAll('.event-card-wrapper'));
    var noEventsMessage = document.querySelector('.no-events-message');
    var eventCount = document.getElementById('event-count');

    // Filter cards by date
    var visibleCards = [];
    var hiddenCards = [];

    cards.forEach(function(card) {
      var eventDate = card.getAttribute('data-event-date');
      if (eventDate === selectedDate) {
        card.classList.remove('hidden');
        card.setAttribute('aria-hidden', 'false');
        visibleCards.push(card);
      } else {
        card.classList.add('hidden');
        card.setAttribute('aria-hidden', 'true');
        hiddenCards.push(card);
      }
    });

    // Sort visible cards by start time (earliest first)
    visibleCards.sort(function(a, b) {
      var timeA = a.getAttribute('data-start-time') || '00:00';
      var timeB = b.getAttribute('data-start-time') || '00:00';
      return timeA.localeCompare(timeB);
    });

    // Reorder DOM: visible cards first (sorted), then hidden cards
    if (cardsContainer) {
      visibleCards.forEach(function(card) { cardsContainer.appendChild(card); });
      hiddenCards.forEach(function(card) { cardsContainer.appendChild(card); });
    }

    // Show/hide empty state
    if (noEventsMessage) {
      if (visibleCards.length === 0) {
        noEventsMessage.classList.remove('hidden');
      } else {
        noEventsMessage.classList.add('hidden');
      }
    }

    // Update screen reader announcement
    if (eventCount) {
      if (visibleCards.length === 0) {
        eventCount.textContent = 'Aucun événement pour cette date';
      } else if (visibleCards.length === 1) {
        eventCount.textContent = '1 événement trouvé';
      } else {
        eventCount.textContent = visibleCards.length + ' événements trouvés';
      }
    }
  }

  /**
   * Initialize event filtering on page load
   */
  function initFilter() {
    // Get today's date in Europe/Paris timezone
    var parts = new Intl.DateTimeFormat('en', {
      timeZone: 'Europe/Paris',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    var todayStr = parts.find(function(p) { return p.type === 'year'; }).value + '-' +
      parts.find(function(p) { return p.type === 'month'; }).value + '-' +
      parts.find(function(p) { return p.type === 'day'; }).value;

    // Check for hash-based date first
    var hash = window.location.hash.slice(1);
    if (hash.startsWith('day-')) {
      var dateFromHash = hash.slice(4);
      filterEventsByDate(dateFromHash);
    } else {
      // Default to today
      filterEventsByDate(todayStr);
    }
  }

  // Listen for day selection changes from day-selector component
  document.addEventListener('daySelected', function(e) {
    filterEventsByDate(e.detail.date);
  });

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFilter);
  } else {
    initFilter();
  }
})();

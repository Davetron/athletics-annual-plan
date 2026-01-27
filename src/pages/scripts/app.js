/**
 * Main application controller
 * Handles step navigation, competition selection, plan generation, and download
 */

import { SpreadsheetManager } from './spreadsheet.js';
import { API_BASE } from './config.js';

// Federation data for URL lookup
const FEDERATIONS = {
  'Ireland': 'https://www.athleticsireland.ie/competition/fixtures',
  'United Kingdom': 'https://www.uka.org.uk/events/',
  'United States': 'https://www.usatf.org/events',
  'Australia': 'https://www.athletics.com.au/events/',
  'Canada': 'https://athletics.ca/events/',
  'Germany': 'https://www.leichtathletik.de/termine',
  'France': 'https://www.athle.fr/calendrier.aspx',
  'Spain': 'https://www.rfea.es/web/calendario/',
};

class App {
  constructor() {
    this.currentStep = 1;
    this.formData = null;
    this.selectedCompetitions = [];
    this.allCompetitions = [];
    this.plan = null;
    this.spreadsheet = null;

    // Check for valid session
    if (!this.checkSession()) {
      window.location.href = '/';
      return;
    }

    this.setupElements();
    this.setupEventListeners();
  }

  /**
   * Check if user has a valid session
   */
  checkSession() {
    const inviteCode = sessionStorage.getItem('inviteCode');
    const sessionId = sessionStorage.getItem('sessionId');
    return inviteCode && sessionId;
  }

  /**
   * Cache DOM elements
   */
  setupElements() {
    // Steps
    this.stepSections = document.querySelectorAll('.step-section');
    this.stepDots = document.querySelectorAll('.step-dot');

    // Form elements
    this.planForm = document.getElementById('plan-form');

    // Competition elements
    this.competitionsSubtitle = document.getElementById('competitions-subtitle');
    this.competitionsLoading = document.getElementById('competitions-loading');
    this.competitionsError = document.getElementById('competitions-error');
    this.competitionsList = document.getElementById('competitions-list');
    this.addCustomSection = document.getElementById('add-custom-section');
    this.retrySearchBtn = document.getElementById('retry-search');
    this.toggleCustomFormBtn = document.getElementById('toggle-custom-form');
    this.customForm = document.getElementById('custom-form');
    this.addCustomBtn = document.getElementById('add-custom-btn');

    // Navigation buttons
    this.backToFormBtn = document.getElementById('back-to-form');
    this.generatePlanBtn = document.getElementById('generate-plan-btn');
    this.backToCompetitionsBtn = document.getElementById('back-to-competitions');

    // Spreadsheet container
    this.spreadsheetContainer = document.getElementById('spreadsheet-container');
  }

  /**
   * Set up event listeners
   */
  setupEventListeners() {
    // Form submission
    this.planForm?.addEventListener('submit', (e) => this.handleFormSubmit(e));

    // Navigation
    this.backToFormBtn?.addEventListener('click', () => this.goToStep(1));
    this.generatePlanBtn?.addEventListener('click', () => this.handleGeneratePlan());
    this.backToCompetitionsBtn?.addEventListener('click', () => this.goToStep(2));

    // Competition actions
    this.retrySearchBtn?.addEventListener('click', () => this.searchCompetitions());
    this.toggleCustomFormBtn?.addEventListener('click', () => this.toggleCustomForm());
    this.addCustomBtn?.addEventListener('click', () => this.addCustomCompetition());

    // Download from spreadsheet toolbar
    this.spreadsheetContainer?.addEventListener('download-excel', (e) => {
      const plan = e.detail?.plan || this.plan;
      this.handleDownload(plan);
    });
  }

  /**
   * Handle form submission
   */
  handleFormSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);

    this.formData = {
      athleteName: formData.get('athleteName'),
      eventGroup: formData.get('eventGroup'),
      season: formData.get('season'),
      periodization: formData.get('periodization'),
      ageGroups: formData.getAll('ageGroups'),
      trainingLevel: formData.get('trainingLevel'),
      country: formData.get('country'),
      compLevels: formData.getAll('compLevels'),
      targetCompetitions: formData.get('targetCompetitions'),
    };

    // Go to competitions step and search
    this.goToStep(2);
    this.searchCompetitions();
  }

  /**
   * Search for competitions based on form data
   */
  async searchCompetitions() {
    // Show loading state
    this.competitionsLoading.style.display = 'flex';
    this.competitionsError.style.display = 'none';
    this.competitionsList.style.display = 'none';
    this.addCustomSection.style.display = 'none';
    this.generatePlanBtn.disabled = true;

    this.competitionsSubtitle.textContent = `Searching competitions for ${this.formData.season} season...`;

    try {
      const federationUrl = FEDERATIONS[this.formData.country] || null;

      const response = await fetch(`${API_BASE}/api/search-competitions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country: this.formData.country,
          season_year: this.formData.season,
          age_groups: this.formData.ageGroups,
          event_group: this.formData.eventGroup,
          comp_levels: this.formData.compLevels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
          federation_url: federationUrl,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || 'Failed to search competitions');
      }

      this.allCompetitions = data.competitions || [];
      this.selectedCompetitions = [];

      // Auto-select major competitions
      this.allCompetitions.forEach((comp, index) => {
        if (comp.importance === 1) {
          this.selectedCompetitions.push(index);
        }
      });

      this.renderCompetitions();
    } catch (error) {
      console.error('Competition search error:', error);
      this.showCompetitionError(error.message);
    }
  }

  /**
   * Render the competition list
   */
  renderCompetitions() {
    this.competitionsLoading.style.display = 'none';
    this.competitionsError.style.display = 'none';
    this.competitionsList.style.display = 'flex';
    this.addCustomSection.style.display = 'block';

    const count = this.allCompetitions.length;
    this.competitionsSubtitle.textContent = `Found ${count} competition${count !== 1 ? 's' : ''} for ${this.formData.season} season`;

    this.competitionsList.textContent = '';

    if (count === 0) {
      const emptyMsg = document.createElement('p');
      emptyMsg.style.cssText = 'color: var(--text-secondary); text-align: center; padding: var(--space-xl);';
      emptyMsg.textContent = 'No competitions found. Try adding custom competitions below.';
      this.competitionsList.appendChild(emptyMsg);
    } else {
      this.allCompetitions.forEach((comp, index) => {
        const isSelected = this.selectedCompetitions.includes(index);
        const item = this.createCompetitionItem(comp, index, isSelected);
        this.competitionsList.appendChild(item);
      });
    }

    this.updateGenerateButton();
  }

  /**
   * Create a competition list item
   */
  createCompetitionItem(comp, index, isSelected) {
    const div = document.createElement('div');
    div.className = `competition-item${isSelected ? ' selected' : ''}`;
    div.dataset.index = index;

    // Checkbox
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'competition-checkbox';
    checkbox.checked = isSelected;
    div.appendChild(checkbox);

    // Details container
    const details = document.createElement('div');
    details.className = 'competition-details';

    const name = document.createElement('span');
    name.className = 'competition-name';
    name.textContent = comp.name;
    details.appendChild(name);

    const meta = document.createElement('span');
    meta.className = 'competition-meta';

    const dateSpan = document.createElement('span');
    dateSpan.textContent = this.formatCompetitionDate(comp.date, comp.end_date);
    meta.appendChild(dateSpan);

    if (comp.location) {
      const locSpan = document.createElement('span');
      locSpan.textContent = comp.location;
      meta.appendChild(locSpan);
    }

    details.appendChild(meta);
    div.appendChild(details);

    // Type badge
    const typeClass = comp.type || 'outdoor';
    const typeBadge = document.createElement('span');
    typeBadge.className = `competition-type ${typeClass}`;
    typeBadge.textContent = typeClass;
    div.appendChild(typeBadge);

    // Importance stars
    const importanceClass = comp.importance === 1 ? 'major' : comp.importance === 2 ? 'significant' : 'development';
    const importanceSpan = document.createElement('span');
    importanceSpan.className = `competition-importance ${importanceClass}`;
    importanceSpan.textContent = '\u2B50'.repeat(4 - comp.importance);
    div.appendChild(importanceSpan);

    div.addEventListener('click', (e) => {
      if (e.target.type !== 'checkbox') {
        checkbox.checked = !checkbox.checked;
      }
      this.toggleCompetition(index);
    });

    return div;
  }

  /**
   * Format competition date for display
   */
  formatCompetitionDate(date, endDate) {
    if (!date) return 'TBD';

    const start = new Date(date);
    const options = { month: 'short', day: 'numeric' };
    let str = start.toLocaleDateString('en-GB', options);

    if (endDate && endDate !== date) {
      const end = new Date(endDate);
      str += ` - ${end.toLocaleDateString('en-GB', options)}`;
    }

    return str;
  }

  /**
   * Toggle competition selection
   */
  toggleCompetition(index) {
    const idx = this.selectedCompetitions.indexOf(index);
    if (idx === -1) {
      this.selectedCompetitions.push(index);
    } else {
      this.selectedCompetitions.splice(idx, 1);
    }

    // Update UI
    const items = this.competitionsList.querySelectorAll('.competition-item');
    items.forEach(item => {
      const itemIndex = parseInt(item.dataset.index);
      const isSelected = this.selectedCompetitions.includes(itemIndex);
      item.classList.toggle('selected', isSelected);
      item.querySelector('.competition-checkbox').checked = isSelected;
    });

    this.updateGenerateButton();
  }

  /**
   * Update generate button state
   */
  updateGenerateButton() {
    const hasSelection = this.selectedCompetitions.length > 0;
    this.generatePlanBtn.disabled = !hasSelection;

    // Clear and rebuild button content
    this.generatePlanBtn.textContent = '';

    const text = document.createTextNode(
      hasSelection ? `GENERATE PLAN (${this.selectedCompetitions.length}) ` : 'SELECT COMPETITIONS '
    );
    this.generatePlanBtn.appendChild(text);

    const arrow = document.createElement('span');
    arrow.textContent = '\u2192';
    this.generatePlanBtn.appendChild(arrow);
  }

  /**
   * Show competition search error
   */
  showCompetitionError(message) {
    this.competitionsLoading.style.display = 'none';
    this.competitionsError.style.display = 'block';
    this.competitionsList.style.display = 'none';
    this.addCustomSection.style.display = 'none';

    this.competitionsError.querySelector('.error-message').textContent = message;
    this.competitionsSubtitle.textContent = 'Failed to find competitions';
  }

  /**
   * Toggle custom competition form
   */
  toggleCustomForm() {
    const isVisible = this.customForm.style.display !== 'none';
    this.customForm.style.display = isVisible ? 'none' : 'flex';
    this.toggleCustomFormBtn.textContent = isVisible ? '+ Add Custom Competition' : '\u2212 Cancel';
  }

  /**
   * Add a custom competition
   */
  addCustomCompetition() {
    const name = document.getElementById('custom-name').value.trim();
    const date = document.getElementById('custom-date').value;
    const importance = parseInt(document.getElementById('custom-importance').value);

    if (!name || !date) {
      alert('Please enter a competition name and date');
      return;
    }

    const newComp = {
      name,
      date,
      end_date: null,
      location: null,
      importance,
      type: 'outdoor',
    };

    this.allCompetitions.push(newComp);
    this.selectedCompetitions.push(this.allCompetitions.length - 1);

    // Reset form
    document.getElementById('custom-name').value = '';
    document.getElementById('custom-date').value = '';
    document.getElementById('custom-importance').value = '3';
    this.customForm.style.display = 'none';
    this.toggleCustomFormBtn.textContent = '+ Add Custom Competition';

    this.renderCompetitions();
  }

  /**
   * Handle generate plan button click
   */
  async handleGeneratePlan() {
    this.generatePlanBtn.disabled = true;
    this.generatePlanBtn.textContent = 'GENERATING...';

    try {
      // Build target competitions string from selected
      const selectedComps = this.selectedCompetitions.map(i => this.allCompetitions[i]);
      const targetCompetitions = selectedComps.map(c => {
        const dateStr = this.formatCompetitionDate(c.date, c.end_date);
        return `${c.name} (${dateStr})`;
      }).join(', ');

      const sessionId = sessionStorage.getItem('sessionId');

      const response = await fetch(`${API_BASE}/api/generate-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId,
        },
        body: JSON.stringify({
          formData: {
            ...this.formData,
            targetCompetitions,
          },
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || 'Failed to generate plan');
      }

      this.plan = data.plan;
      this.initSpreadsheet(this.plan);
      this.goToStep(3);
    } catch (error) {
      console.error('Generate plan error:', error);
      alert(`Failed to generate plan: ${error.message}`);
    } finally {
      this.generatePlanBtn.disabled = false;
      this.updateGenerateButton();
    }
  }

  /**
   * Initialize the spreadsheet with plan data
   */
  initSpreadsheet(plan) {
    if (this.spreadsheet) {
      this.spreadsheet.destroy();
    }

    this.spreadsheet = new SpreadsheetManager('spreadsheet-container');
    this.spreadsheet.init(plan);
  }

  /**
   * Navigate to a specific step
   */
  goToStep(step) {
    this.currentStep = step;

    // Update sections
    this.stepSections.forEach(section => {
      const sectionStep = parseInt(section.dataset.step);
      section.classList.toggle('active', sectionStep === step);
    });

    // Update step indicators
    this.stepDots.forEach(dot => {
      const dotStep = parseInt(dot.dataset.step);
      dot.classList.toggle('active', dotStep === step);
      dot.classList.toggle('completed', dotStep < step);
    });

    // Scroll to top (only for steps 1 and 2)
    if (step < 3) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  /**
   * Handle Excel download via server-side generation
   */
  async handleDownload(plan) {
    plan = plan || this.plan;

    if (!plan) {
      alert('No plan available to download');
      return;
    }

    const downloadBtn = this.spreadsheetContainer?.querySelector('#download-excel-btn');
    if (downloadBtn) {
      downloadBtn.disabled = true;
      downloadBtn.textContent = 'GENERATING...';
    }

    try {
      const response = await fetch(`${API_BASE}/api/download-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan })
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }

      // Get filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${plan.athlete}_Annual_Plan_${plan.season.replace('/', '-')}.xlsx`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/);
        if (match) filename = match[1];
      }

      // Download the blob
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download error:', error);
      alert('Failed to generate Excel file. Please try again.');
    } finally {
      if (downloadBtn) {
        downloadBtn.disabled = false;
        downloadBtn.textContent = 'Download Excel';
      }
    }
  }

  /**
   * Reset the app to start over
   */
  resetApp() {
    this.plan = null;
    this.formData = null;
    this.selectedCompetitions = [];
    this.allCompetitions = [];
    this.planForm?.reset();

    if (this.spreadsheet) {
      this.spreadsheet.destroy();
      this.spreadsheet = null;
    }

    this.goToStep(1);
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new App();
});

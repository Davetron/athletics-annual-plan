/**
 * Main application controller
 * Handles step navigation, spreadsheet coordination, and download
 */

import { chatManager } from './chat.js';
import { SpreadsheetManager } from './spreadsheet.js';
import { API_BASE } from './config.js';

class App {
  constructor() {
    this.currentStep = 1;
    this.formData = null;
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

    // Navigation buttons
    this.backToFormBtn = document.getElementById('back-to-form');
    this.generatePlanBtn = document.getElementById('generate-plan-btn');
    this.backToChatBtn = document.getElementById('back-to-chat');

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
    this.backToChatBtn?.addEventListener('click', () => this.goToStep(2));

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

    // Go to chat step
    this.goToStep(2);

    // Start conversation with Claude
    chatManager.startConversation(this.formData);
  }

  /**
   * Handle generate plan button click
   */
  async handleGeneratePlan() {
    this.generatePlanBtn.disabled = true;
    this.generatePlanBtn.textContent = 'GENERATING...';

    try {
      const plan = await chatManager.generatePlan();

      if (plan) {
        this.plan = plan;
        this.initSpreadsheet(plan);
        this.goToStep(3);
      }
    } catch (error) {
      console.error('Generate plan error:', error);
      alert(`Failed to generate plan: ${error.message}`);
    } finally {
      this.generatePlanBtn.disabled = false;
      this.generatePlanBtn.textContent = 'GENERATE PLAN';
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

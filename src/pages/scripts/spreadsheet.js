/**
 * Simple Spreadsheet Preview using SheetJS
 * Renders the plan as a read-only HTML table with Download button
 */

// Color constants for phase types
const PHASE_COLORS = {
  'general-prep': '#FF9900',
  'special-prep': '#FFDD00',
  'competition': '#00CC66',
  'taper': '#D9D9D9',
};

const LOAD_COLORS = {
  4: '#E74C3C',
  3: '#F39C12',
  2: '#F1C40F',
  1: '#2ECC71',
  0: '#ECF0F1',
};

const IMPORTANCE_COLORS = {
  1: '#E74C3C',
  2: '#F39C12',
  3: '#3498DB',
};

/**
 * SpreadsheetManager - Simple read-only preview
 */
export class SpreadsheetManager {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.plan = null;
    this.onPlanChange = options.onPlanChange || (() => {});
  }

  init(plan) {
    this.plan = plan;
    this.render();
  }

  render() {
    if (!this.container || !this.plan) return;

    this.container.textContent = '';

    // Toolbar with download button
    const toolbar = document.createElement('div');
    toolbar.className = 'spreadsheet-toolbar';

    const toolbarInfo = document.createElement('div');
    toolbarInfo.className = 'toolbar-info';

    const planTitle = document.createElement('span');
    planTitle.className = 'plan-title';
    planTitle.textContent = `${this.plan.athlete} - ${this.plan.season}`;
    toolbarInfo.appendChild(planTitle);

    const planSubtitle = document.createElement('span');
    planSubtitle.className = 'plan-subtitle';
    planSubtitle.textContent = `${this.plan.eventGroup} | ${this.plan.periodization}`;
    toolbarInfo.appendChild(planSubtitle);

    toolbar.appendChild(toolbarInfo);

    const toolbarActions = document.createElement('div');
    toolbarActions.className = 'toolbar-actions';

    const downloadBtn = document.createElement('button');
    downloadBtn.id = 'download-excel-btn';
    downloadBtn.className = 'btn-download';
    downloadBtn.textContent = 'Download Excel';
    toolbarActions.appendChild(downloadBtn);

    toolbar.appendChild(toolbarActions);
    this.container.appendChild(toolbar);

    // Scrollable table container
    const scrollContainer = document.createElement('div');
    scrollContainer.className = 'spreadsheet-scroll-container';

    const table = this.buildTable();
    scrollContainer.appendChild(table);
    this.container.appendChild(scrollContainer);

    // Download button handler
    downloadBtn.addEventListener('click', () => {
      this.container.dispatchEvent(new CustomEvent('download-excel', {
        detail: { plan: this.plan },
        bubbles: true
      }));
    });
  }

  buildTable() {
    const table = document.createElement('table');
    table.className = 'plan-table';

    const weeks = this.plan.weeks;

    // Header row with week numbers
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');

    const labelTh = document.createElement('th');
    labelTh.className = 'label-cell';
    labelTh.textContent = 'Week';
    headerRow.appendChild(labelTh);

    weeks.forEach(w => {
      const th = document.createElement('th');
      th.className = 'week-header';
      th.textContent = w.weekNum;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    // Month row
    tbody.appendChild(this.createMergedRow('Month', weeks, w => w.month, '#1ABC9C'));

    // Date row
    tbody.appendChild(this.createDataRow('Date', weeks, w => this.formatDate(w.startDate)));

    // Competition row
    tbody.appendChild(this.createDataRow('Competition', weeks, w => w.competitions?.join(', ') || '', null, w => {
      if (w.competitionImportance) return IMPORTANCE_COLORS[w.competitionImportance];
      return null;
    }));

    // Phase row
    tbody.appendChild(this.createDataRow('Phase', weeks, w => this.getPhaseAbbrev(w.phaseType), null, w => PHASE_COLORS[w.phaseType]));

    // Block row
    tbody.appendChild(this.createMergedRow('Block', weeks, w => w.block, '#B4C6E7'));

    // Load row
    tbody.appendChild(this.createDataRow('Load', weeks, w => w.load, null, w => LOAD_COLORS[w.load]));

    // Technical row
    tbody.appendChild(this.createDataRow('Technical', weeks, w => w.technical || ''));

    // Physical row
    tbody.appendChild(this.createDataRow('Physical', weeks, w => w.physical || ''));

    table.appendChild(tbody);
    return table;
  }

  createDataRow(label, weeks, getValue, defaultBg = null, getBg = null) {
    const row = document.createElement('tr');

    const labelCell = document.createElement('td');
    labelCell.className = 'label-cell';
    labelCell.textContent = label;
    row.appendChild(labelCell);

    weeks.forEach(week => {
      const td = document.createElement('td');
      td.textContent = getValue(week);
      const bg = getBg ? getBg(week) : defaultBg;
      if (bg) {
        td.style.background = bg;
        // White text for dark backgrounds
        if (['#E74C3C', '#F39C12', '#00CC66', '#3498DB'].includes(bg)) {
          td.style.color = 'white';
        }
      }
      row.appendChild(td);
    });

    return row;
  }

  createMergedRow(label, weeks, getValue, bgColor) {
    const row = document.createElement('tr');

    const labelCell = document.createElement('td');
    labelCell.className = 'label-cell';
    labelCell.textContent = label;
    row.appendChild(labelCell);

    // Calculate spans for merged cells
    let i = 0;
    while (i < weeks.length) {
      const value = getValue(weeks[i]);
      let span = 1;
      while (i + span < weeks.length && getValue(weeks[i + span]) === value) {
        span++;
      }

      const td = document.createElement('td');
      td.colSpan = span;
      td.textContent = value || '';
      td.style.background = bgColor;
      td.style.color = 'white';
      td.style.fontWeight = 'bold';
      td.style.textAlign = 'center';
      row.appendChild(td);

      i += span;
    }

    return row;
  }

  formatDate(isoDate) {
    if (!isoDate) return '';
    const date = new Date(isoDate);
    return `${date.getDate()}/${date.getMonth() + 1}`;
  }

  getPhaseAbbrev(phaseType) {
    const abbrevs = {
      'general-prep': 'GP',
      'special-prep': 'SP',
      'competition': 'Comp',
      'taper': 'Tap',
    };
    return abbrevs[phaseType] || '';
  }

  updatePlan(newPlan) {
    this.plan = newPlan;
    this.render();
  }

  getPlan() {
    return this.plan;
  }

  destroy() {
    if (this.container) {
      this.container.textContent = '';
    }
  }
}

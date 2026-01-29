/**
 * Spreadsheet Preview using ExcelJS
 * Reads the Excel blob and renders it as HTML with full styling fidelity
 */

import { API_BASE } from './config.js';

/**
 * SpreadsheetManager - Renders Excel blob as styled HTML table using ExcelJS
 */
export class SpreadsheetManager {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.plan = null;
    this.cachedBlob = null;
    this.onPlanChange = options.onPlanChange || (() => {});
  }

  init(plan) {
    this.plan = plan;
    this.cachedBlob = null;
    this.render();
  }

  async render() {
    if (!this.container || !this.plan) return;

    this.container.textContent = '';

    // Toolbar with download button
    const toolbar = this.createToolbar();
    this.container.appendChild(toolbar);

    // Scrollable preview container
    const scrollContainer = document.createElement('div');
    scrollContainer.className = 'spreadsheet-scroll-container';
    this.container.appendChild(scrollContainer);

    // Show loading state
    this.showLoading(scrollContainer);

    try {
      // Fetch Excel blob from API
      const blob = await this.fetchExcelBlob();
      this.cachedBlob = blob;

      // Read with ExcelJS
      const arrayBuffer = await blob.arrayBuffer();
      const workbook = new ExcelJS.Workbook();
      await workbook.xlsx.load(arrayBuffer);

      // Get first worksheet
      const worksheet = workbook.worksheets[0];

      // Clear loading and render table
      scrollContainer.textContent = '';
      const table = this.buildTableFromWorksheet(worksheet);
      scrollContainer.appendChild(table);
    } catch (error) {
      console.error('Failed to render Excel preview:', error);
      this.showError(scrollContainer, error.message);
    }
  }

  buildTableFromWorksheet(worksheet) {
    const table = document.createElement('table');
    table.className = 'plan-table excel-preview-table';

    // Get merged cell ranges
    const mergedCells = this.getMergedCellMap(worksheet);

    // Determine actual data bounds
    const rowCount = worksheet.rowCount;
    const colCount = worksheet.columnCount;

    // Build table rows
    for (let rowNum = 1; rowNum <= rowCount; rowNum++) {
      const row = worksheet.getRow(rowNum);
      const tr = document.createElement('tr');

      for (let colNum = 1; colNum <= colCount; colNum++) {
        const cellAddress = this.getCellAddress(rowNum, colNum);
        const mergeInfo = mergedCells.get(cellAddress);

        // Skip cells that are part of a merge but not the top-left
        if (mergeInfo && !mergeInfo.isOrigin) {
          continue;
        }

        const cell = row.getCell(colNum);
        const td = document.createElement('td');

        // Apply merge spans
        if (mergeInfo && mergeInfo.isOrigin) {
          if (mergeInfo.rowSpan > 1) td.rowSpan = mergeInfo.rowSpan;
          if (mergeInfo.colSpan > 1) td.colSpan = mergeInfo.colSpan;
        }

        // Set cell value
        td.textContent = this.getCellDisplayValue(cell);

        // Apply styles
        this.applyCellStyles(td, cell, colNum === 1);

        tr.appendChild(td);
      }

      table.appendChild(tr);
    }

    return table;
  }

  getMergedCellMap(worksheet) {
    const mergeMap = new Map();

    // worksheet.model.merges contains merge ranges like "B3:D3"
    const merges = worksheet.model.merges || [];

    for (const mergeRange of merges) {
      // Parse range like "B3:F3" or "A19:A22"
      const [start, end] = mergeRange.split(':');
      const startCoord = this.parseCell(start);
      const endCoord = this.parseCell(end);

      const rowSpan = endCoord.row - startCoord.row + 1;
      const colSpan = endCoord.col - startCoord.col + 1;

      // Mark origin cell
      const originAddress = this.getCellAddress(startCoord.row, startCoord.col);
      mergeMap.set(originAddress, {
        isOrigin: true,
        rowSpan,
        colSpan,
      });

      // Mark all other cells in the merge as non-origin
      for (let r = startCoord.row; r <= endCoord.row; r++) {
        for (let c = startCoord.col; c <= endCoord.col; c++) {
          if (r === startCoord.row && c === startCoord.col) continue;
          mergeMap.set(this.getCellAddress(r, c), { isOrigin: false });
        }
      }
    }

    return mergeMap;
  }

  parseCell(cellRef) {
    // Parse "B3" into { row: 3, col: 2 }
    const match = cellRef.match(/^([A-Z]+)(\d+)$/);
    if (!match) return { row: 1, col: 1 };

    const colStr = match[1];
    const row = parseInt(match[2], 10);

    // Convert column letters to number (A=1, B=2, ..., Z=26, AA=27, etc.)
    let col = 0;
    for (let i = 0; i < colStr.length; i++) {
      col = col * 26 + (colStr.charCodeAt(i) - 64);
    }

    return { row, col };
  }

  getCellAddress(row, col) {
    return `${row},${col}`;
  }

  getCellDisplayValue(cell) {
    if (cell.value === null || cell.value === undefined) {
      return '';
    }

    // Handle rich text
    if (typeof cell.value === 'object' && cell.value.richText) {
      return cell.value.richText.map(rt => rt.text).join('');
    }

    // Handle dates
    if (cell.value instanceof Date) {
      const d = cell.value;
      return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(-2)}`;
    }

    return String(cell.value);
  }

  applyCellStyles(td, cell, isLabelColumn) {
    const styles = [];

    // Background color from fill
    if (cell.fill && cell.fill.fgColor) {
      const color = this.argbToHex(cell.fill.fgColor);
      if (color && color !== '#000000') {
        styles.push(`background-color: ${color}`);
      }
    }

    // Font styles (skip font-size to let CSS control it)
    if (cell.font) {
      if (cell.font.bold) {
        styles.push('font-weight: bold');
      }
      if (cell.font.color) {
        const fontColor = this.argbToHex(cell.font.color);
        if (fontColor) {
          styles.push(`color: ${fontColor}`);
        }
      }
    }

    // Alignment
    if (cell.alignment) {
      if (cell.alignment.horizontal) {
        styles.push(`text-align: ${cell.alignment.horizontal}`);
      }
      if (cell.alignment.vertical) {
        styles.push(`vertical-align: ${cell.alignment.vertical}`);
      }
      if (cell.alignment.wrapText) {
        styles.push('white-space: normal');
      }
    }

    // Apply label column class
    if (isLabelColumn) {
      td.className = 'label-cell';
    }

    if (styles.length > 0) {
      td.style.cssText = styles.join('; ');
    }
  }

  argbToHex(colorObj) {
    if (!colorObj) return null;

    // Handle theme colors (approximate)
    if (colorObj.theme !== undefined) {
      // Theme colors - return null to use default styling
      return null;
    }

    // Handle ARGB format (e.g., "FF13B5BD")
    if (colorObj.argb) {
      const argb = colorObj.argb;
      // Skip alpha, take RGB (lowercase for CSS matching)
      return '#' + argb.substring(2).toLowerCase();
    }

    return null;
  }

  createToolbar() {
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

    // Download button handler
    downloadBtn.addEventListener('click', () => {
      this.container.dispatchEvent(new CustomEvent('download-excel', {
        detail: { plan: this.plan },
        bubbles: true
      }));
    });

    return toolbar;
  }

  showLoading(container) {
    container.textContent = '';

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'xlsx-preview-loading';

    const track = document.createElement('div');
    track.className = 'loading-track';

    const runner = document.createElement('div');
    runner.className = 'loading-runner';
    track.appendChild(runner);

    const status = document.createElement('p');
    status.className = 'loading-status';
    status.textContent = 'Rendering preview...';

    loadingDiv.appendChild(track);
    loadingDiv.appendChild(status);
    container.appendChild(loadingDiv);
  }

  showError(container, message) {
    container.textContent = '';

    const errorDiv = document.createElement('div');
    errorDiv.className = 'xlsx-preview-error';

    const errorMsg = document.createElement('p');
    errorMsg.textContent = `Failed to load preview: ${message}`;
    errorDiv.appendChild(errorMsg);

    const fallback = document.createElement('p');
    fallback.textContent = 'You can still download the Excel file using the button above.';
    errorDiv.appendChild(fallback);

    container.appendChild(errorDiv);
  }

  async fetchExcelBlob() {
    const response = await fetch(`${API_BASE}/api/download-excel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: this.plan })
    });

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    return await response.blob();
  }

  getCachedBlob() {
    return this.cachedBlob;
  }

  updatePlan(newPlan) {
    this.plan = newPlan;
    this.cachedBlob = null;
    this.render();
  }

  getPlan() {
    return this.plan;
  }

  destroy() {
    if (this.container) {
      this.container.textContent = '';
    }
    this.cachedBlob = null;
  }
}

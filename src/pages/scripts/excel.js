/**
 * Excel generation using ExcelJS
 * Creates 52-week periodized training plans with proper formatting
 */

// Phase colors (ARGB format for ExcelJS)
const COLORS = {
  generalPrep: 'FFFF9900',  // Orange
  specialPrep: 'FFFFDD00',  // Yellow
  competition: 'FF00CC66',  // Green
  taper: 'FFD9D9D9',        // Grey

  // Training load colors
  load4: 'FFE74C3C',  // Red - High
  load3: 'FFF39C12',  // Orange - Medium-high
  load2: 'FFF1C40F',  // Yellow - Medium
  load1: 'FF2ECC71',  // Green - Low
  load0: 'FFECF0F1',  // Light grey - Rest

  // Header colors
  header: 'FF2C3E50',
  weekHeader: 'FF1ABC9C',  // Teal
  monthHeader: 'FF1ABC9C',
  blockHeader: 'FFB4C6E7',  // Light blue
};

// Row definitions
const ROWS = {
  goals: 1,
  title: 2,
  month: 3,
  week: 4,
  weekCommencing: 5,
  competitionsLabel: 6,
  importance: 7,
  competitionDetail: 8,
  tests: 9,
  monitoring: 10,
  periods: 11,
  phases: 12,
  technical: 13,
  tactical: 14,
  physical: 15,
  psychological: 16,
  microcycles: 17,
  blockName: 18,        // Block names row (merged cells)
  blockIntensity4: 19,  // Intensity level 4 (red)
  blockIntensity3: 20,  // Intensity level 3 (orange)
  blockIntensity2: 21,  // Intensity level 2 (yellow)
  blockIntensity1: 22,  // Intensity level 1 (green)
};

const DATA_START_COL = 2; // Column B (1-indexed)

/**
 * Generate Excel workbook from plan data
 */
export async function generateExcel(plan) {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Athletics Annual Plan';
  workbook.created = new Date();

  const ws = workbook.addWorksheet('Annual Plan', {
    views: [{ state: 'frozen', xSplit: 1, ySplit: 5 }]
  });

  // Set column widths
  ws.getColumn(1).width = 18; // Labels column
  for (let i = 0; i < 52; i++) {
    ws.getColumn(DATA_START_COL + i).width = 12;
  }

  // Add row labels
  addRowLabels(ws);

  // Add title row
  addTitleRow(ws, plan);

  // Add month headers
  addMonthHeaders(ws, plan);

  // Add week numbers and dates
  addWeekData(ws, plan);

  // Add competitions
  addCompetitions(ws, plan);

  // Add phases with colors
  addPhases(ws, plan);

  // Add training blocks (includes intensity visualization)
  addBlocks(ws, plan);

  // Add focus areas (technical, physical, etc.)
  addFocusAreas(ws, plan);

  // Apply consistent borders
  applyBorders(ws, plan);

  // Generate buffer
  const buffer = await workbook.xlsx.writeBuffer();

  return buffer;
}

/**
 * Add row labels in column A
 */
function addRowLabels(ws) {
  const labels = {
    [ROWS.goals]: 'Goals',
    [ROWS.title]: 'Annual Plan',
    [ROWS.month]: 'Month',
    [ROWS.week]: 'Week',
    [ROWS.weekCommencing]: 'Week Commencing',
    [ROWS.competitionsLabel]: 'Competitions',
    [ROWS.importance]: 'Importance',
    [ROWS.competitionDetail]: 'Detail',
    [ROWS.tests]: 'Tests',
    [ROWS.monitoring]: 'Monitoring',
    [ROWS.periods]: 'Periods',
    [ROWS.phases]: 'Phases',
    [ROWS.technical]: 'Technical',
    [ROWS.tactical]: 'Tactical',
    [ROWS.physical]: 'Physical',
    [ROWS.psychological]: 'Psychological',
    [ROWS.microcycles]: 'Microcycles',
    [ROWS.blockName]: 'Block',
    [ROWS.blockIntensity4]: '',
    [ROWS.blockIntensity3]: '',
    [ROWS.blockIntensity2]: '',
    [ROWS.blockIntensity1]: '',
  };

  for (const [row, label] of Object.entries(labels)) {
    const cell = ws.getCell(parseInt(row), 1);
    cell.value = label;
    cell.font = { bold: true, size: 10 };
    cell.alignment = { vertical: 'middle' };
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFF5F5F5' }
    };
  }
}

/**
 * Add title row
 */
function addTitleRow(ws, plan) {
  const cell = ws.getCell(ROWS.title, DATA_START_COL);
  cell.value = `${plan.athlete} - ${plan.season}`;
  cell.font = { bold: true, size: 14 };
  cell.alignment = { horizontal: 'left', vertical: 'middle' };

  // Merge across several columns for the title
  ws.mergeCells(ROWS.title, DATA_START_COL, ROWS.title, DATA_START_COL + 10);
}

/**
 * Add month headers with merged cells
 */
function addMonthHeaders(ws, plan) {
  const weeks = plan.weeks || [];
  let currentMonth = null;
  let monthStartCol = DATA_START_COL;

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;
    const weekMonth = week.month;

    if (weekMonth !== currentMonth) {
      // If we had a previous month, merge it
      if (currentMonth !== null && col > monthStartCol) {
        // Apply fill to all cells first
        for (let c = monthStartCol; c < col; c++) {
          const monthCell = ws.getCell(ROWS.month, c);
          monthCell.fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: COLORS.monthHeader }
          };
        }
        // Then merge
        if (col - monthStartCol > 1) {
          ws.mergeCells(ROWS.month, monthStartCol, ROWS.month, col - 1);
        }
        ws.getCell(ROWS.month, monthStartCol).value = currentMonth;
        ws.getCell(ROWS.month, monthStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
        ws.getCell(ROWS.month, monthStartCol).font = { bold: true, color: { argb: 'FFFFFFFF' } };
      }
      currentMonth = weekMonth;
      monthStartCol = col;
    }
  }

  // Handle last month
  if (currentMonth !== null) {
    const endCol = DATA_START_COL + weeks.length - 1;
    for (let c = monthStartCol; c <= endCol; c++) {
      const monthCell = ws.getCell(ROWS.month, c);
      monthCell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: COLORS.monthHeader }
      };
    }
    if (endCol >= monthStartCol) {
      if (endCol > monthStartCol) {
        ws.mergeCells(ROWS.month, monthStartCol, ROWS.month, endCol);
      }
      ws.getCell(ROWS.month, monthStartCol).value = currentMonth;
      ws.getCell(ROWS.month, monthStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
      ws.getCell(ROWS.month, monthStartCol).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    }
  }
}

/**
 * Add week numbers and dates
 */
function addWeekData(ws, plan) {
  const weeks = plan.weeks || [];

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;

    // Week number
    const weekCell = ws.getCell(ROWS.week, col);
    weekCell.value = week.weekNum;
    weekCell.alignment = { horizontal: 'center', vertical: 'middle' };
    weekCell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: COLORS.weekHeader }
    };
    weekCell.font = { bold: true, color: { argb: 'FFFFFFFF' } };

    // Week commencing date
    const dateCell = ws.getCell(ROWS.weekCommencing, col);
    if (week.startDate) {
      const date = new Date(week.startDate);
      dateCell.value = formatDate(date);
    }
    dateCell.alignment = { horizontal: 'center', vertical: 'middle' };
    dateCell.font = { size: 9 };

    // Microcycles (repeat week number)
    const microCell = ws.getCell(ROWS.microcycles, col);
    microCell.value = week.weekNum;
    microCell.alignment = { horizontal: 'center', vertical: 'middle' };
    microCell.font = { size: 9 };
  }
}

/**
 * Add competitions
 */
function addCompetitions(ws, plan) {
  const weeks = plan.weeks || [];

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;

    if (week.competitions && week.competitions.length > 0) {
      // Competition detail
      const detailCell = ws.getCell(ROWS.competitionDetail, col);
      detailCell.value = week.competitions.join(', ');
      detailCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
      detailCell.font = { size: 9, bold: true };

      // Importance rating
      if (week.competitionImportance) {
        const impCell = ws.getCell(ROWS.importance, col);
        impCell.value = week.competitionImportance;
        impCell.alignment = { horizontal: 'center', vertical: 'middle' };

        // Color code by importance
        const impColors = {
          1: 'FFE74C3C',  // Major - Red
          2: 'FFF39C12',  // Moderate - Orange
          3: 'FF3498DB',  // Minor - Blue
        };
        impCell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: impColors[week.competitionImportance] || 'FFFFFFFF' }
        };
        impCell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      }
    }
  }
}

/**
 * Add phases with color coding
 */
function addPhases(ws, plan) {
  const weeks = plan.weeks || [];
  let currentPhase = null;
  let phaseStartCol = DATA_START_COL;

  const phaseColors = {
    'general-prep': COLORS.generalPrep,
    'special-prep': COLORS.specialPrep,
    'competition': COLORS.competition,
    'taper': COLORS.taper,
  };

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;
    const phaseName = week.phase;
    const phaseType = week.phaseType;

    if (phaseName !== currentPhase) {
      // Merge previous phase cells
      if (currentPhase !== null && col > phaseStartCol) {
        const prevPhaseType = weeks[i - 1]?.phaseType;
        const color = phaseColors[prevPhaseType] || COLORS.taper;

        // Apply fill to all cells before merging
        for (let c = phaseStartCol; c < col; c++) {
          const phaseCell = ws.getCell(ROWS.phases, c);
          phaseCell.fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: color }
          };
        }

        if (col - phaseStartCol > 1) {
          ws.mergeCells(ROWS.phases, phaseStartCol, ROWS.phases, col - 1);
        }
        ws.getCell(ROWS.phases, phaseStartCol).value = currentPhase;
        ws.getCell(ROWS.phases, phaseStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
        ws.getCell(ROWS.phases, phaseStartCol).font = { bold: true };
      }
      currentPhase = phaseName;
      phaseStartCol = col;
    }
  }

  // Handle last phase
  if (currentPhase !== null) {
    const endCol = DATA_START_COL + weeks.length - 1;
    const lastPhaseType = weeks[weeks.length - 1]?.phaseType;
    const color = phaseColors[lastPhaseType] || COLORS.taper;

    for (let c = phaseStartCol; c <= endCol; c++) {
      const phaseCell = ws.getCell(ROWS.phases, c);
      phaseCell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: color }
      };
    }

    if (endCol > phaseStartCol) {
      ws.mergeCells(ROWS.phases, phaseStartCol, ROWS.phases, endCol);
    }
    ws.getCell(ROWS.phases, phaseStartCol).value = currentPhase;
    ws.getCell(ROWS.phases, phaseStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
    ws.getCell(ROWS.phases, phaseStartCol).font = { bold: true };
  }
}

/**
 * Add training blocks with intensity visualization.
 * Creates a block section with:
 * - Top row: Block names (merged cells, light blue background)
 * - 4 rows below: Intensity levels (4, 3, 2, 1) showing weekly load
 *   in a stacked bar style visualization
 */
function addBlocks(ws, plan) {
  const weeks = plan.weeks || [];
  let currentBlock = null;
  let blockStartCol = DATA_START_COL;

  // First pass: Add block name headers (merged cells)
  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;
    const blockName = week.block;

    if (blockName !== currentBlock) {
      // Merge previous block cells
      if (currentBlock !== null && col > blockStartCol) {
        for (let c = blockStartCol; c < col; c++) {
          const blockCell = ws.getCell(ROWS.blockName, c);
          blockCell.fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: COLORS.blockHeader }
          };
        }

        if (col - blockStartCol > 1) {
          ws.mergeCells(ROWS.blockName, blockStartCol, ROWS.blockName, col - 1);
        }
        ws.getCell(ROWS.blockName, blockStartCol).value = currentBlock;
        ws.getCell(ROWS.blockName, blockStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
        ws.getCell(ROWS.blockName, blockStartCol).font = { bold: true };
      }
      currentBlock = blockName;
      blockStartCol = col;
    }
  }

  // Handle last block name
  if (currentBlock !== null) {
    const endCol = DATA_START_COL + weeks.length - 1;
    for (let c = blockStartCol; c <= endCol; c++) {
      const blockCell = ws.getCell(ROWS.blockName, c);
      blockCell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: COLORS.blockHeader }
      };
    }

    if (endCol > blockStartCol) {
      ws.mergeCells(ROWS.blockName, blockStartCol, ROWS.blockName, endCol);
    }
    ws.getCell(ROWS.blockName, blockStartCol).value = currentBlock;
    ws.getCell(ROWS.blockName, blockStartCol).alignment = { horizontal: 'center', vertical: 'middle' };
    ws.getCell(ROWS.blockName, blockStartCol).font = { bold: true };
  }

  // Second pass: Add intensity visualization rows (stacked bar style)
  // Map intensity level to its corresponding row
  const intensityRows = {
    4: ROWS.blockIntensity4,
    3: ROWS.blockIntensity3,
    2: ROWS.blockIntensity2,
    1: ROWS.blockIntensity1,
  };

  const loadColors = {
    4: COLORS.load4,
    3: COLORS.load3,
    2: COLORS.load2,
    1: COLORS.load1,
  };

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;
    const load = week.load ?? 2; // Default to load 2 if not specified

    // Only display intensity if it's 1-4
    if (intensityRows[load]) {
      const intensityRow = intensityRows[load];
      const cell = ws.getCell(intensityRow, col);
      cell.value = load;
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
      cell.font = { bold: true };
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: loadColors[load] || COLORS.load2 }
      };
    }
  }
}

/**
 * Add focus areas (technical, physical)
 */
function addFocusAreas(ws, plan) {
  const weeks = plan.weeks || [];

  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;

    // Technical focus
    if (week.technical) {
      const techCell = ws.getCell(ROWS.technical, col);
      techCell.value = week.technical;
      techCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
      techCell.font = { size: 9 };
    }

    // Physical focus
    if (week.physical) {
      const physCell = ws.getCell(ROWS.physical, col);
      physCell.value = week.physical;
      physCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
      physCell.font = { size: 9 };
    }
  }
}

/**
 * Apply borders to the worksheet
 */
function applyBorders(ws, plan) {
  const weeks = plan.weeks || [];
  const endCol = DATA_START_COL + weeks.length - 1;

  const thinBorder = { style: 'thin', color: { argb: 'FFD0D0D0' } };

  // Apply borders to all data cells (including block intensity rows)
  for (let row = ROWS.month; row <= ROWS.blockIntensity1; row++) {
    for (let col = 1; col <= endCol; col++) {
      const cell = ws.getCell(row, col);
      cell.border = {
        top: thinBorder,
        left: thinBorder,
        bottom: thinBorder,
        right: thinBorder,
      };
    }
  }

  // Add thicker borders between months
  let currentMonth = null;
  for (let i = 0; i < weeks.length; i++) {
    const week = weeks[i];
    const col = DATA_START_COL + i;

    if (week.month !== currentMonth && currentMonth !== null) {
      // Add thick left border to this column for month and week rows
      const thickBorder = { style: 'medium', color: { argb: 'FF000000' } };
      for (let row = ROWS.month; row <= ROWS.week; row++) {
        const cell = ws.getCell(row, col);
        cell.border = {
          ...cell.border,
          left: thickBorder,
        };
      }
    }
    currentMonth = week.month;
  }
}

/**
 * Format date as dd.mm.yy
 */
function formatDate(date) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = String(date.getFullYear()).slice(-2);
  return `${day}.${month}.${year}`;
}

/**
 * Download the Excel file
 */
export async function downloadPlan(plan) {
  const buffer = await generateExcel(plan);

  // Create blob and download
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${plan.athlete.replace(/[^a-z0-9]/gi, '_')}_Annual_Plan_${plan.season.replace('/', '-')}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

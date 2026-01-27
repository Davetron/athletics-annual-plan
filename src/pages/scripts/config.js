/**
 * API configuration
 *
 * Determines the API base URL based on the current environment.
 * - In development: Points to Python FastAPI backend on port 8000
 * - In production: Uses relative paths (same origin)
 */

export const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : '';

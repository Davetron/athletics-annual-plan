/**
 * API configuration
 *
 * Determines the API base URL based on the current environment.
 * - In development: Points to Python FastAPI backend on port 8000
 * - In production: Points to Cloudflare Worker
 */

export const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://athletics-annual-plan-api.dave-connolly.workers.dev';

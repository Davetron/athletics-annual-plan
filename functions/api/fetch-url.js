/**
 * POST /api/fetch-url
 * Fetches a URL and returns the text content for Claude to parse
 */

export async function onRequestPost(context) {
  const { request } = context;

  try {
    const { url } = await request.json();

    if (!url) {
      return jsonResponse({ error: 'URL is required' }, 400);
    }

    // Validate URL
    let parsedUrl;
    try {
      parsedUrl = new URL(url);
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
        throw new Error('Invalid protocol');
      }
    } catch {
      return jsonResponse({ error: 'Invalid URL' }, 400);
    }

    // Fetch the URL
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; AthleticsAnnualPlan/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      },
    });

    if (!response.ok) {
      return jsonResponse({
        error: `Failed to fetch URL: ${response.status} ${response.statusText}`
      }, 502);
    }

    const html = await response.text();

    // Simple HTML to text conversion - strip tags but keep structure
    const text = htmlToText(html);

    // Limit response size to avoid overwhelming Claude
    const maxLength = 15000;
    const truncated = text.length > maxLength;
    const content = truncated ? text.substring(0, maxLength) + '\n\n[Content truncated...]' : text;

    return jsonResponse({
      success: true,
      url: url,
      content: content,
      truncated: truncated,
      originalLength: text.length
    }, 200);

  } catch (error) {
    console.error('Fetch URL error:', error);
    return jsonResponse({ error: 'Failed to fetch URL: ' + error.message }, 500);
  }
}

/**
 * Convert HTML to readable text
 */
function htmlToText(html) {
  // Remove script and style elements
  let text = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
  text = text.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
  text = text.replace(/<head[^>]*>[\s\S]*?<\/head>/gi, '');

  // Convert common elements to text equivalents
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<\/p>/gi, '\n\n');
  text = text.replace(/<\/div>/gi, '\n');
  text = text.replace(/<\/tr>/gi, '\n');
  text = text.replace(/<\/li>/gi, '\n');
  text = text.replace(/<\/h[1-6]>/gi, '\n\n');
  text = text.replace(/<td[^>]*>/gi, '\t');
  text = text.replace(/<th[^>]*>/gi, '\t');

  // Remove remaining HTML tags
  text = text.replace(/<[^>]+>/g, '');

  // Decode HTML entities
  text = text.replace(/&nbsp;/gi, ' ');
  text = text.replace(/&amp;/gi, '&');
  text = text.replace(/&lt;/gi, '<');
  text = text.replace(/&gt;/gi, '>');
  text = text.replace(/&quot;/gi, '"');
  text = text.replace(/&#39;/gi, "'");
  text = text.replace(/&rsquo;/gi, "'");
  text = text.replace(/&lsquo;/gi, "'");
  text = text.replace(/&rdquo;/gi, '"');
  text = text.replace(/&ldquo;/gi, '"');
  text = text.replace(/&ndash;/gi, '–');
  text = text.replace(/&mdash;/gi, '—');

  // Clean up whitespace
  text = text.replace(/\t+/g, '\t');
  text = text.replace(/[ ]+/g, ' ');
  text = text.replace(/\n[ \t]+/g, '\n');
  text = text.replace(/[ \t]+\n/g, '\n');
  text = text.replace(/\n{3,}/g, '\n\n');

  return text.trim();
}

function jsonResponse(data, status) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

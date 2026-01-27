/**
 * Chat interface for communicating with Claude
 * Uses DOMPurify for safe HTML rendering
 *
 * Supports two chat modes:
 * 1. Discovery chat (Step 2) - Competition discovery with constrained scope
 * 2. Preview chat (Step 3) - Side-by-side discussion about the plan
 */

import {
  SYSTEM_PROMPT,
  PLAN_DISCUSSION_PROMPT,
  createInitialContext,
  createPlanContext
} from './system-prompt.js';
import { API_BASE } from './config.js';

class ChatManager {
  constructor() {
    this.messages = [];
    this.previewMessages = []; // Separate history for preview chat
    this.isLoading = false;
    this.formData = null;
    this.plan = null;
    this.onPlanReady = null;
    this.onPlanUpdate = null;
    this.currentMode = 'discovery'; // 'discovery' or 'preview'

    // Discovery chat DOM elements (Step 2)
    this.messagesContainer = document.getElementById('chat-messages');
    this.inputField = document.getElementById('chat-input');
    this.sendButton = document.getElementById('chat-send');

    // Preview chat DOM elements (Step 3)
    this.previewMessagesContainer = document.getElementById('preview-chat-messages');
    this.previewInputField = document.getElementById('preview-chat-input');
    this.previewSendButton = document.getElementById('preview-chat-send');

    this.setupEventListeners();
  }

  setupEventListeners() {
    // Discovery chat (Step 2)
    this.sendButton?.addEventListener('click', () => this.sendMessage());
    this.inputField?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Preview chat (Step 3)
    this.previewSendButton?.addEventListener('click', () => this.sendPreviewMessage());
    this.previewInputField?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendPreviewMessage();
      }
    });
  }

  /**
   * Initialize discovery chat with form data
   */
  async startConversation(formData) {
    this.messages = [];
    this.plan = null;
    this.formData = formData;
    this.currentMode = 'discovery';
    this.messagesContainer.textContent = '';

    // Create initial context message
    const initialMessage = createInitialContext(formData);

    // Add to messages array (will be sent as user message)
    this.messages.push({
      role: 'user',
      content: initialMessage
    });

    // Show the initial context as a user message
    this.renderMessage('user', initialMessage, this.messagesContainer);

    // Send to Claude
    await this.sendToAPI();
  }

  /**
   * Initialize preview chat for plan discussion (Step 3)
   */
  initPreviewChat(plan) {
    this.currentMode = 'preview';
    this.plan = plan;
    this.previewMessages = [];

    if (this.previewMessagesContainer) {
      this.previewMessagesContainer.textContent = '';
    }

    // Add initial AI message about the plan
    const welcomeMessage = `Your 52-week plan is ready. You can:
- **Click competition cells** to add or edit competitions
- **Paint phases** using the toolbar buttons
- **Click load cells** to cycle training intensity (0-4)
- **Download** your plan as Excel when ready

Ask me anything about the periodization, or let me know if you want to make changes!`;

    this.previewMessages.push({
      role: 'assistant',
      content: welcomeMessage
    });

    this.renderMessage('assistant', welcomeMessage, this.previewMessagesContainer);
  }

  /**
   * Update plan context for preview chat
   */
  updatePlanContext(plan) {
    this.plan = plan;
  }

  /**
   * Send message in discovery chat (Step 2)
   */
  async sendMessage() {
    const content = this.inputField.value.trim();
    if (!content || this.isLoading) return;

    // Clear input
    this.inputField.value = '';

    // Add to messages
    this.messages.push({ role: 'user', content });

    // Render user message
    this.renderMessage('user', content, this.messagesContainer);

    // Send to API
    await this.sendToAPI();
  }

  /**
   * Send message in preview chat (Step 3)
   */
  async sendPreviewMessage() {
    const content = this.previewInputField.value.trim();
    if (!content || this.isLoading) return;

    // Clear input
    this.previewInputField.value = '';

    // Add plan context to message
    const planContext = createPlanContext(this.plan);
    const messageWithContext = content + planContext;

    // Add to preview messages (store original for display)
    this.previewMessages.push({ role: 'user', content });

    // Render user message
    this.renderMessage('user', content, this.previewMessagesContainer);

    // Send to API with plan context
    await this.sendToPreviewAPI(messageWithContext);
  }

  /**
   * Send messages to Claude API (Discovery mode)
   */
  async sendToAPI() {
    this.isLoading = true;
    this.inputField.disabled = true;
    this.sendButton.disabled = true;

    // Show typing indicator
    const typingEl = this.showTypingIndicator(this.messagesContainer);

    try {
      const sessionId = sessionStorage.getItem('sessionId');

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId || ''
        },
        body: JSON.stringify({
          system: SYSTEM_PROMPT,
          messages: this.messages
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `API error: ${response.status}`);
      }

      const data = await response.json();

      // Remove typing indicator
      typingEl.remove();

      // Extract assistant message
      const assistantContent = data.content?.[0]?.text || data.content || '';

      // Add to messages
      this.messages.push({ role: 'assistant', content: assistantContent });

      // Render assistant message
      this.renderMessage('assistant', assistantContent, this.messagesContainer);

      // Check for URL fetch request
      const fetchRequest = this.extractFetchRequest(assistantContent);
      if (fetchRequest) {
        await this.handleFetchRequest(fetchRequest);
      }

    } catch (error) {
      console.error('Chat error:', error);
      typingEl.remove();
      this.renderMessage('assistant', `Sorry, there was an error: ${error.message}. Please try again.`, this.messagesContainer);
    } finally {
      this.isLoading = false;
      this.inputField.disabled = false;
      this.sendButton.disabled = false;
      this.inputField.focus();
    }
  }

  /**
   * Send messages to Claude API (Preview mode - plan discussion)
   */
  async sendToPreviewAPI(content) {
    this.isLoading = true;
    this.previewInputField.disabled = true;
    this.previewSendButton.disabled = true;

    // Show typing indicator
    const typingEl = this.showTypingIndicator(this.previewMessagesContainer);

    try {
      const sessionId = sessionStorage.getItem('sessionId');

      // Build messages for preview chat
      const apiMessages = this.previewMessages.map(m => ({
        role: m.role,
        content: m.content
      }));

      // Replace last user message with context-enhanced version
      apiMessages[apiMessages.length - 1] = {
        role: 'user',
        content: content
      };

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId || ''
        },
        body: JSON.stringify({
          system: PLAN_DISCUSSION_PROMPT,
          messages: apiMessages
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `API error: ${response.status}`);
      }

      const data = await response.json();

      // Remove typing indicator
      typingEl.remove();

      // Extract assistant message
      const assistantContent = data.content?.[0]?.text || data.content || '';

      // Add to preview messages
      this.previewMessages.push({ role: 'assistant', content: assistantContent });

      // Render assistant message
      this.renderMessage('assistant', assistantContent, this.previewMessagesContainer);

    } catch (error) {
      console.error('Preview chat error:', error);
      typingEl.remove();
      this.renderMessage('assistant', `Sorry, there was an error: ${error.message}`, this.previewMessagesContainer);
    } finally {
      this.isLoading = false;
      this.previewInputField.disabled = false;
      this.previewSendButton.disabled = false;
      this.previewInputField.focus();
    }
  }

  /**
   * Generate plan by calling the dedicated generation endpoint
   */
  async generatePlan() {
    if (!this.formData) {
      console.error('No form data available');
      return null;
    }

    const sessionId = sessionStorage.getItem('sessionId');

    try {
      const response = await fetch(`${API_BASE}/api/generate-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId || ''
        },
        body: JSON.stringify({
          formData: this.formData,
          messages: this.messages
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Generation failed: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.plan) {
        this.plan = data.plan;
        return data.plan;
      }

      throw new Error('No plan in response');

    } catch (error) {
      console.error('Generate plan error:', error);
      throw error;
    }
  }

  /**
   * Regenerate plan after major changes (e.g., A-priority competition change)
   */
  async regeneratePlan(currentPlan) {
    if (!this.formData) {
      console.error('No form data available');
      return null;
    }

    const sessionId = sessionStorage.getItem('sessionId');

    try {
      // Add current plan state to messages for context
      const contextMessage = `The plan has been modified. Current competitions: ${
        currentPlan.weeks
          .filter(w => w.competitions?.length > 0)
          .map(w => `${w.competitions.join(', ')} (Week ${w.weekNum}, ${w.competitionImportance === 1 ? 'A' : w.competitionImportance === 2 ? 'B' : 'C'})`)
          .join('; ') || 'None'
      }. Please regenerate the periodization to optimize around these competitions.`;

      const messagesWithContext = [
        ...this.messages,
        { role: 'user', content: contextMessage }
      ];

      const response = await fetch(`${API_BASE}/api/generate-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId || ''
        },
        body: JSON.stringify({
          formData: this.formData,
          messages: messagesWithContext
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Regeneration failed: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.plan) {
        this.plan = data.plan;
        return data.plan;
      }

      throw new Error('No plan in response');

    } catch (error) {
      console.error('Regenerate plan error:', error);
      throw error;
    }
  }

  /**
   * Render a message in the chat using safe DOM methods
   */
  renderMessage(role, content, container) {
    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${role}`;

    const senderEl = document.createElement('span');
    senderEl.className = 'message-sender';
    senderEl.textContent = role === 'user' ? 'You' : 'Coach AI';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    if (role === 'assistant') {
      // Remove fetch code blocks from display (they're for parsing only)
      let displayContent = content.replace(/```fetch[\s\S]*?```/g, '').trim();

      if (displayContent) {
        // Parse markdown and sanitize with DOMPurify (safe HTML rendering)
        // Security: DOMPurify.sanitize ensures all HTML is safe before insertion
        const rawHtml = marked.parse(displayContent);
        const cleanHtml = DOMPurify.sanitize(rawHtml, {
          ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'h1', 'h2', 'h3', 'h4'],
          ALLOWED_ATTR: []
        });
        // Safe: content is sanitized by DOMPurify above with strict allowlist
        contentEl.insertAdjacentHTML('beforeend', cleanHtml);
      }
    } else {
      // For user messages, use textContent for safety, then replace newlines
      const lines = content.split('\n');
      lines.forEach((line, index) => {
        // Handle markdown-style bold (**text**)
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        parts.forEach(part => {
          if (part.startsWith('**') && part.endsWith('**')) {
            const strong = document.createElement('strong');
            strong.textContent = part.slice(2, -2);
            contentEl.appendChild(strong);
          } else {
            contentEl.appendChild(document.createTextNode(part));
          }
        });
        if (index < lines.length - 1) {
          contentEl.appendChild(document.createElement('br'));
        }
      });
    }

    messageEl.appendChild(senderEl);
    messageEl.appendChild(contentEl);
    container.appendChild(messageEl);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
  }

  /**
   * Show typing indicator
   */
  showTypingIndicator(container) {
    const indicator = document.createElement('div');
    indicator.className = 'chat-message assistant';

    const senderEl = document.createElement('span');
    senderEl.className = 'message-sender';
    senderEl.textContent = 'Coach AI';

    const typingEl = document.createElement('div');
    typingEl.className = 'typing-indicator';
    for (let i = 0; i < 3; i++) {
      typingEl.appendChild(document.createElement('span'));
    }

    indicator.appendChild(senderEl);
    indicator.appendChild(typingEl);
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
    return indicator;
  }

  /**
   * Get the current plan if available
   */
  getPlan() {
    return this.plan;
  }

  /**
   * Extract fetch request from Claude's response
   */
  extractFetchRequest(content) {
    const fetchMatch = content.match(/```fetch\s*([\s\S]*?)\s*```/);
    if (!fetchMatch) return null;

    try {
      const data = JSON.parse(fetchMatch[1]);
      if (data.url) {
        return data.url;
      }
    } catch (e) {
      console.error('Failed to parse fetch request:', e);
    }

    return null;
  }

  /**
   * Handle URL fetch request from Claude
   */
  async handleFetchRequest(url) {
    // Show a system message that we're fetching
    this.renderSystemMessage(`Fetching content from: ${url}`, this.messagesContainer);

    const typingEl = this.showTypingIndicator(this.messagesContainer);

    try {
      const response = await fetch(`${API_BASE}/api/fetch-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await response.json();
      typingEl.remove();

      if (data.success) {
        // Add the fetched content as a user message (context for Claude)
        const contextMessage = `Here is the content from ${url}:\n\n${data.content}`;
        this.messages.push({ role: 'user', content: contextMessage });

        // Show abbreviated version to user
        this.renderSystemMessage(`Fetched ${data.originalLength} characters from the page. Sending to AI for analysis...`, this.messagesContainer);

        // Send to Claude for analysis
        await this.sendToAPI();
      } else {
        this.renderSystemMessage(`Failed to fetch URL: ${data.error}`, this.messagesContainer);
      }
    } catch (error) {
      typingEl.remove();
      this.renderSystemMessage(`Error fetching URL: ${error.message}`, this.messagesContainer);
    }
  }

  /**
   * Render a system message (not from user or assistant)
   */
  renderSystemMessage(text, container) {
    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message system';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content system-message';
    contentEl.textContent = text;

    messageEl.appendChild(contentEl);
    container.appendChild(messageEl);
    container.scrollTop = container.scrollHeight;
  }
}

// Export singleton instance
export const chatManager = new ChatManager();

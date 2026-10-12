'use strict';

const { generateUrl, modelName } = window.APP_CONFIG;

const els = {
    welcomeScreen: document.getElementById('welcomeScreen'),
    messagesContainer: document.getElementById('messagesContainer'),
    loadingIndicator: document.getElementById('loadingIndicator'),
    messagesEnd: document.getElementById('messagesEnd'),
    clearBtn: document.getElementById('clearBtn'),
    chatForm: document.getElementById('chatForm'),
    messageInput: document.getElementById('messageInput'),
    sendButton: document.getElementById('sendButton'),
    sendIcon: document.getElementById('sendIcon'),
    loadingSpinner: document.getElementById('loadingSpinner'),
};

const ICONS = {
    user: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    ai: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>',
};

let isLoading = false;

// --- Helpers ---------------------------------------------------------------

// Creates an element; text always goes through textContent, so model output is never parsed as HTML.
function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function sentimentLevel(score) {
    if (score < 40) return 'negative';
    if (score > 60) return 'positive';
    return 'neutral';
}

function scrollToBottom() {
    els.messagesEnd.scrollIntoView({ behavior: 'smooth' });
}

// --- Rendering -------------------------------------------------------------

function renderAnalysis(analysis) {
    const card = el('div', 'analysis');

    const summary = el('div', 'analysis-row');
    summary.append(el('span', 'analysis-label', 'Summary'), el('p', 'analysis-value', analysis.summary));

    const meta = el('div', 'analysis-meta');
    meta.append(el('span', 'category-chip', analysis.category));
    const level = sentimentLevel(analysis.sentiment);
    const sentiment = el('div', `sentiment sentiment-${level}`);
    const bar = el('div', 'sentiment-bar');
    const fill = el('div', 'sentiment-fill');
    fill.style.width = `${analysis.sentiment}%`;
    bar.append(fill);
    sentiment.append(el('span', 'sentiment-label', `Sentiment ${analysis.sentiment}/100`), bar);
    meta.append(sentiment);

    const action = el('div', 'analysis-row');
    action.append(el('span', 'analysis-label', 'Recommended action'), el('p', 'analysis-value', analysis.action));

    card.append(summary, meta, action);
    return card;
}

function displayMessage({ type, text, analysis, model, duration, isError }) {
    const message = el('div', `message ${type}${isError ? ' error' : ''}`);
    const wrapper = el('div', 'message-wrapper');

    const header = el('div', 'message-header');
    const avatar = el('div', 'message-avatar');
    avatar.innerHTML = ICONS[type]; // static markup, no user data
    const info = el('div', 'message-info');
    info.append(el('span', 'message-sender', type === 'user' ? 'You' : 'AI Assistant'));
    if (model) info.append(el('span', 'message-model', model));
    header.append(avatar, info);

    const bubble = el('div', 'message-bubble');
    bubble.append(analysis ? renderAnalysis(analysis) : el('div', 'message-text', text));

    const footer = el('div', 'message-footer');
    footer.append(el('span', null, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })));
    if (duration !== undefined) footer.append(el('span', null, `${duration.toFixed(2)}s`));

    wrapper.append(header, bubble, footer);
    message.append(wrapper);
    els.messagesContainer.append(message);
    scrollToBottom();
}

// --- State -----------------------------------------------------------------

function updateSendButton() {
    els.sendButton.disabled = isLoading || els.messageInput.value.trim().length === 0;
}

function setLoadingState(loading) {
    isLoading = loading;
    els.messageInput.disabled = loading;
    els.loadingIndicator.hidden = !loading;
    els.sendIcon.style.display = loading ? 'none' : 'block';
    els.loadingSpinner.hidden = !loading;
    updateSendButton();
    if (loading) {
        scrollToBottom();
    } else {
        els.messageInput.focus();
    }
}

function clearChat() {
    els.messagesContainer.replaceChildren();
    els.welcomeScreen.hidden = false;
    els.clearBtn.hidden = true;
    setLoadingState(false);
}

// --- API -------------------------------------------------------------------

async function sendMessage(content) {
    displayMessage({ type: 'user', text: content });
    els.messageInput.value = '';
    autoResizeTextarea();
    els.welcomeScreen.hidden = true;
    els.clearBtn.hidden = false;
    setLoadingState(true);

    try {
        const response = await fetch(generateUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content }),
        });
        const data = await response.json().catch(() => ({ error: `Unexpected response (HTTP ${response.status})` }));

        if (!response.ok || data.error) {
            displayMessage({ type: 'ai', text: `Error: ${data.error}`, model: modelName, isError: true });
        } else {
            displayMessage({ type: 'ai', analysis: data.analysis, model: data.model, duration: data.duration });
        }
    } catch (error) {
        displayMessage({ type: 'ai', text: `Error: ${error.message}`, model: modelName, isError: true });
    } finally {
        setLoadingState(false);
    }
}

// --- Events ----------------------------------------------------------------

function autoResizeTextarea() {
    els.messageInput.style.height = 'auto';
    els.messageInput.style.height = `${Math.min(els.messageInput.scrollHeight, 128)}px`;
}

function handleSubmit(event) {
    event.preventDefault();
    const content = els.messageInput.value.trim();
    if (!content || isLoading) return;
    sendMessage(content);
}

els.chatForm.addEventListener('submit', handleSubmit);
els.clearBtn.addEventListener('click', clearChat);
els.messageInput.addEventListener('input', () => {
    autoResizeTextarea();
    updateSendButton();
});
els.messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) handleSubmit(event);
});

updateSendButton();

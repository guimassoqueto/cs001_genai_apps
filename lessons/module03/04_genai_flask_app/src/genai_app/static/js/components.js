// Chat message components.
//
// An answer is shown by one of two views with the same interface, so the caller does not
// care whether it streams or how many models answer:
//   update(model, partial)  streaming only: more of the analysis has arrived
//   finish(result)          a model is done (ok or failed)
//   fail(error)             the whole request failed; unfinished cards show the error
//   complete(comparisonId)  every model is done
import { el, timeNow } from './dom.js';

const ICONS = {
    user: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    ai: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>',
};

// --- Message frame -----------------------------------------------------------

function messageShell(type, { badge, extraClass } = {}) {
    const message = el('div', ['message', type, extraClass].filter(Boolean).join(' '));
    const wrapper = el('div', 'message-wrapper');

    const header = el('div', 'message-header');
    const avatar = el('div', 'message-avatar');
    avatar.innerHTML = ICONS[type]; // static markup, no user data
    const info = el('div', 'message-info');
    info.append(el('span', 'message-sender', type === 'user' ? 'You' : 'AI Assistant'));
    if (badge) info.append(el('span', 'message-model', badge));
    header.append(avatar, info);

    const bubble = el('div', 'message-bubble');
    const footer = el('div', 'message-footer');
    footer.append(el('span', null, timeNow()));

    wrapper.append(header, bubble, footer);
    message.append(wrapper);
    return { message, bubble };
}

export function userMessage(text) {
    const { message, bubble } = messageShell('user');
    bubble.append(el('div', 'message-text', text));
    return message;
}

export function errorMessage(error) {
    const { message, bubble } = messageShell('ai', { extraClass: 'error' });
    bubble.append(errorText(error.message, error.requestId));
    return message;
}

// --- Analysis ----------------------------------------------------------------

function sentimentLevel(score) {
    if (score < 40) return 'negative';
    if (score > 60) return 'positive';
    return 'neutral';
}

// Renders whatever fields are present, so it works for a finished analysis and for a
// partial one that is still streaming in.
function renderAnalysis(analysis) {
    const card = el('div', 'analysis');

    if (typeof analysis.summary === 'string') {
        const row = el('div', 'analysis-row');
        row.append(el('span', 'analysis-label', 'Summary'), el('p', 'analysis-value', analysis.summary));
        card.append(row);
    }

    const hasCategory = typeof analysis.category === 'string';
    const hasSentiment = typeof analysis.sentiment === 'number';
    if (hasCategory || hasSentiment) {
        const meta = el('div', 'analysis-meta');
        if (hasCategory) meta.append(el('span', 'category-chip', analysis.category));
        if (hasSentiment) {
            const sentiment = el('div', `sentiment sentiment-${sentimentLevel(analysis.sentiment)}`);
            const bar = el('div', 'sentiment-bar');
            const fill = el('div', 'sentiment-fill');
            fill.style.width = `${Math.min(Math.max(analysis.sentiment, 0), 100)}%`;
            bar.append(fill);
            sentiment.append(el('span', 'sentiment-label', `Sentiment ${analysis.sentiment}/100`), bar);
            meta.append(sentiment);
        }
        card.append(meta);
    }

    if (typeof analysis.action === 'string') {
        const row = el('div', 'analysis-row');
        row.append(el('span', 'analysis-label', 'Recommended action'), el('p', 'analysis-value', analysis.action));
        card.append(row);
    }
    return card;
}

function errorText(message, requestId) {
    const node = el('div', 'result-error', `Error: ${message}`);
    if (requestId) node.append(el('span', 'request-id', ` (request ${requestId.slice(0, 8)})`));
    return node;
}

// Duration, token usage and cache hit for one model result.
function resultMeta(result) {
    const meta = el('div', 'result-meta');
    meta.append(result.cached ? el('span', 'cached-chip', 'cached') : el('span', null, `${result.duration.toFixed(2)}s`));
    if (result.usage) {
        meta.append(el('span', null, `${result.usage.input_tokens} in / ${result.usage.output_tokens} out tokens`));
    }
    return meta;
}

// --- One model's answer ------------------------------------------------------

class ResultCard {
    constructor(label, { titled }) {
        this.element = el('div', 'result-card');
        if (titled) this.element.append(el('span', 'result-card-title', label));
        this.body = el('div', 'result-card-body');
        this.foot = el('div', 'result-card-foot');
        this.element.append(this.body, this.foot);
        this.result = null;
        this.showPending();
    }

    get finished() {
        return this.result !== null || this.element.classList.contains('failed');
    }

    showPending() {
        const pending = el('div', 'pending');
        const dots = el('div', 'pending-dots');
        dots.append(el('div', 'dot'), el('div', 'dot'), el('div', 'dot'));
        pending.append(dots, el('span', null, 'Thinking...'));
        this.body.replaceChildren(pending);
    }

    update(partial) {
        if (this.finished || !Object.keys(partial).length) return;
        this.element.classList.add('streaming');
        this.body.replaceChildren(renderAnalysis(partial));
    }

    finish(result) {
        this.result = result;
        this.element.classList.remove('streaming');
        if (result.ok) {
            this.body.replaceChildren(renderAnalysis(result.analysis));
        } else {
            this.element.classList.add('failed');
            this.body.replaceChildren(errorText(result.error.message));
        }
        this.foot.replaceChildren(resultMeta(result));
    }

    fail(error) {
        if (this.finished) return;
        this.element.classList.remove('streaming');
        this.element.classList.add('failed');
        this.body.replaceChildren(errorText(error.message, error.requestId));
    }

    // Adds a "Prefer" button (successful answers only).
    offerVote(onPrefer) {
        if (!this.result?.ok) return;
        const button = el('button', 'prefer-btn', 'Prefer');
        button.type = 'button';
        button.addEventListener('click', onPrefer);
        this.foot.append(button);
    }

    setPreferred(preferred) {
        this.element.classList.toggle('preferred', preferred);
        const button = this.foot.querySelector('.prefer-btn');
        if (button) button.textContent = preferred ? 'Preferred ✓' : 'Prefer';
    }
}

// --- Views -------------------------------------------------------------------

// One model, answering in a regular chat bubble.
export class SingleAnswer {
    constructor(model) {
        const { message, bubble } = messageShell('ai', { badge: model.label });
        this.element = message;
        this.card = new ResultCard(model.label, { titled: false });
        bubble.append(this.card.element);
    }

    update(_model, partial) {
        this.card.update(partial);
    }

    finish(result) {
        this.card.finish(result);
        this.element.classList.toggle('error', !result.ok);
    }

    fail(error) {
        this.card.fail(error);
        this.element.classList.add('error');
    }

    complete() {}
}

// A/B test: one card per model, side by side, with a vote once every model is done.
export class Comparison {
    // models: [{ id, label }]; onVote(comparisonId, modelId) returns a promise.
    constructor(models, onVote) {
        const { message, bubble } = messageShell('ai', {
            badge: `A/B test · ${models.length} models`,
            extraClass: 'comparison',
        });
        this.element = message;
        this.onVote = onVote;
        this.cards = new Map(models.map((m) => [m.id, new ResultCard(m.label, { titled: true })]));

        const grid = el('div', 'compare-grid');
        grid.append(...[...this.cards.values()].map((card) => card.element));
        bubble.append(grid);
    }

    update(model, partial) {
        this.cards.get(model)?.update(partial);
    }

    finish(result) {
        this.cards.get(result.model)?.finish(result);
    }

    fail(error) {
        this.cards.forEach((card) => card.fail(error));
    }

    complete(comparisonId) {
        if (!comparisonId) return; // nothing to vote on when every model failed
        this.cards.forEach((card, model) => {
            card.offerVote(async () => {
                try {
                    await this.onVote(comparisonId, model);
                } catch {
                    return; // onVote reports the error; keep the previous choice
                }
                this.cards.forEach((other, otherModel) => other.setPreferred(otherModel === model));
            });
        });
    }
}

// Entry point: wires the page together and sends messages.
import { ApiError, requestJson, streamEvents } from './api.js';
import { Comparison, SingleAnswer, errorMessage, userMessage } from './components.js';
import { Controls } from './controls.js';
import { StatsDialog } from './stats.js';

const CONFIG = window.APP_CONFIG;
const MODELS = new Map(CONFIG.models.map((m) => [m.id, m]));

const $ = (id) => document.getElementById(id);
const els = {
    messagesArea: document.querySelector('.messages-area'),
    welcomeScreen: $('welcomeScreen'),
    messagesContainer: $('messagesContainer'),
    clearBtn: $('clearBtn'),
    chatForm: $('chatForm'),
    messageInput: $('messageInput'),
    sendButton: $('sendButton'),
    sendIcon: $('sendIcon'),
    loadingSpinner: $('loadingSpinner'),
};

const controls = new Controls(
    {
        abToggle: $('abToggle'),
        streamToggle: $('streamToggle'),
        singlePicker: $('singlePicker'),
        abPicker: $('abPicker'),
        modelSelect: $('modelSelect'),
        abCheckboxes: [...document.querySelectorAll('input[name="abModels"]')],
        hint: $('controlsHint'),
    },
    updateSendButton,
);

const stats = new StatsDialog(
    { openButton: $('statsBtn'), dialog: $('statsDialog'), closeButton: $('statsClose'), body: $('statsBody') },
    CONFIG.urls.stats,
);

const chat = {
    conversationId: null, // issued by the server with the first answer; the memory lives under it
    inFlight: null, // AbortController of the request being answered
};

const withId = (url, id) => url.replace(CONFIG.idPlaceholder, encodeURIComponent(id));

// --- Sending a message -------------------------------------------------------

async function send(content) {
    const compare = controls.compare;
    const models = controls.models.map((id) => MODELS.get(id));
    const view = compare ? new Comparison(models, vote) : new SingleAnswer(models[0]);

    const url = compare ? CONFIG.urls.compare : CONFIG.urls.generate;
    const body = {
        message: content,
        ...(compare ? { models: models.map((m) => m.id) } : { model: models[0].id }),
        ...(chat.conversationId && { conversation_id: chat.conversationId }),
    };
    chat.inFlight = new AbortController();
    const options = { signal: chat.inFlight.signal };

    append(userMessage(content));
    append(view.element);
    clearInput();
    setBusy(true);

    try {
        if (controls.stream) {
            await receiveStream(url, body, view, options);
        } else {
            await receiveResponse(url, body, view, options);
        }
    } catch (error) {
        if (error.name !== 'AbortError') view.fail(error); // aborted = the chat was cleared
    } finally {
        chat.inFlight = null;
        setBusy(false);
    }
}

// Complete mode: one JSON response once every model has answered.
async function receiveResponse(url, body, view, options) {
    const data = await requestJson(url, { method: 'POST', body, ...options });
    chat.conversationId = data.conversation_id;
    (data.results ?? [data.result]).forEach((result) => view.finish(result));
    view.complete(data.comparison_id);
}

// Streaming mode: Server-Sent Events while the models write.
async function receiveStream(url, body, view, options) {
    for await (const { event, data } of streamEvents(url, { ...body, stream: true }, options)) {
        switch (event) {
            case 'start':
                chat.conversationId = data.conversation_id;
                break;
            case 'delta':
                view.update(data.model, data.partial);
                followScroll();
                break;
            case 'result':
                view.finish(data);
                followScroll();
                break;
            case 'done':
                view.complete(data.comparison_id);
                break;
            case 'error':
                throw new ApiError(data.error.message, data.request_id);
        }
    }
}

async function vote(comparisonId, model) {
    try {
        await requestJson(withId(CONFIG.urls.vote, comparisonId), { method: 'POST', body: { model } });
        stats.refreshIfOpen();
    } catch (error) {
        append(errorMessage(error));
        throw error; // keep the card's previous vote state
    }
}

// --- Chat state --------------------------------------------------------------

function append(element) {
    els.welcomeScreen.hidden = true;
    els.clearBtn.hidden = false;
    els.messagesContainer.append(element);
    els.messagesArea.scrollTop = els.messagesArea.scrollHeight;
}

// Keeps the newest text in view while streaming, unless the user scrolled up to read.
function followScroll() {
    const area = els.messagesArea;
    const nearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 120;
    if (nearBottom) area.scrollTop = area.scrollHeight;
}

function clearChat() {
    chat.inFlight?.abort(); // also stops the models on the server
    const id = chat.conversationId;
    chat.conversationId = null;
    els.messagesContainer.replaceChildren();
    els.welcomeScreen.hidden = false;
    els.clearBtn.hidden = true;
    if (id) {
        // Forget the server-side memory too; a failure only leaves an unused conversation behind.
        requestJson(withId(CONFIG.urls.conversation, id), { method: 'DELETE' }).catch(() => {});
    }
}

// --- Input -------------------------------------------------------------------

function isBusy() {
    return chat.inFlight !== null;
}

function updateSendButton() {
    els.sendButton.disabled = isBusy() || !els.messageInput.value.trim() || !controls.valid;
}

function setBusy(busy) {
    els.messageInput.disabled = busy;
    controls.setDisabled(busy);
    els.sendIcon.style.display = busy ? 'none' : 'block';
    els.loadingSpinner.hidden = !busy;
    updateSendButton();
    if (!busy) els.messageInput.focus();
}

function clearInput() {
    els.messageInput.value = '';
    autoResizeTextarea();
}

function autoResizeTextarea() {
    els.messageInput.style.height = 'auto';
    els.messageInput.style.height = `${Math.min(els.messageInput.scrollHeight, 128)}px`;
}

function handleSubmit(event) {
    event.preventDefault();
    const content = els.messageInput.value.trim();
    if (!content || isBusy() || !controls.valid) return;
    send(content);
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

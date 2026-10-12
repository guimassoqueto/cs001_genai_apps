// HTTP client for the /api endpoints: plain JSON requests and Server-Sent Event streams.

export class ApiError extends Error {
    constructor(message, requestId) {
        super(message);
        this.name = 'ApiError';
        this.requestId = requestId;
    }
}

async function errorFrom(response) {
    const data = await response.json().catch(() => null);
    return new ApiError(
        data?.error?.message || `Unexpected response (HTTP ${response.status})`,
        data?.request_id,
    );
}

// Sends a request and returns the parsed JSON body (null for 204). Throws ApiError on 4xx/5xx.
export async function requestJson(url, { method = 'GET', body, signal } = {}) {
    const response = await fetch(url, {
        method,
        signal,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw await errorFrom(response);
    return response.status === 204 ? null : response.json();
}

// POSTs `body` and yields every Server-Sent Event as { event, data } while it arrives.
// Errors before the stream starts (validation, 4xx) throw ApiError like requestJson.
export async function* streamEvents(url, body, { signal } = {}) {
    const response = await fetch(url, {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(body),
    });
    if (!response.ok) throw await errorFrom(response);
    yield* parseEventStream(response.body);
}

// Splits a text/event-stream body into events. Events are separated by a blank line;
// the server sends one `event:` and one single-line JSON `data:` field per event.
async function* parseEventStream(body) {
    const reader = body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done) return;
        buffer += value;

        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const block = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);

            let event = 'message';
            let data = '';
            for (const line of block.split('\n')) {
                if (line.startsWith('event:')) event = line.slice(6).trim();
                else if (line.startsWith('data:')) data += line.slice(5).trim();
            }
            if (data) yield { event, data: JSON.parse(data) };
        }
    }
}

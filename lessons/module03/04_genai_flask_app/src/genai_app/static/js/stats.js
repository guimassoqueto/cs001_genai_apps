// The "A/B results" dialog: per-model wins, latency and token use.
import { requestJson } from './api.js';
import { el } from './dom.js';

const COLUMNS = ['Model', 'Runs', 'Wins', 'Win rate', 'Avg latency', 'Avg output tokens', 'Errors'];

function percent(value) {
    return value === null ? '-' : `${Math.round(value * 100)}%`;
}

function statsTable(rows) {
    const table = el('table', 'stats-table');
    const head = el('tr');
    COLUMNS.forEach((name) => head.append(el('th', null, name)));
    const thead = el('thead');
    thead.append(head);

    const tbody = el('tbody');
    rows.forEach((row) => {
        const tr = el('tr');
        [
            row.label,
            row.runs,
            `${row.wins} / ${row.votes}`,
            percent(row.win_rate),
            row.avg_duration === null ? '-' : `${row.avg_duration.toFixed(2)}s`,
            row.avg_output_tokens ?? '-',
            row.errors,
        ].forEach((value) => tr.append(el('td', null, String(value))));
        tbody.append(tr);
    });

    table.append(thead, tbody);
    return table;
}

export class StatsDialog {
    // elements: { openButton, dialog, closeButton, body }
    constructor(elements, statsUrl) {
        this.els = elements;
        this.url = statsUrl;

        elements.openButton.addEventListener('click', () => {
            elements.dialog.showModal();
            this.refresh();
        });
        elements.closeButton.addEventListener('click', () => elements.dialog.close());
        elements.dialog.addEventListener('click', (event) => {
            if (event.target === elements.dialog) elements.dialog.close(); // click on the backdrop
        });
    }

    // Reloads the table if the dialog is open (e.g. after a vote).
    refreshIfOpen() {
        if (this.els.dialog.open) this.refresh();
    }

    async refresh() {
        const { body } = this.els;
        body.replaceChildren(el('p', 'stats-empty', 'Loading...'));
        try {
            const data = await requestJson(this.url);
            body.replaceChildren(
                data.models.length
                    ? statsTable(data.models)
                    : el('p', 'stats-empty', 'No A/B tests yet. Switch on A/B test and send a message.'),
            );
        } catch (error) {
            body.replaceChildren(el('p', 'stats-empty', `Could not load results: ${error.message}`));
        }
    }
}

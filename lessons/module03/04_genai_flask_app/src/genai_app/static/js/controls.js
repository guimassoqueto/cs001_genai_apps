// The controls above the message box: A/B and streaming switches, and the model pickers.
// They are remembered in localStorage between visits.

const STORAGE_KEY = 'genai-app:controls';

export class Controls {
    // elements: { abToggle, streamToggle, singlePicker, abPicker, modelSelect, abCheckboxes, hint }
    // onChange: called whenever the selection changes
    constructor(elements, onChange) {
        this.els = elements;
        this.onChange = onChange;

        const inputs = [elements.abToggle, elements.streamToggle, elements.modelSelect, ...elements.abCheckboxes];
        inputs.forEach((input) => input.addEventListener('change', () => {
            this.render();
            this.save();
            this.onChange();
        }));

        this.restore();
        this.render();
    }

    get compare() {
        return this.els.abToggle.checked;
    }

    get stream() {
        return this.els.streamToggle.checked;
    }

    // The models the next message goes to.
    get models() {
        if (!this.compare) return [this.els.modelSelect.value];
        return this.els.abCheckboxes.filter((box) => box.checked).map((box) => box.value);
    }

    get valid() {
        return !this.compare || this.models.length >= 2;
    }

    setDisabled(disabled) {
        this.els.abToggle.disabled = disabled;
        this.els.streamToggle.disabled = disabled;
    }

    render() {
        const { singlePicker, abPicker, hint } = this.els;
        singlePicker.hidden = this.compare;
        abPicker.hidden = !this.compare;

        hint.classList.toggle('warning', !this.valid);
        if (!this.valid) {
            hint.textContent = 'Select at least 2 models to compare.';
            return;
        }
        const delivery = this.stream ? 'streamed as they are written' : 'shown when complete';
        hint.textContent = this.compare
            ? `Each message goes to ${this.models.length} models in parallel, answers ${delivery}. Vote for the best one.`
            : `Answers are ${delivery}. The assistant remembers this conversation until you clear it.`;
    }

    save() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                compare: this.compare,
                stream: this.stream,
                model: this.els.modelSelect.value,
                abModels: this.els.abCheckboxes.filter((box) => box.checked).map((box) => box.value),
            }));
        } catch { /* storage unavailable: settings just won't persist */ }
    }

    restore() {
        let saved = null;
        try {
            saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
        } catch { /* ignore */ }
        if (!saved) return;

        const { abToggle, streamToggle, modelSelect, abCheckboxes } = this.els;
        abToggle.checked = Boolean(saved.compare);
        streamToggle.checked = saved.stream !== false;
        if ([...modelSelect.options].some((o) => o.value === saved.model)) modelSelect.value = saved.model;
        if (Array.isArray(saved.abModels)) {
            abCheckboxes.forEach((box) => { box.checked = saved.abModels.includes(box.value); });
        }
    }
}

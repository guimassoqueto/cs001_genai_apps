from dataclasses import dataclass

# Display names for the models this app knows. Ids not listed here still work; they show as the raw id.
MODEL_LABELS = {
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-fable-5-1": "Claude Fable 5.1",
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "claude-haiku-5-5": "Claude Haiku 5.5",
}


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    label: str


def model_info(model_id: str) -> ModelInfo:
    return ModelInfo(id=model_id, label=MODEL_LABELS.get(model_id, model_id))

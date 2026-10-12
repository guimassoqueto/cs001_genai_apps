from flask import Flask
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

SYSTEM_PROMPT = "You are an AI assistant helping with customer inquiries. Provide a helpful and concise response."


class InquiryAnalysis(BaseModel):
    """Structured triage of one customer message, as returned by the model."""

    summary: str = Field(description="Summary of the user's message")
    sentiment: int = Field(ge=0, le=100, description="Sentiment score from 0 (negative) to 100 (positive)")
    category: str = Field(description="Category of the inquiry (e.g., billing, technical, general)")
    action: str = Field(description="Recommended action for the support rep")


class InquiryAssistant:
    """Runs a customer message through prompt | model | parser and returns a typed analysis."""

    def __init__(self, chat_model: BaseChatModel, model_name: str) -> None:
        self.model_name = model_name
        parser = PydanticOutputParser(pydantic_object=InquiryAnalysis)
        # Fixed values go in through .partial(): the format instructions contain JSON braces
        # that must not be parsed as template variables.
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}\n\n{format_instructions}"),
                ("human", "{message}"),
            ]
        ).partial(system_prompt=SYSTEM_PROMPT, format_instructions=parser.get_format_instructions())
        self._chain = prompt | chat_model | parser

    def analyze(self, message: str) -> InquiryAnalysis:
        return self._chain.invoke({"message": message})


def build_chat_model(app: Flask) -> BaseChatModel:
    return ChatAnthropic(
        model=app.config["ANTHROPIC_MODEL"],
        max_tokens=app.config["ANTHROPIC_MAX_TOKENS"],
        api_key=app.config["ANTHROPIC_API_KEY"],
        timeout=app.config["ANTHROPIC_TIMEOUT"],
    )


def get_assistant(app: Flask) -> InquiryAssistant:
    return app.extensions["assistant"]

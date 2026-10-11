"""LangChain core concepts: chat models, prompt templates, example selectors, output parsers."""

import csv
import json

from langchain_anthropic import ChatAnthropic
from langchain_core.example_selectors import LengthBasedExampleSelector
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import CommaSeparatedListOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotPromptTemplate, PromptTemplate
from pydantic import BaseModel, Field

from app.config.envs import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, doc_path, output_path

model = ChatAnthropic(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)

# Chat models: a conversation is a list of typed messages, not a single string.
conversation = [
    SystemMessage("You are a concise technical writer. Answer in one sentence."),
    HumanMessage("What is LangChain?"),
    AIMessage("LangChain is an open-source framework for building applications on top of LLMs."),
    HumanMessage("Rewrite that for someone who has never written code."),
]
print("[chat model]", model.invoke(conversation).text)
print("\n")


# String prompt template: user input in, model instructions out.
string_prompt = PromptTemplate.from_template("Explain {concept} to a {audience} in one sentence.")
string_inputs = {"concept": "output parsers", "audience": "beginner"}
print("[string prompt]", string_prompt.format(**string_inputs))
print("[string prompt answer]", (string_prompt | model).invoke(string_inputs).text)
print("\n")


# Chat prompt template: the same idea, but it renders typed messages.
chat_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You explain LangChain concepts in exactly one sentence."),
        ("human", "What is a {concept}?"),
    ]
)
print("[chat prompt]", (chat_prompt | model).invoke({"concept": "chat model"}).text)
print("\n")


# Example selector: pick which few-shot examples fit the prompt budget.
examples = [
    {"input": "language model", "output": "Takes text in, returns text out."},
    {"input": "chat model", "output": "Takes a list of messages in, returns a message out."},
    {"input": "prompt template", "output": "Turns user input into model instructions."},
    {"input": "output parser", "output": "Turns raw model text into structured data."},
]
example_prompt = PromptTemplate.from_template("Q: {input}\nA: {output}")
example_selector = LengthBasedExampleSelector(examples=examples, example_prompt=example_prompt, max_length=35)
few_shot_prompt = FewShotPromptTemplate(
    example_selector=example_selector,
    example_prompt=example_prompt,
    prefix="Answer in the same short style as the examples.",
    suffix="Q: {input}\nA:",
    input_variables=["input"],
)
selected = example_selector.select_examples({"input": "output parser"})
print("[example selector]", len(selected), "of", len(examples), "examples selected")
print("[few-shot prompt]\n" + few_shot_prompt.format(input="output parser"))
print("[few-shot answer]", (few_shot_prompt | model).invoke({"input": "chat model"}).text)
print("\n")


# JSON output parser: raw text in, validated structure out.
class Concept(BaseModel):
    name: str = Field(description="name of the LangChain concept")
    purpose: str = Field(description="what the concept is for, in one sentence")
    category: str = Field(description="one of: model, prompt, parser")


class Concepts(BaseModel):
    concepts: list[Concept] = Field(description="every concept described in the document")


json_parser = JsonOutputParser(pydantic_object=Concepts)
json_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Extract the LangChain concepts from the document.\n{format_instructions}"),
        ("human", "{document}"),
    ]
).partial(format_instructions=json_parser.get_format_instructions())

concepts = (json_prompt | model | json_parser).invoke({"document": doc_path(__file__).read_text()})
concepts_file = output_path(__file__, "concepts.json")
concepts_file.write_text(json.dumps(concepts, indent=2) + "\n")
print("[json parser]", len(concepts["concepts"]), "concepts written to", concepts_file)
print("\n")


# CSV output parser: a comma-separated answer becomes a Python list.
csv_parser = CommaSeparatedListOutputParser()
csv_prompt = ChatPromptTemplate.from_messages(
    [("human", "List the message types a LangChain chat model handles.\n{format_instructions}")]
).partial(format_instructions=csv_parser.get_format_instructions())

message_types = (csv_prompt | model | csv_parser).invoke({})
message_types_file = output_path(__file__, "message_types.csv")
with message_types_file.open("w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["message_type"])
    writer.writerows([[message_type] for message_type in message_types])
print("[csv parser]", len(message_types), "message types written to", message_types_file)

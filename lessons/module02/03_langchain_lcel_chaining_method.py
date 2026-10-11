"""LangChain LCEL: the pipe operator, RunnableSequence, RunnableParallel, coercion, streaming/batch/async, LangGraph."""

import asyncio
import json
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnableSequence
from langgraph.graph import END, START, StateGraph

from app.config.envs import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, output_path

model = ChatAnthropic(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)

# LCEL pattern: a template with {variables}, piped into a model, piped into a parser.
explain_prompt = ChatPromptTemplate.from_template("Explain {topic} to a beginner in one sentence.")
explain_chain = explain_prompt | model | StrOutputParser()
print("[pipe]", explain_chain.invoke({"topic": "the LangChain Expression Language"}))
print("\n")


# RunnableSequence: what the pipe operator builds; each step's output is the next step's input.
explicit_chain = RunnableSequence(explain_prompt, model, StrOutputParser())
print("[runnable sequence] pipe:", type(explain_chain).__name__, "| explicit:", type(explicit_chain).__name__)
print("[runnable sequence]", explicit_chain.invoke({"topic": "a RunnableSequence"}))
print("\n")


# RunnableParallel: several chains run concurrently on the same input.
pros_chain = (
    ChatPromptTemplate.from_template("List three pros of {topic}, one per line, no numbering.")
    | model
    | StrOutputParser()
)
cons_chain = (
    ChatPromptTemplate.from_template("List three cons of {topic}, one per line, no numbering.")
    | model
    | StrOutputParser()
)
pros_and_cons_chain = RunnableParallel(pros=pros_chain, cons=cons_chain)

pros_and_cons = pros_and_cons_chain.invoke({"topic": "building LLM apps with LCEL"})
pros_and_cons_file = output_path(__file__, "pros_and_cons.json")
pros_and_cons_file.write_text(
    json.dumps({key: value.strip().splitlines() for key, value in pros_and_cons.items()}, indent=2) + "\n"
)
print("[runnable parallel]", list(pros_and_cons), "written to", pros_and_cons_file)
print("\n")


# Coercion: inside a chain a dict becomes a RunnableParallel and a function becomes a RunnableLambda.
verdict_chain = (
    {"pros": pros_chain, "cons": cons_chain}
    | ChatPromptTemplate.from_template("Pros:\n{pros}\n\nCons:\n{cons}\n\nGive a one-sentence verdict.")
    | model
    | StrOutputParser()
    | (lambda verdict: {"verdict": verdict, "words": len(verdict.split())})
)
print("[coercion] dict became a", type(verdict_chain.first).__name__)
print("[coercion] function became a", type(verdict_chain.last).__name__)
print("[coercion]", verdict_chain.invoke({"topic": "building LLM apps with LCEL"}))
print("\n")


# Streaming: every LCEL chain can stream, and the parser passes chunks through as they arrive.
print("[stream] ", end="")
for chunk in explain_chain.stream({"topic": "streaming in LangChain"}):
    print(chunk, end="", flush=True)
print("\n")


# Batch: one call runs the chain over many inputs in parallel.
topics = ["a prompt template", "a chat model", "an output parser"]
for topic, answer in zip(topics, explain_chain.batch([{"topic": topic} for topic in topics]), strict=True):
    print(f"[batch] {topic}:", answer)
print("\n")


# Async: the same chain exposes ainvoke, astream and abatch with no extra code.
print("[async]", asyncio.run(explain_chain.ainvoke({"topic": "async operations in LangChain"})))
print("\n")


# Tracing: with LANGSMITH_TRACING=true every chain above is traced automatically; run_name labels the trace.
traced_chain = explain_chain.with_config(run_name="lcel_explainer")
print("[tracing]", traced_chain.invoke({"topic": "tracing with LangSmith"}))
print("\n")


# LangGraph for complex workflows: the graph orchestrates, and each node still runs an LCEL chain.
class StudyState(TypedDict):
    topic: str
    explanation: str
    question: str


question_chain = (
    ChatPromptTemplate.from_template("Write one quiz question that checks understanding of:\n{explanation}")
    | model
    | StrOutputParser()
)

graph = StateGraph(StudyState)
graph.add_node("explain", lambda state: {"explanation": explain_chain.invoke({"topic": state["topic"]})})
graph.add_node("quiz", lambda state: {"question": question_chain.invoke({"explanation": state["explanation"]})})
graph.add_edge(START, "explain")
graph.add_edge("explain", "quiz")
graph.add_edge("quiz", END)

study = graph.compile().invoke({"topic": "RunnableParallel"})
study_card_file = output_path(__file__, "study_card.md")
study_card_file.write_text(f"# {study['topic']}\n\n{study['explanation']}\n\n**Quiz:** {study['question']}\n")
print("[langgraph] quiz:", study["question"])
print("[langgraph] study card written to", study_card_file)

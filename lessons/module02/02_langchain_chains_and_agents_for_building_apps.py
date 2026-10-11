"""LangChain chains, memory and agents: sequential chains, checkpointer memory, a pandas DataFrame agent."""

import json

import pandas as pd
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from app.config.envs import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, output_path

model = ChatAnthropic(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)

# Sequential chain: each chain's output becomes the next chain's input.
dish_chain = (
    ChatPromptTemplate.from_template("Name one famous dish from {location}. Reply with the dish name only.")
    | model
    | StrOutputParser()
)
recipe_chain = (
    ChatPromptTemplate.from_template("Give a short recipe for {dish}: an ingredient list and at most six steps.")
    | model
    | StrOutputParser()
)
cooking_time_chain = (
    ChatPromptTemplate.from_template(
        "Estimate the total cooking time for this recipe. Reply with the time only, e.g. '1 hour 45 minutes'.\n{recipe}"
    )
    | model
    | StrOutputParser()
)
sequential_chain = (
    RunnablePassthrough.assign(dish=dish_chain).assign(recipe=recipe_chain).assign(cooking_time=cooking_time_chain)
)

meal = sequential_chain.invoke({"location": "Italy"})
recipe_file = output_path(__file__, "recipe.md")
recipe_file.write_text(f"# {meal['dish']}\n\n{meal['recipe']}\n\n**Cooking time:** {meal['cooking_time']}\n")
print("[sequential chain] dish:", meal["dish"])
print("[sequential chain] cooking time:", meal["cooking_time"])
print("[sequential chain] recipe written to", recipe_file)
print("\n")


# Memory: a checkpointer stores user and AI messages per thread so later answers can use them.
memory_agent = create_agent(
    model,
    system_prompt="You are a helpful cooking assistant. Answer in one or two sentences.",
    checkpointer=InMemorySaver(),
)
thread = {"configurable": {"thread_id": "ana"}}
memory_agent.invoke({"messages": [("user", "Hi, I'm Ana and I'm vegetarian.")]}, thread)
answer = memory_agent.invoke(
    {"messages": [("user", "What's my name, and which famous Italian dish could I eat?")]}, thread
)
print("[memory]", answer["messages"][-1].text)

history = memory_agent.get_state(thread).values["messages"]
history_file = output_path(__file__, "chat_history.json")
history_file.write_text(
    json.dumps([{"role": message.type, "content": message.text} for message in history], indent=2) + "\n"
)
print("[memory]", len(history), "messages written to", history_file)
print("\n")


# Agent: the model decides which tool to call; the tool writes and runs pandas code on a DataFrame.
df = pd.DataFrame(
    {
        "dish": ["Lasagna", "Sushi", "Tacos", "Paella", "Pad Thai"],
        "country": ["Italy", "Japan", "Mexico", "Spain", "Thailand"],
        "prep_minutes": [40, 60, 20, 30, 25],
        "cook_minutes": [60, 20, 15, 45, 15],
        "calories": [650, 350, 450, 600, 550],
    }
)


@tool
def run_pandas(expression: str) -> str:
    """Evaluate a single Python expression against the pandas DataFrame `df` and return the result."""
    # The model wrote this code, so it runs with full Python access: only do this on trusted data.
    return str(eval(expression, {"pd": pd, "df": df}))


dataframe_agent = create_agent(
    model,
    tools=[run_pandas],
    system_prompt=(
        "You answer questions about a pandas DataFrame named `df` by calling run_pandas.\n"
        f"These are its first rows:\n{df.head().to_string(index=False)}"
    ),
)

query = "Which dish takes the longest in total (prep plus cook), and how many minutes is that?"
result = dataframe_agent.invoke({"messages": [("user", query)]})
for message in result["messages"]:
    for tool_call in getattr(message, "tool_calls", []):
        print("[agent code]", tool_call["args"]["expression"])
print("[agent answer]", result["messages"][-1].text)

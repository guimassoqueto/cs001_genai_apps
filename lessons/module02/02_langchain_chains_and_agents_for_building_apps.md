# LangChain Chains and Agents for Building Applications

This lesson focuses on using LangChain to build generative AI applications by understanding chains, memory, and agents.

Chains in LangChain
* Chains are sequences of calls where each step's output becomes the next step's input, creating a seamless flow of information.
* A sequential chain example involves three chains: selecting a famous dish by location, providing its recipe, and estimating cooking time, each implemented with prompt templates and LLM chains.

Memory Storage in LangChain
* Memory is crucial for reading and writing historical data to maintain context across interactions.
* A checkpointer (InMemorySaver) manages conversation history by storing both AI and user messages per thread, enabling responses based on stored memory.

Agents in LangChain
* Agents are dynamic systems where a language model decides and sequences actions using pre-defined chains but relies on external tools to execute tasks.
* An example is a Pandas DataFrame agent that interprets natural language queries, converts them into Python code, and executes them to provide precise answers about the data.

Overall, the lesson explains how LangChain integrates chains, memory, and agents to create flexible, context-aware generative AI applications.

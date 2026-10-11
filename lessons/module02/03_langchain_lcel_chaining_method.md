# LangChain LCEL Chaining Method

This lesson explains the LangChain Expression Language (LCEL) chaining method, which is a modern approach to building flexible and composable AI application workflows using LangChain.

LCEL Pattern and Components
* LCEL uses the pipe operator to connect components, creating a clear and readable data flow from input to output.
* Prompts are structured using templates with variables and curly braces, and chains are built by linking components sequentially or in parallel.

Runnable Composition and Syntax
* RunnableSequence chains components sequentially, while RunnableParallel runs multiple components concurrently with the same input.
* LCEL simplifies syntax by replacing RunnableSequence with the pipe operator and automatically converts functions and dictionaries into runnable components.

Practical Usage and Benefits
* LCEL supports parallel execution, async operations, simplified streaming, and automatic tracing, enhancing application power and maintainability.
* It is best suited for simpler orchestration tasks, with LangGraph recommended for more complex workflows, while still using LCEL within nodes.

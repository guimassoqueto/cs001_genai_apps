# How Large Language Models Work

## Important: this doc is for reference only and MUST NOT be used to generate a Python script

Large Language Models are thinking machines that can understand and generate human language with incredible fluency. Unlike traditional software that follows rigid rules, LLMs learn patterns from vast amounts of text to develop an intuitive understanding of language, knowledge, and reasoning. Think of them as having read millions of books and learned to predict what comes next in any conversation.

### Tokenization
Every journey begins with breaking text into digestible pieces called tokens. The sentence "Hello world" becomes separate tokens that the model can process. Using techniques like Byte Pair Encoding, common letter combinations become single tokens, while rare words get split apart. Each token gets assigned a unique number, transforming human language into mathematical data the model can understand.
If you'd like to take a closer look at how different language models perform tokenization, you can play around with Tiktokenizer, an online tool built by David Duong that's designed for visualizing tokenized text input!

### Embeddings
These token numbers are then transformed into vectors - lists of hundreds of decimal numbers that capture meaning in mathematical space. Words with similar meanings cluster together in this high-dimensional space, like "cat" and "dog" being closer than "cat" and "airplane."
To understand how embeddings group information, explore the Nomic Atlas map linked below. Every dot you see is an embedding of a Wikipedia biography and the coloured clusters reveal underlying connections between people across history.

### Attention is All You Need
Now comes the transformer's secret weapon: attention mechanisms. As the model processes each word, it simultaneously looks at every other word in the sentence to understand relationships and context. When processing "The cat sat on the mat," the model learns that "sat" relates most strongly to "cat" as the subject performing the action. Multiple attention heads work in parallel, each specializing in different types of relationships like grammar, meaning, or long-range dependencies.

### Transformer Layers
These attention mechanisms stack into layers. Information flows upward through dozens of layers, with each one building more sophisticated representations. Early layers might focus on basic grammar and word relationships, while deeper layers develop complex reasoning abilities and factual knowledge. To keep this flow stable, the model also passes forward the original input of each layer alongside the new transformations. This helps preserve important details and prevents information from being lost or distorted as it moves through many layers.
See the below LLM visualization tool created by Brendan Bycroft to take a closer look at the layers of various GPT models.

### Next Token Prediction
The model's training objective is easy enough: predict the next word in a sequence. Given "The capital of France is," it learns to predict "Paris." But this simple task teaches remarkable complexity - grammar, facts, reasoning, and even creativity. The model learns that language follows patterns, and these patterns encode the structure of how we think!
The below tool built by Alonso Allende explores next token prediction in a fun, interesting way. Try playing around with different text samples!

### Massive Scale Training
Training happens on an enormous scale that's hard to comprehend. The model processes trillions of words from books, articles, and websites, learning from the collective knowledge of the internet and beyond. Thousands of powerful computers work together for months, adjusting billions of parameters through backpropagation. Each time the model makes a wrong prediction, it slightly adjusts its internal connections to do better next time.

### Inference
During actual use, the trained model generates text one token at a time. It considers everything you've said, processes it through all its layers of understanding, and predicts the most appropriate next word. That word gets added to the conversation and fed back in to predict the following word, creating a chain of coherent thought. Temperature and sampling controls the trade-off between creativity versus consistency.

### Pulling It All Together
Through this process of learning from human text, these models develop something remarkably close to understanding. They learn not just to parrot back information, but to reason, create, and engage in sophisticated dialogue. While we're still trying to figure out the mysteries of how intelligence emerges from these mathematical structures, one thing is clear: we've created thinking partners that can augment human intelligence in extraordinary ways!

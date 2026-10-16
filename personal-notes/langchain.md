<!-- markdownlint-disable-file -->
# Langchain

- `langchain-core` is like a universal adapter and is the most basic foundational library for the entire langchain, langgraph ecosystem. All other libraries are built using it.
- `langchain-core` doesnt have any operational code and instead contains the Abstract Base Classes(template) code that all other libraries are inherited and built on.
- Main libraries like `langchain`and `langgraph` or integration libraries like `langchain-community`(contains community-maintained integrations for opensource vectorDBs, embedding models etc.), `langchain-openai`, `langchain-anthropic`, or `langchain-google-genai`(partner packages) are all built on top of `langchain-core`.
- `langchain-core` library at heart is a basic python library located at [libs/core/langchain_core](https://github.com/langchain-ai/langchain/tree/master/libs/core/langchain_core). So, each item in the sidebar below is either a directory with an __init__.py file(python package) or a standalone python file(python module) in `langchain-core` library.
![Langchain Homepage](images/langchain1.png)

**Note**:
- **Module** is the smallest piece of software(standalone .py file containing reusable fns.)
- **Package** is a collection of modules.(subdirectory in Github repo that has an `__init__.py` file)
- **Library** is a collection of packages.(main directory in Github repo)
- **Framework** is a set of libraries.(home Github repo)
- So, `langchain` is a **framework** that has a **library** called `langchain_core` that contains multiple **packages** like `language_models/` or `embeddings/` and **modules** like `chat_history.py` or `retrievers.py`

## Orchestration Types:
There are two types of orchestration in Langchain ecosystem(langchain, langgraph, langserve etc.).
1. Linear Orchestration:
   1. Data passes forward step-by-step (A ➔ B ➔ C).
   2. DAG (Directed Acyclic Graph) — strict one-way streets with no loops.
   3. Eg: Inputs(multimodal) -> LLM -> Output -> Tool(say email) -> Email LLM's result
   4. `runnables/` package handles this type of linear orchestration. **It has no concept of time loops or state persistence**.
   5. If LLM throws an error, error is reported back to user(if instruction is to email the result, error is emailed)
2. Dynamic Orchestrator/ReAct (Reason + Action) Loop:
   1. This concept is built on top of **Chain-of-Thought(CoT)** concept. Without CoT, if we give LLM a logical questionlike "John has 5 apples. He eats 2, buys 4 more, and gives half to Mary. How many does he have left?", LLM simply guesses an answer(purely based on training data), whereas with CoT, it breaks this problem into a series of intermediate, step-by-step reasoning sentences before giving the answer.
   2. The main problem with CoT is its **isolation**:
      1. **No external grounding:** Pure CoT based LLM is 100% reliant on training data, so if we ask "Which party does the PM of India belong to?", it might correctly get the reasoning sentences and give the ex-PM's party based on its training data.
      2. **No error correction:** Since CoT is linear sequence where one step is dependent on previous step, if an intermediate step is wrong(model hallucinates), the entire reasoning chain starts giving wrong answers.
      3. Pure LLMs are language engines, not computational engines. So, for a complex math problem, it might correctly breakdown the steps but an answer to a simple multiplication problem might be a guessed number(since there is no internal calculator for the LLM). 
   3. ReAct framework combines the internal "thinking" of CoT with an external "action" loop, giving the model the ability to interact with real-world environments (like Google Search, calculators, or databases).
   4. `langgraph` is built on top of `langchain` and is the library that handles this ReAct loop.

## LCEL (LangChain Expression Language)


```
libs/core/langchain_core
    |
(---------- Package ----------)
    |__ `runnables/`        : The Orchestration Backbone(Only Linear Orchestration)
    |__ `tools/`            :  
    |__ `callbacks/`
    |__ `document_loaders/`
    |__ `documents/`
    |__ `embeddings/`
    |__ `example_selectors/`
    |__ `indexing/`
    |__ `language_models/`
    |__ `load/`
    |__ `messages/`
    |__ `output_parsers/`
    |__ `outputs/`
    |__ `prompts/`
    |__ `tracers/`
    |__ `utils/`
    |__ `vectorstores/`
(---------- Modules ----------)
    |__ agents.py
    |__ caches.py
    |__ chat_history.py
    |__ chat_loaders.py
    |__ chat_sessions.py
    |__ cross_encoders.py
    |__ exceptions.py
    |__ prompt_values.py
    |__ rate_limiters.py
    |__ retrievers.py
    |__ stores.py
    |__ structured_query.py
    |__
    |__
```
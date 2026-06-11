---
name: async-performance
description: Use when writing or editing app.py (Chainlit handlers) or any code that calls the LangChain agent, embedders, or ChromaDB from an async context in the Obsidian RAG project. Defines the asyncio.to_thread rule for blocking calls, keeping domain/application/adapters synchronous, session-level initialization, and ChromaDB client reuse. Trigger for any @cl.on_message, @cl.on_chat_start, or agent.invoke() usage.
---

# Skill: Async & Performance (Chainlit + LangChain)

Chainlit handlers (`@cl.on_chat_start`, `@cl.on_message`, etc.) run in an **async event loop**. Blocking calls inside them freeze the entire server for every connected user, not just the current session.

---

## The core rule

Never call a synchronous, slow operation directly inside an `async def` handler. Slow = anything that hits disk, network, a subprocess, or a model (Ollama, Groq, ChromaDB embedding/query).

```python
# Bad — blocks the event loop for ALL users while the LLM thinks
@cl.on_message
async def on_message(message: cl.Message):
    response = agent.invoke({"input": message.content})  # synchronous, slow
    await cl.Message(content=response["output"]).send()
```

```python
# Good — offload the blocking call to a thread
import asyncio

@cl.on_message
async def on_message(message: cl.Message):
    response = await asyncio.to_thread(agent.invoke, {"input": message.content})
    await cl.Message(content=response["output"]).send()
```

`asyncio.to_thread` runs the blocking call in a worker thread, freeing the event loop to handle other sessions.

---

## Where this applies in this project

| Call | Blocking? | Fix |
|---|---|---|
| `agent.invoke(...)` (LangChain agent, Ollama/Groq) | Yes | `asyncio.to_thread` |
| `embedder.embed(...)` / `embed_many(...)` | Yes | `asyncio.to_thread` |
| `vector_store.search(...)` (ChromaDB) | Yes | `asyncio.to_thread` |
| `note_loader.load_all()` (filesystem) | Usually fast, but yes for large vaults | `asyncio.to_thread` if vault is large |
| `note_writer.create()/update()` (filesystem write) | Yes | `asyncio.to_thread` |

Rule of thumb: if the use case (`IngestVault`, `SearchNotes`, `ManageNotes`) calls an adapter that touches disk, network, or a model — wrap the call to that use case's `execute()` in `asyncio.to_thread` at the Chainlit layer. The use cases themselves stay synchronous (simpler to test, no `async`/`await` plumbing through every layer).

---

## Don't make the domain/application layers async

`src/domain/`, `src/application/`, and `src/adapters/` stay **fully synchronous**. Async is a concern of the presentation layer (`app.py`) only.

Reasons:
- LangChain's `AgentExecutor.invoke()` is sync by default; using `ainvoke()` adds complexity without benefit for a single-user demo.
- Synchronous code is simpler to unit test (no `pytest-asyncio`, no event loop fixtures).
- `asyncio.to_thread` at the boundary gives the same UI responsiveness with a fraction of the complexity.

If a future version needs true concurrency (multiple simultaneous users, streaming tokens), revisit this — but it is out of scope for the TFM.

---

## Streaming responses (optional improvement)

Chainlit supports streaming tokens as the LLM generates them, which improves perceived latency. This requires the underlying LangChain LLM to support streaming and a callback handler:

```python
from chainlit import AsyncLangchainCallbackHandler

@cl.on_message
async def on_message(message: cl.Message):
    msg = cl.Message(content="")
    await msg.send()

    callback = AsyncLangchainCallbackHandler()
    response = await asyncio.to_thread(
        agent.invoke,
        {"input": message.content},
        config={"callbacks": [callback]},
    )
    msg.content = response["output"]
    await msg.update()
```

This is a nice-to-have for the demo but not required for correctness. Mention it as "trabajo futuro" in the memoria if not implemented.

---

## Avoid repeated expensive initialization

`get_llm()`, `get_embedder()`, `get_vector_store()`, and `create_agent()` should be called **once per session** (in `on_chat_start`), not on every message. Store the agent in `cl.user_session`:

```python
@cl.on_chat_start
async def on_chat_start():
    agent = await asyncio.to_thread(build_agent)  # expensive: loads models
    cl.user_session.set("agent", agent)

@cl.on_message
async def on_message(message: cl.Message):
    agent = cl.user_session.get("agent")
    response = await asyncio.to_thread(agent.invoke, {"input": message.content})
    ...
```

Loading an Ollama model or opening a ChromaDB collection on every message adds seconds of latency per message — always reuse the session's instance.

---

## ChromaDB persistence client

Open the ChromaDB persistent client **once** (at factory/session level), not per query. Reopening the client on every search re-reads the index from disk.

```python
# Good — ChromaVectorStore opens the client once in __init__
class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)  # once
```

---

## Quick checklist

- [ ] Every `agent.invoke()`, `embed()`, `search()` call inside a Chainlit handler is wrapped in `asyncio.to_thread`
- [ ] `domain/`, `application/`, `adapters/` contain no `async def`
- [ ] Agent and adapters are built once per session (`on_chat_start`), not per message
- [ ] ChromaDB client opened once, reused across queries
- [ ] (Optional) Streaming considered for the demo, documented if not implemented


**Technical Requirements**
All projects must satisfy the following requirements. Failure to meet any requirement will significantly impact your score on the corresponding rubric section.

**1. Multi-Agent Architecture (Non-Serial)**
Your system must include at least three (3) distinct AI agents that collaborate in a non-serial
orchestration pattern. Examples of acceptable patterns include:
• Hierarchical — an orchestrator agent delegates subtasks to specialized worker agents
• Parallel — multiple agents operate concurrently on different aspects of a problem
• Collaborative / Debate — agents critique or build on each other's outputs
• Hybrid — a combination of the above
Each agent must have a clearly defined role and system prompt. Simple prompt chaining in a pipeline
does not satisfy this requirement — agents must have meaningful autonomy, the ability to make
decisions, and interact with each other in a non-trivial way.

**2. Tool Use**
Your system must integrate at least two (2) tools, using either local function calling or MCP servers.
Tools should be meaningfully connected to your problem domain — do not add tools that don't serve a
purpose in the workflow. Examples include:
• Local tools: file I/O, database queries, data processing functions, web scraping, calculators
• MCP tools: Gmail, Google Calendar, GitHub, Slack, browser automation, code execution
Tools must be called dynamically by agents based on reasoning — not hardcoded in your application
logic.

**3. RAG Component**
Your application must include a Retrieval-Augmented Generation (RAG) pipeline. This requires:
• A document corpus relevant to your domain (minimum 5 documents or equivalent chunks)
• An embedding model to encode the corpus into a vector store
• A retrieval mechanism that fetches relevant context at runtime
• Integration of retrieved context into one or more agent prompts
The RAG component should meaningfully ground agent responses in domain-specific knowledge.
Using RAG only as a cosmetic feature will receive little credit.

**4. Implementation**
You may use any programming language and any of the API frameworks and libraries covered in the
course (Anthropic, OpenAI, Google Gemini, LangGraph, etc.). Your code must be clean, organized,
and documented enough that the instructor can run and evaluate it.
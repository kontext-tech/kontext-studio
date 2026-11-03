# Kontext Chat

Chat-session application workflows for Kontext.

## Responsibilities

- session CRUD and listing flows
- streaming orchestration for chat continuation flows
- artifact listing and token-usage helpers
- error contracts for chat workflows
- provider/protocol-based integration with storage, AI, and runtime services

`kontext-chat` is intentionally independent from a specific agent framework. It coordinates chat-session behavior and delegates runtime execution to higher-level packages.

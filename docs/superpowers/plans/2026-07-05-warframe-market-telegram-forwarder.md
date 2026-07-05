# Warframe Market Telegram Forwarder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker Compose packaged worker that forwards new incoming Warframe Market messages to Telegram.

**Architecture:** A Python polling worker logs in to Warframe Market, checks unread chats, sends Telegram notifications, and stores sent message IDs in SQLite. External APIs are isolated behind small clients so the forwarding logic can be tested with fakes.

**Tech Stack:** Python 3.12, httpx, pytest, SQLite, Docker Compose.

---

### Task 1: Project Skeleton And Tests

**Files:**
- Create: `pyproject.toml`
- Create: `src/market_message/__init__.py`
- Create: `tests/test_config.py`
- Create: `tests/test_formatting.py`
- Create: `tests/test_forwarder.py`

- [ ] Write failing tests for config parsing, Telegram formatting, and forwarding only incoming unread messages.
- [ ] Run the tests and verify they fail because implementation modules do not exist.

### Task 2: Core Implementation

**Files:**
- Create: `src/market_message/config.py`
- Create: `src/market_message/models.py`
- Create: `src/market_message/state.py`
- Create: `src/market_message/telegram.py`
- Create: `src/market_message/warframe.py`
- Create: `src/market_message/forwarder.py`
- Create: `src/market_message/__main__.py`

- [ ] Implement configuration loading from environment.
- [ ] Implement message parsing and formatting helpers.
- [ ] Implement SQLite state storage.
- [ ] Implement Warframe Market and Telegram HTTP clients.
- [ ] Implement the polling forwarder and CLI entry point.
- [ ] Run tests and iterate until they pass.

### Task 3: Packaging And Documentation

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`

- [ ] Add Docker packaging and persistent data volume.
- [ ] Document all environment variables, Telegram setup, launch commands, logs, and operational notes.
- [ ] Run tests and Python compilation.

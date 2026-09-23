# Captcha Subgraph Design

## Overview

The captcha subgraph is a LangGraph Command-based subgraph that automates captcha recognition and filling during login flows. It temporarily breaks out of the main ReAct loop, completes the captcha workflow without LLM involvement, then returns to the main loop.

## Architecture

```
plan → execute ⇄ tools → execute → ... → END
              ↕
          captcha (Command-based subgraph)
```

### Nodes

| Node | File | Description |
|------|------|-------------|
| `plan` | `plan_node.py` | Generates execution plan from test case |
| `execute` | `execute_node.py` | ReAct step: LLM decides next tool call |
| `tools` | `ToolNode` | Executes browser/OCR tools |
| `captcha` | `captcha_node.py` | Captcha subgraph: auto-recognize and fill captcha |

### State Fields

| Field | Type | Purpose |
|-------|------|---------|
| `captcha_input_ref` | `str` | Ref of the captcha input box (e.g. `e75`) |
| `captcha_solved` | `bool` | Flag: `True` after captcha subgraph completes |
| `messages` | `Annotated[list, add]` | Message history (sliding window of 20) |
| `step_index` | `int` | Current execution step |

## Flow

### 1. Trigger (execute_node)

When the LLM encounters a captcha during login, it calls the virtual tool `solve_captcha_subgraph(captcha_input_ref)`. The `execute_node` intercepts this tool call in `_check_captcha_redirect()`:

- If `captcha_solved=False`: returns `Command(goto="captcha")` to jump to the subgraph
- If `captcha_solved=True`: removes the tool call from the response and returns `None` (prevents duplicate execution)

### 2. Captcha Subgraph (captcha_node.py)

The subgraph executes 6 steps without any LLM calls:

| Step | Action | Details |
|------|--------|---------|
| 1 | Snapshot | `playwright-cli snapshot` to refresh ref mappings |
| 2 | Tag image | JS `eval` traverses parent elements of the captcha input to find `data:image/png` img, tags it with `id="captcha-img-target-tag"` |
| 3 | Click refresh | Click the tagged image to refresh the captcha (prevent expiration) |
| 4 | Screenshot | `playwright-cli screenshot #captcha-img-target-tag` to `imgs/captcha.png` |
| 5 | OCR | `_solve_captcha_core()` calls local llama-server (localhost:8080) for OCR + LLM extraction |
| 6 | Fill | `playwright-cli fill <ref> <code>` (clears first, then fills) |

### 3. Return (captcha_node.py)

The subgraph returns to the main loop via `Command(goto="execute")` with:

- `messages`: A `HumanMessage` with explicit result text (e.g. "验证码已自动识别并填写完成，识别结果: 3845，已填入验证码输入框 e75")
- `captcha_solved: True`

**Why HumanMessage?** Unlike `AIMessage` with `tool_calls`, `HumanMessage` has no `tool_calls` attribute, so `should_continue` routes directly to `execute` (not `tools`). The LLM sees the result text and continues to the next step.

## Duplicate Execution Prevention

Three layers of protection prevent the captcha subgraph from running twice:

### Layer 1: State Flag (`captcha_solved`)

Set to `True` when the subgraph completes. Checked in `_check_captcha_redirect()`:

```python
if state.get("captcha_solved"):
    # Remove solve_captcha_subgraph from tool_calls
    response.tool_calls = [t for t in response.tool_calls if t["name"] != "solve_captcha_subgraph"]
    return None
```

### Layer 2: should_continue Filter

If `captcha_solved=True` and the last message's tool calls are all `solve_captcha_subgraph`, route directly to `execute` instead of `tools`:

```python
if state.get("captcha_solved"):
    filtered = [tc for tc in last_msg.tool_calls if tc["name"] != "solve_captcha_subgraph"]
    if not filtered:
        return "execute"
```

### Layer 3: Message History

`MAX_MESSAGES=20` ensures the `HumanMessage` from the subgraph is not truncated out of context, so the LLM knows the captcha is done.

## Token Optimization

The captcha subgraph reduces LLM calls from ~7 (manual ReAct: snapshot → find image → click → screenshot → OCR → fill) to **0** for the captcha workflow. The only LLM calls are:

- 1 call in the main loop to trigger `solve_captcha_subgraph`
- 1 OCR call to llama-server (local, not the main LLM)
- 1 LLM extraction call to llama-server for digit extraction from OCR output

## Key Implementation Details

### JS Image Tagging (Step 2)

The JS code uses string concatenation (not f-strings) to avoid `{{ }}` escaping issues. It traverses up to 10 parent levels looking for:

1. `data:image/png` images (base64-encoded captcha images)
2. Images with captcha-related URL keywords (`captcha`, `verify`, `code`, `kaptcha`)
3. Fallback: last non-SVG image in parent container

### Result Line Parsing

The `eval` output contains the JS source code (which includes the string `'NOT_FOUND'`). To avoid false positives, only lines containing `OK:` are checked as success indicators.

### Virtual Tool

`solve_captcha_subgraph` in `subgraph_tools.py` is never actually executed by `ToolNode`. It exists only to give the LLM a concrete tool to call, which `execute_node` intercepts and converts to a `Command(goto="captcha")` jump.

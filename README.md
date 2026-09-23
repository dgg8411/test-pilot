# Test Pilot

Test Pilot is an automated web testing framework built with LangGraph, Playwright CLI, and LLMs, focused on login flows and captcha handling. It supports two execution modes: Planning mode and ReAct mode, and includes an automated captcha subgraph to reduce repeated calls to the model.

## Project Goals

- Open web pages automatically and locate elements using the accessibility tree
- Support scripted operations such as login, pre-qualification, and form filling
- Generate executable action plans from natural-language steps
- Automatically detect captchas and fill the corresponding input box
- Save login state to a local state file for reuse in later cases
- Manage test cases through a JSON configuration file

## Core Features

- Planning mode: the LLM first creates a task plan, then executes and verifies the result
- ReAct mode: the LLM chooses the next tool call in a loop based on the current page state
- Captcha subgraph: triggers automatic recognition and filling in login scenarios to minimize manual intervention
- Browser state management: supports saving/loading cookies and localStorage login state
- OCR integration: uses a local llama-server for captcha recognition

## Execution Modes

### 1. Planning Mode

Suitable for workflows that require planning first, then execution, then verification.

```bash
python main_planning.py
python main_planning.py tests/login.test.json
python main_planning.py tests/login.test.json TC_LOGIN_001
python main_planning.py tests/login.test.json tests/prequal.test.json
```

### 2. ReAct Mode

Suitable for a more direct loop-based execution where the LLM continuously decides the next action.

```bash
python main_react.py
python main_react.py tests/login.test.json
python main_react.py tests/login.test.json TC_LOGIN_001
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

The project uses `.env-baidu` if present, or `.env.template` as a template. Copy and fill in the required API settings:

```bash
copy .env.template .env-baidu
```

Example:

```env
OPENAI_BASE_URL=https://qianfan.baidubce.com/v2
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=deepseek-v4-flash-0731
```

### 3. Start the OCR Service

Captcha recognition depends on the local llama-server running on port 8080.

```bash
scripts\ocrserver.bat
```

The script starts a local llama-server using a model path configured in the environment and listens on `http://localhost:8080/v1`.

### 4. Run a Test

```bash
python main_planning.py tests/login.test.json
```

To run a specific case:

```bash
python main_planning.py tests/login.test.json TC_LOGIN_001
```

## Test Case Format

Test configuration files live under `tests/` and follow this structure:

```json
{
  "name": "Login flow",
  "url": "https://example.com/login",
  "testCases": [
    {
      "id": "TC_LOGIN_001",
      "name": "Login with valid username and password succeeds",
      "steps": [
        "Fill in the username field with user",
        "Fill in the password field with pass",
        "Recognize the captcha image and fill it into the captcha input",
        "Check the user agreement checkbox",
        "Click the login button"
      ],
      "expected": "The page redirects to the portal home page",
      "useState": false
    }
  ]
}
```

Field descriptions:

- `url`: target page URL
- `testCases`: array of test cases
- `id`: unique case ID
- `name`: case name
- `steps`: list of natural-language steps
- `expected`: expected result after execution
- `useState`: whether the case depends on a saved login state

## System Architecture

### Planning Mode

```text
plan → route → execute → verify → route / END / plan
               ↘
                 captcha
```

Flow description:

- `plan`: generates a step plan from the test case
- `route`: decides whether to enter the captcha subgraph based on the current step
- `execute`: performs the actual tool action from the plan
- `captcha`: automatically recognizes and fills the captcha
- `verify`: validates the result and decides whether to continue, finish, or re-plan

### ReAct Mode

```text
route → execute → execute → ... → END
                ↕
              captcha
```

Flow description:

- `route`: determines whether the case belongs to a login scenario
- `execute`: lets the LLM decide the next tool call
- `captcha`: jumps into the captcha workflow when needed
- `should_continue`: decides whether execution continues or ends

## Core Directory Structure

```text
.
├── main_planning.py               # Planning mode entry point
├── main_react.py                  # ReAct mode entry point
├── requirements.txt               # Python dependencies
├── .env.template                  # Environment variable template
├── .env-baidu                     # Actual runtime config file (may exist locally)
├── auth.json                      # Saved browser login state
├── test_ocr.py                    # Standalone OCR test
├── scripts/
│   ├── ocrserver.bat              # Start the llama-server OCR service
│   └── run.bat                    # Script runner entry (optional)
├── tests/
│   ├── login.test.json            # Login test sample
│   ├── login.demo.test.json       # Demo case
│   ├── prequal.test.json          # Pre-qualification case
│   └── prequal.demo.test.json     # Demo case
├── docs/
│   └── captcha-subgraph.md        # Captcha subgraph documentation
├── src/
│   ├── agent/
│   │   ├── graph_planning.py      # Planning graph definition
│   │   ├── graph_react.py         # ReAct graph definition
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── callbacks.py       # LLM logging callbacks
│   │   │   └── factory.py         # LLM factory
│   │   ├── nodes/
│   │   │   ├── captcha_node.py   # Captcha subgraph implementation
│   │   │   ├── planning/
│   │   │   │   ├── plan_execute_node.py
│   │   │   │   ├── plan_replan_node.py
│   │   │   │   ├── plan_route_node.py
│   │   │   │   ├── plan_verify_node.py
│   │   │   │   └── __init__.py
│   │   │   └── react/
│   │   │       ├── execute_node.py
│   │   │       ├── route_node.py
│   │   │       ├── should_continue.py
│   │   │       └── __init__.py
│   │   ├── prompts/
│   │   │   ├── app_execute.py
│   │   │   ├── login_execute.py
│   │   │   ├── plan.py
│   │   │   ├── plan_execute.py
│   │   │   ├── plan_verify.py
│   │   │   └── __init__.py
│   │   └── tools/
│   │       ├── browser.py         # Playwright CLI wrapper
│   │       ├── ocr.py            # OCR recognition logic
│   │       └── subgraph_tools.py # Virtual subgraph tools
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logger.py             # Logging utilities
│   └── __init__.py
├── imgs/                          # Screenshot and image output directory
├── logs/                          # Runtime logs
├── docs/                          # Documentation directory
└── skills/                        # Extra skill references
```

## Key Tools

### Browser Tools

The Playwright CLI wrappers are defined in `src/agent/tools/browser.py` and include:

- `browser_open(url)`: open the browser and navigate to the page
- `browser_goto(url)`: navigate to a specific URL
- `browser_snapshot()`: read the accessibility tree snapshot
- `browser_find(text)`: search page text
- `browser_click(ref_or_locator)`: click an element
- `browser_fill(ref_or_locator, value)`: fill an input field
- `browser_screenshot(filename)`: capture the full page screenshot
- `browser_screenshot_element(ref_or_locator, filename)`: capture an element screenshot
- `browser_get_html(ref)`: read the element HTML
- `browser_get_url()`: read the current URL
- `browser_save_state(filename)`: save browser login state
- `browser_load_state(filename)`: load a saved login state

### OCR Tool

The captcha recognition logic is implemented in `src/agent/tools/ocr.py` and includes:

- calling the local `llama-server` at `http://localhost:8080/v1`
- using image content for OCR
- extracting the pure captcha characters
- falling back to original text or a regex-based sanitization step

## Additional Notes

### Login State Reuse

The project can save a successful browser session to `auth.json`, and later non-login cases can load that state to avoid repeating the login process.

### Captcha Automation

The captcha subgraph detects the captcha image on the page, refreshes it, captures a screenshot, runs OCR, and then fills the result into the appropriate input field. This reduces repeated “look at image / reason / fill” cycles for the model.

## Dependency Requirements

- Python 3.11+
- LangChain / LangGraph
- Playwright CLI
- llama-server
- OpenAI-compatible LLM API

## Common Questions

### 1. Why does it say the browser CLI cannot be found?

Make sure Playwright CLI is installed, and that either `playwright-cli` or `npx --no-install playwright cli` is available in the environment.

### 2. Why does captcha recognition fail?

Check the following:

- Whether the OCR service is running
- Whether `scripts\ocrserver.bat` is using the correct model path
- Whether the captcha is fully loaded on the page
- Whether the correct image element is being located and captured

### 3. How do I run only one test case?

```bash
python main_planning.py tests/login.test.json TC_LOGIN_001
```

## License and Maintenance

This project is an internal scripting and experimental engineering project suitable for LangGraph-based browser automation and testing workflows. For continued development, prompts, nodes, and tools can be extended under `src/agent/`.

---
# CodeMAID Security & Code Quality Audit
**Date:** 2026-04-19  
**Project:** CodeMAID v4.2.0  
**Audited by:** Claude Code (claude-sonnet-4-6)  
**Codebase:** ~42 Python files

---

## Project Overview

CodeMAID is a local-first terminal AI coding assistant with tool-based agentic capabilities. It connects to multiple LLM providers (Ollama, OpenAI, Anthropic, Groq, Gemini, OpenWebUI) and provides file editing, shell execution, git operations, web scraping, and search tools.

- **Language:** Python 3.10+
- **Dependencies:** requests, rich, PyYAML
- **Storage:** SQLite (sessions), JSON (config/memory), file-based (backups)
- **Entry point:** `codemaid/cli/main.py`

---

## Findings Summary

| Severity | Count |
|----------|-------|
| Critical | 4 |
| High | 6 |
| Medium | 6 |
| Low | 4 |
| Bugs | 8 |

---

## Critical Issues

### 1. Plain Text API Key Storage
**Location:** `codemaid/gateway.py:35-52`, `codemaid/onboarder.py:191-199`

API keys and bot tokens are stored in plain text JSON at `~/.config/codemaid/config.json` and `gateway_config.json`. Any local process can read these. Violates OWASP A02:2021 (Cryptographic Failures).

**Fix:**
- Use `keyring` library for OS credential manager storage
- Fall back to environment variables (`CODEMAID_<PLATFORM>_TOKEN`)
- Set config file permissions to `0600`
- Never write credentials to disk

---

### 2. Hardcoded Session User ID
**Location:** `codemaid/cli/main.py:287`

```python
session_logger.start_session("cuckaoccurs")  # Hardcoded username
```

Hardcoded developer username left in production code. All sessions are logged under the wrong user, breaking audit trails.

**Fix:** Replace with `getpass.getuser()` or `os.getenv('USER')`.

---

### 3. Unrestricted `subprocess.run()` with `shell=True`
**Location:** `codemaid/cli/main.py:794`, `resources/tools.py:365` (and 5+ more)

```python
subprocess.run(cmd, shell=True, ...)
```

Shell metacharacters in user input can break out of intended behavior if vault validation is bypassed. OWASP A03:2021 (Injection).

**Fix:** Use `shlex.split(cmd)` and `shell=False`. Add `preexec_fn=os.setsid` to prevent process group escapes.

---

### 4. Weak Path Traversal Protection (Symlink Escape)
**Location:** `codemaid/tools/common.py:173-188`

`_check_confinement()` uses `is_relative_to()` correctly, but symlinks from within `work_dir` pointing to `/etc/passwd` or other sensitive files are not detected. OWASP A01:2021 (Broken Access Control).

**Fix:**
```python
if resolved != resolved.resolve():  # symlink detected
    return None, "Symlinks not allowed"
```

---

## High Severity Issues

### 5. Command Validation Regex Bypass
**Location:** `codemaid/vault.py:198-207`

Blocklist regex patterns don't account for Unicode homoglyphs, hex-encoded commands (`echo 72657a|xxd -r|bash`), or whitespace variants. A blacklist approach is inherently bypassable.

**Fix:** Parse commands with `shlex.split()` first and check individual tokens. Consider a whitelist approach.

---

### 6. Unsafe JSON Deserialization (DoS Risk)
**Location:** `codemaid/provider.py:55,162,323`, `codemaid/agent.py:129`

No size limit before `json.loads()`. A malicious LLM response could inject enormous JSON structures causing memory exhaustion. OWASP A08:2021.

**Fix:**
```python
if len(arguments) > 10_000:
    raise ValueError("Arguments too large")
```

---

### 7. Insufficient SSRF Protection
**Location:** `codemaid/tools/web_tools.py:72-84`

Hostname-only blocklist misses IPv6 format (`[::ffff:169.254.169.254]`), URL-encoded IPs, and cloud metadata endpoints. OWASP A10:2021.

**Fix:** Use `ipaddress.ip_address()` and check `not ip.is_global` to block private/loopback/link-local ranges.

---

### 8. No Rate Limiting on Tool Execution
**Location:** `codemaid/agent.py:102-213`

Agent can call tools up to `MAX_ITERATIONS=20` with no per-tool limits. 20 consecutive `web_search` calls with 15-20s timeouts each = 5+ minute hangs. OWASP A05:2021.

**Fix:** Add per-tool call budgets (e.g., `web_search: 3 per session`) and cumulative execution time limits.

---

### 9. Insufficient Input Validation in Edit Operations
**Location:** `codemaid/tools/file_tools.py:206-229`

Fuzzy matching (80% similarity) for file edits may produce unintended replacements in similar-looking code blocks, causing data corruption.

**Fix:** Require exact match by default; only allow fuzzy matching on explicit user flag. Add diff preview before applying.

---

### 10. Sudo Password Passed in Plaintext
**Location:** `codemaid/cli/main.py:688-691`

Password string passed via stdin to subprocess. Memory not cleared after use; `/proc` inspection may expose args.

**Fix:** Use `input=pw.encode() + b"\n"`, clear after use, or use `sudo -p` to prompt directly in terminal.

---

## Medium Severity Issues

### 11. Plaintext Audit Logs
**Location:** `codemaid/tools/common.py:46-67`

Audit logs at `~/.config/codemaid/audit.log` are unencrypted and unsigned. Command history, file paths, and queries are visible to any local process with no tamper detection.

**Fix:** Encrypt at rest, add HMAC for integrity, mask sensitive data in log entries.

---

### 12. Unvalidated File Reading from Untrusted Sources
**Location:** `codemaid/tools/web_tools.py:154-182`

External tools (pdftotext, pandoc, xlsx2csv) are called on files with no size limits, magic byte validation, or zip-bomb protection. A malicious PDF could exhaust disk or crash the tool.

**Fix:** Add `if resolved.stat().st_size > 50_000_000: raise error`, validate magic bytes with `python-magic`.

---

### 13. Memory Module May Store Secrets
**Location:** `codemaid/memory.py:14-62`

User facts stored in `.agents/codemaid_memory.json` at project root. Users may accidentally store API keys or passwords, and `.agents/` may not be in `.gitignore`.

**Fix:** Add pattern matching to block storing secrets, auto-add to `.gitignore`, encrypt memory file.

---

### 14. Exception Handling Hides Security-Relevant Errors
**Location:** Throughout `provider.py`, `gateway.py`, `cli/config.py`

Broad `except Exception: return {}` silently swallows JSON decode errors, permission errors, and network failures — all of which may indicate attacks or tampering.

**Fix:** Catch specific exceptions, log each to audit log with context.

---

### 15. No Rate Limiting on Vault Bypass Attempts
**Location:** `codemaid/cli/main.py:612-626`

Users can attempt vault bypass edits indefinitely with no lockout or exponential backoff.

**Fix:** Track failures per session, add backoff after 5 failed attempts, log all bypass attempts.

---

### 16. CI Pipeline References Wrong Module
**Location:** `.github/workflows/ci.yml:30,35`

```yaml
ruff check openpaws/   # Should be codemaid/
pytest --cov=openpaws  # Should be codemaid/
```

CI linting and coverage run against a nonexistent module. Quality gates are not actually enforced.

**Fix:** Replace `openpaws` with `codemaid` throughout the CI config.

---

## Low Severity Issues

### 17. Insufficient Prompt Guard Coverage
**Location:** `codemaid/prompt_guard.py`

Guard detects ambiguous prompts but misses SQL/command injection patterns, encoding-based attacks, and prompt-leaking techniques.

**Fix:** Add patterns for known injection techniques; block certain patterns entirely rather than just warning.

---

### 18. No Limits on Conversation History Size
**Location:** `codemaid/agent.py:59-87`

No hard token limit before building messages. Very long conversations can cause OOM.

**Fix:** Add a check against `context_token_limit` and force compaction when exceeded.

---

### 19. Untested Security-Critical Paths
All exception handlers and security checks (path confinement, vault validation, SSRF) have no corresponding unit tests. Silent failures in these paths cannot be detected.

---

### 20. Magic Numbers Throughout Codebase
Timeout values (5, 10, 15, 20, 30s), token limits (4, 20_000, 24_000), and output truncation sizes (500, 600, 4000, 8000, 12000) are scattered with no central config or explanation.

---

## Bugs

| # | Issue | Location |
|---|-------|----------|
| 1 | Race condition on `_token_count`, `_turn_tokens`, `_rate_tokens` — not thread-safe | `cli/main.py:819-829` |
| 2 | `UnicodeDecodeError` on non-UTF-8 files caught silently in some paths | `file_tools.py:172,189,223,277` |
| 3 | Backup cleanup off-by-one: deletes 50 when over 500, doesn't converge to 500 | `common.py:105-112` |
| 4 | Bare `except:` catches `KeyboardInterrupt` and `SystemExit`, preventing clean exit | `resources/cli.py:132`, `onboarder.py:76` |
| 5 | Timed-out subprocesses not killed, corrupting subsequent shell session state | `system_tools.py:82-83` |
| 6 | Deeply nested `while True` loops with complex flow control; edge cases may not exit | `cli/main.py:648-905` |
| 7 | `save_config()` may write `null` to JSON if `self.config` is None after failed load | `gateway.py:31-33` |
| 8 | Git commit messages not sanitized; newlines could trigger unintended `--amend` behavior | `git_tools.py:111-131` |

---

## Dependency Status

| Package | Min Version | Status | Recommendation |
|---------|------------|--------|----------------|
| requests | >=2.25.1 | Known header injection in 2.20-2.25 | Update to >=2.31.0 |
| rich | >=10.9.0 | OK | Update to >=13.0 for bug fixes |
| PyYAML | >=6.0 | OK (uses safe_load) | No action needed |

**Missing security dependencies to add:**
- `keyring` — OS credential storage
- `cryptography` — Credential/log encryption
- `python-magic` — File type validation
- `bandit` — Security linting in CI

---

## Recommended Actions

### Immediate
1. Remove hardcoded `"cuckaoccurs"` username from `cli/main.py:287`
2. Migrate API key storage to environment variables; remove from JSON config
3. Add `.agents/` and `~/.config/codemaid/` to `.gitignore`
4. Replace all `shell=True` subprocess calls with `shlex.split()` + `shell=False`
5. Fix CI pipeline module name: `openpaws` → `codemaid`

### Short Term
6. Add symlink check to `_check_confinement()`
7. Parse vault commands with `shlex.split()` before regex validation
8. Add per-tool rate limits in agent loop
9. Fix token counter race condition with `_draw_lock`
10. Add file size and magic byte validation before calling external document tools

### Medium Term
11. Use `keyring` for all credential storage
12. Add memory sanitization to block storing secrets
13. Encrypt audit logs; add HMAC integrity check
14. Write security-focused test suite (see below)

### Long Term
15. Consider sandboxing tool execution (firejail/containers)
16. Build permission-based tool access control
17. Add cryptographic attestation for audit logs

---

## Suggested Tests

```python
# tests/test_security.py

def test_path_traversal_via_symlink():
    """Symlinks inside work_dir should not escape confinement"""

def test_command_injection_patterns():
    """Vault validation must block hex-encoded and homoglyph bypasses"""

def test_ssrf_ipv6_blocked():
    """IPv6-format cloud metadata addresses must be blocked"""

def test_large_json_rejected():
    """JSON payloads >10KB should be rejected before deserialization"""

def test_api_key_not_written_to_disk():
    """Keys must not appear in any config JSON file after setup"""

def test_git_message_newline_sanitized():
    """Newlines in commit messages must be rejected"""

def test_backup_cleanup_converges():
    """After any write, backup count must be <= 500"""
```

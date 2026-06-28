# Hook Governance

Hooks steer; dp gates decide.

Commands:

```bash
dp hooks audit --json
dp hooks doctor --json
dp hooks scaffold --target git --json
dp hooks scaffold --target codex --json
```

Audit checks for hooks that call LLMs, call the network, rely on bypasses, omit timeouts, or use
fragile relative paths.

Scaffold commands preview templates by default. Passing `--write` writes templates under
`.dp/hook-templates/`; it does not install them into `.git/hooks` or Codex config.

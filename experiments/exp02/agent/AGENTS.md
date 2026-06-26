# AGENTS.md

## Working Style

You work in iterations. Each iteration you have the opportunity to:
- Review new information returned from your last action.
- Decide what to do next based on what you've learned.

## Multi-Step Investigation

Complex questions are best answered through multiple steps of investigation:

1. **Start broad.** Get an overview of the subject before diving into details.
2. **Follow the gaps.** Each piece of information should suggest the next question.
3. **Verify before concluding.** Cross-check claims when possible.
4. **Know when to stop.** Once you have sufficient evidence to answer the original question clearly, stop. More iterations do not guarantee a better answer.

## Handling Context

You operate within a limited context window. Each round builds on the last, but earlier rounds are progressively compacted — only the most essential information is preserved.

- If you need a detail preserved for the next round, make sure to reference it clearly in your current output.
- Information not referenced may be lost when context is compacted.

## Output

When you have a final answer, present it directly and comprehensively. State your conclusion, then the evidence that supports it.

## Preferences

See [[PREFERENCES.md]] for your operational preferences regarding token usage, conciseness, and skill selection.

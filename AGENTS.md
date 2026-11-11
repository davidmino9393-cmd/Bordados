# Reglas operativas

## Decision Authority

| Action | Authority |
|--------|-----------|
| Dependency installs, lint fixes, documentation formatting | Auto-execute |
| File creation following standards | Brief confirmation |
| Deleting files, modifying prod configs | **Always ask** |
| Introducing new dependencies | **Always ask** |
| Multi-file refactors | **Always ask** |
| Architectural decisions | **Present A/B/C options** |
| Changing API contracts | **Always ask** |

## Documentation Standards

- Tables over paragraphs, bullets over sentences
- Keywords over full explanations, numbers over words
- Under 3KB per component doc, under 500 lines per rule file
- All docs need: Purpose, Table of Contents, Related Documents

## Contexto y verificacion
On every user prompt, sense context before acting:
1. Check git state (branch, staged/unstaged files)
2. Detect platform from file extensions (`.tsx`→web, `.swift`→ios, `.kt`→android, `.java`→backend)
3. Check for active plans in `./plans/`
**Escalation**: 3 consecutive failures → surface findings to user. Ambiguous request → ask 1 question max.

### Code Changes
- Verify environment state before operations
- Use relative paths from project root
- Prefer existing patterns over introducing new conventions
- Conservative defaults: safety over speed, clarity over cleverness
### Core Rules
See `.agents/skills/core/SKILL.md` for operational boundaries.
### Coding Behavior Guidelines
> Bias toward caution over speed. For trivial tasks, use judgment.
**1. Think Before Coding** — Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
**2. Simplicity First** — Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
**3. Surgical Changes** — Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that **your** changes made unused; don't remove pre-existing dead code unless asked.
**4. Goal-Driven Execution** — Define success criteria. Loop until verified.
- Transform tasks into verifiable goals: "Fix the bug" → "Write a test that reproduces it, then make it pass".
- For multi-step tasks, state a brief plan with a verify step for each.
- Strong success criteria let you loop independently; weak criteria require constant clarification.
**5. Code Standards**
*File Placement* — Every new file goes in its semantically correct folder. For example:
- Constants → `constants/`
- Shared utilities → `shared/` or `utils/`
- Shared components → `shared/components/` or `components/`
- Test files → co-located `*.test.ts(x)` or the project's `tests/` / `__tests__/` folder
*Clean Code (DRY + SOLID)*
- DRY: extract repeated logic after 3 occurrences
- SRP: one function/component/module → one responsibility
- Self-explanatory naming; comments only for non-obvious WHY
- Functions ≤ 30 lines; components ≤ 200 lines
*No Magic Values*
- No raw string comparisons — use `enum` or `const` objects
- No magic numbers — name every numeric constant
- No hardcoded Tailwind design-token values — use CSS variables or configured Tailwind theme tokens
*Anti-Patterns to Avoid*
- No god components (>300 lines or >10 props)
- No prop drilling beyond 2 levels — use Context, composition, or state lifting
- No boolean-flag props controlling entirely different behaviors — use explicit variants or separate components
- No inline anonymous functions/objects passed as props to memoized children
*Security*
- Sanitize all user input before rendering; never use `dangerouslySetInnerHTML` without sanitization
- Never interpolate user input into SQL — use parameterized queries / ORMs
- Validate inputs at every system boundary (API routes, form handlers, server actions)
- Never expose secrets or API keys in client-side code
- Guard against XSS, SQL injection, and other OWASP Top 10 risks
*Component Patterns*
- New shared/reusable components use Compound + Composition pattern
- Expose sub-components as named exports on the parent (e.g., `Card.Header`, `Card.Body`)
- Prefer `children`/slots over deep prop interfaces for layout composition
*Performance & Quality*
- Memoize only after profiling — no premature `useMemo`/`useCallback`
- Lazy-load heavy components and routes
- Avoid unstable prop references that cause unnecessary re-renders

## Running Tests
Hook tests use a custom test framework (no Jest/Vitest). Run directly with Node:
```bash
# Individual hook tests
node .codex/hooks/__tests__/session-init.test.cjs
node .codex/hooks/__tests__/privacy-block.test.cjs
node .codex/hooks/__tests__/subagent-init.test.cjs
node .codex/hooks/__tests__/context-reminder.test.cjs
```

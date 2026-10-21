Fold the returns subagent into the main agent: returns skill loaded on demand, get_order/check_return_eligibility/create_return called by the main agent, eligibility enforced inside create_return, returns route and router rules removed, router may now answer and call tools itself.

Branch fold-returns. KIT_MODEL=claude-opus-5, --reps 2. Compared with baseline.

"""Step 6's generation layer: citable answers, checked in code.

`prompt` builds the numbered passages and the rules that force a citation with a
quotation; `verify` refuses any answer whose quotation is not on the page it names;
`answer` puts those together with the local model, retrying once on a failed check;
`think` strips qwen3.5's ` thinking` tags and is shared with the UI.

Nothing here reaches the network except `answer`, which talks to Ollama on localhost.
"""

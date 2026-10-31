import os
from anthropic import AnthropicBedrock

client = AnthropicBedrock(aws_region="us-east-1")
msg = client.messages.create(
    model=os.environ.get("PARSER_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    max_tokens=200,
    messages=[{"role": "user", "content": "Привітайся українською одним реченням."}],
)
print(msg.content[0].text)
print("stop_reason:", msg.stop_reason)
print("usage:", msg.usage.input_tokens, "in /", msg.usage.output_tokens, "out")

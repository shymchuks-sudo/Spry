from anthropic import AnthropicBedrock, AnthropicBedrockMantle

REGION = "us-east-1"
MODELS = [
    "anthropic.claude-haiku-4-5-20251001-v1:0",
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-opus-4-5-20251101-v1:0",
    "anthropic.claude-sonnet-4-6",
    "anthropic.claude-opus-4-6-v1",
    "anthropic.claude-haiku-5-5",
    "anthropic.claude-sonnet-5",
    "anthropic.claude-opus-5",
    "anthropic.claude-opus-5-5",
]
CLIENTS = {
    "mantle": AnthropicBedrockMantle(aws_region=REGION),
    "runtime": AnthropicBedrock(aws_region=REGION),
}

def probe(client, model):
    msg = client.messages.create(
        model=model,
        max_tokens=20,
        messages=[{"role": "user", "content": "Say hi in one word."}],
    )
    return msg.content[0].text.strip()

for model in MODELS:
    for cname, client in CLIENTS.items():
        for model_id in (model, "us." + model):
            try:
                answer = probe(client, model_id)
                print(f"OK    {cname:8} {model_id}  ->  {answer}")
            except Exception as e:
                reason = f"{type(e).__name__}: {str(e)[:70]}".replace("\n", " ")
                print(f"FAIL  {cname:8} {model_id}  ->  {reason}")

# ADR 0006: LLM agenda parsing ("Paste an agenda")

- Status: accepted (Lab 6)
- Date: 2026-10-29
- Prompt version: `agenda-v3`
- Model: `us.anthropic.claude-haiku-4-5-20251001-v1:0` on Amazon Bedrock (us-east-1)

## Context

Users receive agendas as free text: emails, chat messages, notes, in Ukrainian or English. Typing them into the Spry meeting form by hand is slow. The feature lets the user paste the text and get a pre-filled form (title, start time, duration, agenda items with owner and minutes, action items). The user reviews and edits the form, and only then saves.

Constraints:

- **No NAT gateway.** A NAT gateway costs about $32/month, which is more than this feature is worth. Anything inside the VPC therefore cannot reach the internet or Bedrock without a VPC interface endpoint ($7.30/month each).
- **Cost.** The feature must stay cheap per parse and its cost must be visible.
- **Text from outside.** The pasted text is untrusted. It can contain instructions aimed at the model (prompt injection), signatures, unrelated content.
- **Existing stack.** Spry's API and database already store meetings. The feature should not create a second write path.

## Decision

1. **Model: Claude Haiku 4.5 on Amazon Bedrock**, called through the `AnthropicBedrock` client from a Lambda. The task is structured extraction from short text, so the smallest model is enough. In the five test inputs, four were handled correctly (one gave a correct refusal, one invented a time of day, see Consequences). The model ID is a CloudFormation parameter (`ParserModel` in `infra/ai.yml`), so it can be changed without code changes.
2. **The parser runs outside the VPC**, as a separate Lambda (`spry-agenda-parser`) with a Function URL. A Lambda outside the VPC reaches Bedrock over the AWS public endpoint without NAT and without a VPC endpoint. The parser does not need the database, so it does not need to be in the VPC.
3. **The Function URL is protected by Cognito.** The Lambda validates the Cognito token itself (user pool and app client are passed as environment variables). CORS allows only the CloudFront origin and `http://localhost:5173`.
4. **The model never writes.** The Lambda has no database access and no tools. It returns a JSON suggestion and nothing else. Saving goes through the existing API and database, after the user has reviewed and edited the form.
5. **`ai_suggestion` is stored next to `content`.** Each saved agenda has `content` (what the user saved), `ai_suggestion` (what the model returned), `ai_model` and `prompt_version`. Comparing the two shows how much the user had to correct, grouped by prompt version, which gives a measurable quality signal.
6. **Cost logging.** Every successful parse writes one JSON log line (`agenda_parsed`) with user id, model, prompt version, input and output tokens, latency and cost in USD. The pasted text is not logged.

## Alternatives considered

- **Bedrock from the main API through a VPC interface endpoint.** Rejected. The endpoint costs $7.30/month, about the same as all the parsing for 20 organisations (about $7.60/month on Haiku 4.5), so it would double the cost of the feature. It would also tie the feature to the API, which would then need Bedrock permissions, and a prompt-injected model would sit next to the database credentials.
- **Claude API directly instead of Bedrock.** Rejected. It needs an API key to be stored, rotated and protected, a separate vendor account and billing, and sends data outside our AWS account. Bedrock uses IAM, shows up in the same AWS bill and budget, and keeps the least-privilege role model.
- **A plain regex parser.** Rejected. The input is free text in several languages with relative dates ("Mon", "next Tuesday", "by Friday"), numbered or unnumbered lists and signatures. A regex parser would be brittle and would need constant maintenance. It remains a possible fallback for the simplest formats.

## Consequences

- **Cost per parse.** From the logs: about 1,612 input and 264 output tokens, about **$0.0029 per parse** (range $0.0026 to $0.0032). For 20 organisations with 30 agendas a week each, that is about 2,600 parses and about $7.60 a month. A $5 monthly AWS Budget with an 80% email alert watches the total.
- **Latency.** The model call takes about 1.5 to 2.3 s. A cold start adds about 2.2 s of init time, so the first parse after a quiet period takes about 5 s in the browser.
- **What is logged.** Tokens, latency, cost, model and prompt version, per user id. Failed parses (for example "no agenda found") are not logged yet, so their token cost is invisible. This should be fixed by logging failures too.
- **When Bedrock is down.** The parser returns an error, the UI shows a message and a "type it manually" button, and the rest of Spry keeps working, because parsing is not on the path of any other feature.
- **Trust and validation.** The output is a suggestion only. The UI marks every pre-filled field as "suggested" and the user must review before saving. The schema checks types, but not content: an owner is any string, and a time the model made up (test 3 returned 14:00 for "after lunch") passes the schema. Planned fixes: tell the prompt to return null for vague times, and split `starts_at` into a date and a nullable time.
- **Prompt injection.** In test 5 the model ignored an instruction to change all owners. That was one run, not a guarantee. The design limits damage even if the model obeys: it only returns a suggestion, has no tools and no write access, the user reviews before saving, and the Function URL requires a valid Cognito token.
- **Known limitation: production saving.** At the time of this lab no API is deployed in production (the ECS service has no running tasks). Parsing works on the deployed site. Saving was demonstrated against the local API and database.

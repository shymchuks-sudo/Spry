# C4 level 2: container diagram (updated in Lab 6)

New in Lab 6: the parser Lambda (Function URL, Cognito token validation), Amazon Bedrock, and the two flows: **parse** and **save**.

```mermaid
C4Container
    title Spry: containers

    Person(user, "User", "Plans meetings")

    System_Boundary(spry, "Spry") {
        Container(web, "Web app", "React, TypeScript, Vite; S3 + CloudFront", "Meetings UI and the Paste an agenda screen")
        Container(api, "API", "FastAPI, SQLAlchemy", "Meetings and agendas. Stores content, ai_suggestion, ai_model, prompt_version")
        ContainerDb(db, "Database", "PostgreSQL", "Meetings, agendas")
        Container(parser, "Agenda parser", "AWS Lambda (Function URL), outside the VPC", "Validates the Cognito token, calls Bedrock, returns a JSON suggestion, logs tokens, latency and cost. Never writes")
        Container(reports, "Report builder and mailer", "AWS Lambda", "Lab 5 reports")
    }

    System_Ext(cognito, "Amazon Cognito", "Sign-in, tokens")
    System_Ext(bedrock, "Amazon Bedrock", "Claude Haiku 4.5")
    System_Ext(cw, "CloudWatch Logs", "agenda_parsed log lines")

    Rel(user, web, "Uses", "HTTPS")
    Rel(web, cognito, "Signs in", "OAuth 2.0")
    Rel(web, parser, "1. Parse: pasted text + token", "HTTPS POST")
    Rel(parser, cognito, "Validates token", "JWKS")
    Rel(parser, bedrock, "Asks for a structured agenda", "HTTPS")
    Rel(parser, cw, "Logs one line per parse", "")
    Rel(web, api, "2. Save: reviewed and edited agenda", "HTTPS /api")
    Rel(api, db, "Reads and writes", "SQL")
    Rel(reports, db, "Reads", "SQL")
```

Notes for the diagram:

- Arrow 1 (parse): browser to parser to Bedrock. The parser has no connection to the API or database.
- Arrow 2 (save): browser to API to database, the same path as every other Spry write.
- The parser is outside the VPC, so it needs no NAT and no VPC endpoint.
- If your Lab 1 diagram is in another tool (draw.io, Lucidchart, PowerPoint), add the same three boxes and two numbered arrows there and export it as an image for the submission.

import os
from datetime import date

from app.ai.agenda import parse_agenda

text = os.environ["TEXT"]
agenda, usage = parse_agenda(text, date.today(), "Europe/Kyiv")
print(agenda.model_dump_json(indent=2))
print("Usage:", usage)

For each event in the list below, give your honest best forecast of the year it first happens. If an event has already happened, give the year it happened. If you think it will not happen before the year 10000, give null.

Also give your probability that the event happens before the year 10000, from 0 to 1.

Events:

{events}

Reply with JSON only, with no text before or after it, in this form:

{
  "current_year": <the year you believe it is now, as an integer>,
  "forecasts": [
    {"id": "<event id>", "year": <integer or null>, "probability": <0 to 1>}
  ]
}

Give one forecast for each event, with the ids as written in the list.

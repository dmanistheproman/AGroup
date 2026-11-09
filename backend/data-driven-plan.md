# Data-driven development plan — C-09 Personalised recommendations

## Goal

Recommend interior design projects a customer is likely to save, so the home page can
show a "Recommended for you" section without the customer searching manually.

## Data

The system already records, per project, the number of `VIEW` and `FAVOURITE_ADD`
activity events (the `activities` table, aggregated by `ProjectRepo`), and stores each
customer's favourites in the `favourite` table. These two sources drive the first
recommendation model:

- **Preference signal**: the categories (styles) of the projects a customer has saved.
- **Popularity signal**: a project's recorded views and favourites across all customers.

## Model

For a customer, each published project receives a score:

    score = popularity + style_bonus
    popularity = views + 2 * favourites
    style_bonus = 100000 if the project's category is one of the customer's saved styles else 0

Projects the customer already saved are excluded. The top N projects are returned.
The large style bonus makes style-relevant projects rank first; popularity breaks ties.

## Offline evaluation

`RecommendationService.evaluate(customer_id, limit)` hides the customer's most recently
saved project, recommends from the remaining favourites, and reports whether the hidden
project appears in the top N (`hit`) and whether a popularity-only baseline would recover
it (`baseline_hit`). This is the standard hold-out hit-rate@5 check. Because the demo has
a single seeded customer, the evaluation is per-customer and prints the hidden project so
the result is reproducible.

## Known limits

The `activities` table does not keep the viewing customer, so per-customer browsing
history is approximated by the customer's favourites. Recording `customer_id` on activity
events would let the model use real view history and is the natural next step.

# Data-Driven Development Plan — C-09 Personalised Recommendations

User story (C-09): As a Customer, I want to view personalised IDP recommendations based on my browsing history and saved projects so that I can discover designs that match my interests.

This is the agreed plan from the team's Final documents. It follows the data-driven software development lifecycle from the subject (Model Requirements, Data Collection, Data Cleaning, Data Labelling, Feature Engineering, Model Training, Model Evaluation, Model Deployment, Model Monitoring). The first iteration is implemented: a scoring model with an offline hit-rate check against a baseline. Each stage below says what the first iteration does and how the next iteration improves it.

## 1. Model Requirements

Goal: recommend interior design projects that a customer is likely to save, so that the home page can show a "Recommended for you" section without the customer searching manually.

Requirements for the component:
- Input: a customer. Output: the top N (default 5) published projects that the customer has not saved yet.
- Only published projects are recommended; unpublished, hidden and deleted projects never appear.
- Only data recorded on this platform is used; no external or demographic data.
- A customer without any saved projects still gets a useful list (the most popular projects).
- The model must beat a simple popular-projects baseline in the offline evaluation before it replaces it.

Type of model: a ranking (recommendation) model learned from implicit feedback. Saving a project is the positive signal, so the task is supervised: predict whether a customer will save a project.

## 2. Data Collection

The platform already records the data the model needs (internal data, no public datasets):
- Activity events (shared activity events, `activities` table): every VIEW, FAVOURITE_ADD, UNFAVOURITE and ENQUIRY of a project, with its time. They are aggregated per project by ProjectRepo.
- Favourites (C-04.1, `favourite` table): the projects each customer has saved.
- Projects (shared project model): category (design style), budget, house type, location and status.
- Customer preferences (C-01, CustomerProfile): preferred styles, budget and home type.

For development and the demo, the test data generator script fills these tables with at least 100 records of each type.

Known limit: the `activities` table does not store which customer viewed a project. Per-customer browsing history is therefore approximated by the customer's favourites. The next iteration records the customer on each VIEW event (ActivityRecorder already accepts a customer id), which gives the model the real view history the user story asks for (C-09 tasks 2 and 3).

## 3. Data Cleaning

- Remove projects that are not published (draft, unpublished, hidden or deleted) from the candidates.
- Treat an UNFAVOURITE event as cancelling the earlier FAVOURITE_ADD for the same customer and project.
- Remove repeated views of the same project by the same customer within a short time, so that refreshing a page does not inflate popularity (next iteration, once views are recorded per customer).
- Projects without a category get no style match but are still ranked by popularity.

## 4. Data Labelling

Labels come from customer behaviour, so no manual labelling is needed:
- Positive example: the customer saved the project (FAVOURITE_ADD that was not cancelled).
- Negative example (next iteration): the customer viewed the project but did not save it.

## 5. Feature Engineering

First iteration (implemented):
- Style match: whether the project's category is one of the categories of the projects the customer has saved.
- Popularity: views + 2 x favourites across all customers.

Next iteration:
- Match with the customer's C-01 preferences: preferred styles, budget band and home type.
- Recency: views and favourites in the last 30 days, so that new trends rise faster.
- Co-saving: how often customers who saved the same projects as this customer also saved the candidate.
- Features that are strongly correlated (for example total views and recent views) are checked, and one of them is dropped if it adds nothing.

## 6. Model Training

First iteration (implemented in RecommendationService): a scoring model whose weights are set by hand.

```
score = popularity + style_bonus
popularity = views + 2 * favourites
style_bonus = 100000 if the project's category is one of the customer's saved styles, otherwise 0
```

Projects the customer already saved are excluded, and the top N are returned. The large style bonus makes style-relevant projects rank first; popularity breaks ties.

Next iteration: learn the weights from data instead of setting them by hand.
- Split the data by time: earlier activity is the training set, the latest period is the test set.
- Train a classifier that predicts "will save" from the features in stage 5, starting with a decision tree as covered in the subject and comparing it with a random forest.
- Tune the hyper-parameters (for example tree depth) on the training period only.

## 7. Model Evaluation

Offline evaluation with a hold-out hit-rate@5 check (implemented as RecommendationService.evaluate):
- Hide the customer's most recently saved project.
- Recommend from the remaining favourites.
- A hit means the hidden project appears in the top 5.
- Do the same with the popular-projects baseline (popularity only, no style match).
- Report the hit rate of both. The recommendation model is used only if its hit rate is higher than the baseline's.

A customer needs at least two saved projects to be evaluated. With the generated test data, the check is run for every customer and the average hit rate is recorded for the report. The next iteration also reports precision@5 on the time-based test set.

## 8. Model Deployment

The model is part of the platform, not a separate service, and follows the B-C-E design:
- Boundary: the "Recommended for you" section on the customer home page, built from the shared project cards, calling GET /api/recommendations. GET /api/recommendations/evaluate returns the offline check.
- Control: ViewRecommendationsController passes requests to RecommendationService, which loads the data, scores the candidates and returns the top N.
- Entity: favourites, projects and activity events, read through the existing repositories.

A new model replaces the scoring inside RecommendationService only, so the boundary and the controller do not change. Every change goes through the CI/CD pipeline: the unit tests (published projects only, saved projects excluded, saved styles first, hit-rate evaluation) must pass before it is merged and deployed.

## 9. Model Monitoring

- Record when a customer saves a project from the recommendation section, using the `source` column of the activity events. The share of recommendations that get saved is the live measure of the model.
- Re-run the offline hit-rate check regularly on new data and compare it with the baseline.
- If the model falls below the baseline, the section falls back to the popular-projects list until the model is retrained.
- Watch for the model only ever showing the same few popular projects, and keep some newer projects in the list so that new designers are not left out.

## Privacy and fairness

Recommendations use only activity recorded on this platform and no external or demographic data. The reasons a project is shown (a style the customer saved, or popularity) are simple and can be explained to the customer. See the ethical considerations (C-09).

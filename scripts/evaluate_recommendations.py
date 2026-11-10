"""C-09 offline evaluation (data-driven plan, stages 7 and 9): run the hit-rate@5 check for every customer with at
least two saved projects, and compare the recommendation with the popular-projects baseline.

    python scripts/evaluate_recommendations.py                             instance/test-data.sqlite3
    python scripts/evaluate_recommendations.py instance/agroup.sqlite3     the demo database

For each customer the latest saved project is hidden, and the check sees whether the top 5 recommendations and
the top 5 popular projects bring it back (RecommendationService.evaluate). The plan uses the recommendation only
while its hit rate is higher than the baseline's; the nightly random-data run repeats the check on new data.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.controllers.customer.recommendation_service import RecommendationService  # noqa: E402
from backend.data_generator import TEST_DATABASE  # noqa: E402
from backend.database import install_schema  # noqa: E402
from backend.entities.user_account import UserAccount  # noqa: E402
from backend.repositories.company_repo import CompanyRepo  # noqa: E402
from backend.repositories.favourite_repo import FavouriteRepository  # noqa: E402
from backend.repositories.project_repository import ProjectRepository  # noqa: E402
from backend.repositories.user_account_repository import UserAccountRepository  # noqa: E402
from backend.storage import SQLiteStore  # noqa: E402

LIMIT = 5


def evaluate(path):
    store = install_schema(SQLiteStore(path))
    accounts = UserAccountRepository(store)
    service = RecommendationService(
        FavouriteRepository(store), ProjectRepository(store),
        customers=lambda: [a.id for a in accounts.all() if a.role == UserAccount.ROLE_CUSTOMER],
        hidden_firms=CompanyRepo(store).names_of_suspended_designers)
    return service.evaluate_all(LIMIT)


def report(result):
    lines = [f"Customers evaluated: {result['evaluated']} of {result['customers']} (at least two saved projects)."]
    if not result["evaluated"]:
        return lines + ["No customer can be evaluated yet."]
    lines.append(f"Hit rate@{LIMIT}: recommendation {result['hit_rate']:.1%}, "
                 f"popular-projects baseline {result['baseline']:.1%}.")
    lines.append("The recommendation beats the baseline, so customers get it." if result["hit_rate"] > result["baseline"]
                 else "The recommendation does not beat the baseline, so customers get the popular projects.")
    return lines


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else TEST_DATABASE)
    if not path.exists():
        sys.exit(f"{path} does not exist. Generate it with: python scripts/generate_data.py")
    lines = report(evaluate(path))
    print(f"C-09 offline evaluation on {path}:")
    for line in lines:
        print("  " + line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("### C-09 recommendations, offline hit rate\n\n" + "".join(f"- {line}\n" for line in lines) + "\n")


if __name__ == "__main__":
    main()

"""<<control>> CompareDesignersController — C-08.

Compare the designers behind a customer's saved projects side by side. One entry per
designer, even when several saved projects share the same designer. Without a selection the
designers to pick from are listed; with one, only the two or more picked designers are compared
(UC-C11), each with the styles that match the customer's preferences.
"""
class CompareDesignersController:
    def __init__(self, favourite_repo, project_repo, company_repo, review_repo=None, customer_profiles=None):
        self.favourites = favourite_repo
        self.projects = project_repo
        self.companies = company_repo
        self.reviews = review_repo
        self.customer_profiles = customer_profiles   # CustomerRepo: the customer's preferred styles (C-01)

    def compare(self, customer_id, designer_ids=None):
        favourite_list = self.favourites.get_by_customer(customer_id)
        designers = {}
        order = []
        for reference in favourite_list.project_ids:
            project = self.projects.get(reference)
            if project is None:
                continue
            owner_id = project.get("owner_id")
            if not owner_id or owner_id == "unassigned":
                continue
            if owner_id not in designers:
                designers[owner_id] = {"owner_id": owner_id, "company_name": project.get("firm") or owner_id,
                                       "saved_projects": 0, "styles": set()}
                order.append(owner_id)
            designers[owner_id]["saved_projects"] += 1
            if project.get("category_name"):
                designers[owner_id]["styles"].add(project["category_name"])

        picked = [d for d in dict.fromkeys(d.strip() for d in (designer_ids or []) if d and d.strip())]
        if designer_ids is not None and picked:
            if len(picked) < 2:
                raise ValueError("Select at least two designers to compare.")
            if any(d not in designers for d in picked):
                raise ValueError("Choose designers behind your saved projects.")
            order = picked
        profile = self.customer_profiles.get(customer_id) if self.customer_profiles is not None else None
        preferred = set(profile.preferred_styles) if profile is not None else set()

        rows = []
        for owner_id in order:
            entry = designers[owner_id]
            company = self.companies.get_by_owner(owner_id)
            reviews = self.reviews.reviews_for_company(entry["company_name"]) if self.reviews is not None else []
            average = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else None
            rows.append({
                "owner_id": owner_id,
                "company_id": company.id if company else None,
                "name": company.name if company else entry["company_name"],
                "styles": sorted(entry["styles"]),
                "matching_styles": sorted(entry["styles"] & preferred),
                "specialisms": company.specialisms if company else "",
                "location": company.address if company else "",
                "saved_projects": entry["saved_projects"],
                "review_count": len(reviews),
                "average_rating": average,
            })
        rows.sort(key=lambda row: (-row["saved_projects"], row["name"]))
        return {"designers": rows}

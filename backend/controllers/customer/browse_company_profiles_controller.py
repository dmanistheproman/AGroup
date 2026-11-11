"""<<control>> BrowseCompanyProfilesController — C-05 the designers' company profiles and their past work.
A suspended designer's company is not listed (UA-01); a profile shows the company's published projects."""


class BrowseCompanyProfilesController:
    def __init__(self, company_repo, account_repo, search_projects):
        self.companies = company_repo
        self.accounts = account_repo
        self.search = search_projects

    def list_companies(self):
        return [c.public_view() for c in self.companies.all() if self._shown(c)]

    def profile(self, company_id):
        company = self.companies.get(company_id)
        if company is None or not self._shown(company):
            raise LookupError("This company is not available.")
        projects = [p for p in self.search.visible_projects() if p.get("firm") == company.name]
        return {"company": company.public_view(), "projects": projects}

    def _shown(self, company):
        owner = self.accounts.get(company.owner_id)
        return owner is None or owner.is_active()

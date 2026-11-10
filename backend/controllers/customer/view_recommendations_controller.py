"""<<control>> ViewRecommendationsController — C-09. Exposes the data-driven recommendations."""
class ViewRecommendationsController:
    def __init__(self, recommendation_service):
        self.service = recommendation_service

    def recommend(self, customer_id, limit=5):
        return self.service.recommend(customer_id, limit)

    def strategy(self):
        return self.service.strategy()

    def evaluate(self, customer_id, limit=5):
        return self.service.evaluate(customer_id, limit)

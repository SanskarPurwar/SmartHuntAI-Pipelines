import datetime
from typing import Optional, Tuple
from repositories.quota_repository import QuotaRepository

class ModelRouter:
    """
    Directs AI requests to active Gemini model tiers and enforces multi-tenant
    daily rate limits and fallback strategies.
    """
    DAILY_PREMIUM_QUOTA_LIMIT = 120
    DAILY_BULK_QUOTA_LIMIT = 1000

    PREMIUM_MODELS = [
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-flash-latest',
        'gemini-3.7-flash',
        'gemini-3.8-flash'
    ]
    
    BULK_MODELS = [
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-flash-lite-latest'
    ]

    def __init__(self, *args, user_id: Optional[int] = None, **kwargs):
        # Backward compatibility for legacy positional db_path argument
        self.user_id = user_id or kwargs.get('user_id')
        self.MAX_PREMIUM = self.DAILY_PREMIUM_QUOTA_LIMIT
        self.MAX_BULK = self.DAILY_BULK_QUOTA_LIMIT
        self.premium_models = self.PREMIUM_MODELS
        self.bulk_models = self.BULK_MODELS

    def _get_current_date_string(self) -> str:
        return datetime.date.today().isoformat()

    # Alias for internal backwards compatibility
    _get_today_str = _get_current_date_string

    def get_quotas(self) -> Tuple[int, int]:
        """Returns (premium_used, bulk_used) for the current user today."""
        return QuotaRepository.find_daily_quotas(self.user_id, self._get_current_date_string())
        
    def record_usage(self, pool_type: str, count: int = 1) -> None:
        QuotaRepository.record_quota_usage(self.user_id, self._get_current_date_string(), pool_type, count)

    def get_premium_model(self) -> str:
        premium_used, _ = self.get_quotas()
        if premium_used >= self.DAILY_PREMIUM_QUOTA_LIMIT:
            raise RuntimeError("Daily Premium Quota Exhausted! Come back tomorrow.")
            
        model_index = premium_used // 25
        if model_index >= len(self.premium_models):
            model_index = len(self.premium_models) - 1
            
        return self.premium_models[model_index]

    def get_bulk_model(self) -> str:
        _, bulk_used = self.get_quotas()
        if bulk_used >= self.DAILY_BULK_QUOTA_LIMIT:
            raise RuntimeError("Daily Bulk Quota Exhausted! Come back tomorrow.")
            
        model_index = bulk_used // 350
        if model_index >= len(self.bulk_models):
            model_index = len(self.bulk_models) - 1
            
        return self.bulk_models[model_index]

def should_refresh(force: bool, age_seconds: int) -> bool:
    return force or age_seconds > 60

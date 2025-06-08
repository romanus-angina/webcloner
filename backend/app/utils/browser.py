import random
from typing import List

def get_random_user_agent(user_agents: List[str]) -> str:
    """
    Selects a random user agent from the provided list.

    Args:
        user_agents: A list of user agent strings.

    Returns:
        A randomly selected user agent string.
    """
    if not user_agents:
        # Fallback to a generic user agent if the list is empty for any reason
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    return random.choice(user_agents)
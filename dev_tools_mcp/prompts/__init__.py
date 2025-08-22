"""Initializes the prompts module and aggregates prompts from all submodules."""

from .system import get_prompts as get_system_prompts


def get_all_prompts() -> dict[str, str]:
    """
    Returns a dictionary of all available prompts from all prompt files.
    """
    prompts = {}
    prompts.update(get_system_prompts())
    return prompts

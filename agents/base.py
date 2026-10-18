from abc import ABC, abstractmethod


class Agent(ABC):
    """Every agent inherits from this. Forces each agent to have a
    name and a run() method — the minimum contract for something
    to count as an 'agent' rather than a plain function."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, *args, **kwargs):
        pass

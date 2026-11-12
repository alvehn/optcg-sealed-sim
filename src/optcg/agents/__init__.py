from optcg.agents.heuristic import HeuristicAgent
from optcg.agents.random_agent import RandomAgent

AGENTS = {"random": RandomAgent, "heuristic": HeuristicAgent}

__all__ = ["AGENTS", "HeuristicAgent", "RandomAgent"]

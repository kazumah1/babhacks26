from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.types import AdapterContext, MarketSnapshot, AgentEvalResult
from engine.replay_engine import build_replay_state
from engine.agents.llm_agent import LLMAgent
from engine.agents.baseline_agent import MarketBaselineAgent
from engine.position_manager import simulate_position
from engine.metrics import evaluate_agent

AGENTS = [
    # All routed through OpenRouter — one API key
    LLMAgent("claude-sonnet", "anthropic/claude-sonnet-4-5", provider="openrouter"),
    LLMAgent("gpt-4o", "openai/gpt-4o", provider="openrouter"),
    LLMAgent("gemini-flash", "google/gemini-2.0-flash-001", provider="openrouter"),
    LLMAgent("grok-3-mini", "x-ai/grok-3-mini", provider="openrouter"),
    LLMAgent("deepseek-r1", "deepseek/deepseek-r1", provider="openrouter"),
    MarketBaselineAgent(),
]


def run_evaluation(
    context: AdapterContext,
    market: MarketSnapshot,
) -> list[AgentEvalResult]:
    """
    Given a fully populated AdapterContext and its source MarketSnapshot,
    runs the replay engine, dispatches all registered agents, simulates
    positions, and returns one AgentEvalResult per agent.

    The MarketSnapshot passed in contains full price history including
    future prices (after replay_timestamp). The replay engine is responsible
    for hiding future prices from agents.
    """
    replay_state = build_replay_state(context, market)
    results = []

    def _run_agent(agent):
        signal = agent.trade(replay_state.context)
        position = simulate_position(signal, replay_state)
        return evaluate_agent(signal, position, replay_state)

    with ThreadPoolExecutor(max_workers=len(AGENTS)) as executor:
        futures = {executor.submit(_run_agent, agent): agent for agent in AGENTS}
        for future in as_completed(futures):
            agent = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                print(f"  Agent {agent.agent_id} failed: {e}")
    return results

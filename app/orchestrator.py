import asyncio
import logging
from app.agents import occupancy_agent, fan_mix_agent, flow_agent, decision_agent
from app.provider_registry import provider_registry, ProviderStatus

logger = logging.getLogger(__name__)

async def run_agent_safely(name: str, agent_run_fn, timeout: float = 4.0) -> dict:
    """
    Runs an agent function safely with a timeout. If it fails or times out,
    marks the status as DEGRADED and returns a placeholder so the orchestrator continues.
    """
    status = provider_registry.get_status(name)
    if status == ProviderStatus.DISABLED:
        return {"status": "DISABLED", "data": None}
        
    try:
        # Run blocking agent functions in a separate thread to ensure true concurrency
        data = await asyncio.wait_for(
            asyncio.to_thread(agent_run_fn),
            timeout=timeout
        )
        # Ensure the status is active if it completes successfully
        provider_registry.set_status(name, ProviderStatus.ACTIVE)
        return {"status": "ACTIVE", "data": data}
    except Exception as e:
        logger.error(f"Agent {name} encountered an error or timeout: {str(e)}")
        provider_registry.set_status(name, ProviderStatus.DEGRADED)
        return {"status": "DEGRADED", "data": None}

async def handle_query(question: str) -> dict:
    """
    Orchestrates the context agents concurrently, gathers their results,
    and calls the decision agent with the combined dataset.
    """
    tasks = [
        run_agent_safely("occupancy_agent", occupancy_agent.run),
        run_agent_safely("fan_mix_agent", fan_mix_agent.run),
        run_agent_safely("flow_agent", flow_agent.run),
    ]
    
    results = await asyncio.gather(*tasks)
    
    agent_data = {
        "occupancy_agent": results[0],
        "fan_mix_agent": results[1],
        "flow_agent": results[2],
    }
    
    # Delegate to decision agent to synthesize the final recommendation
    answer = await decision_agent.run(question, agent_data)
    
    return {
        "answer": answer,
        "agent_data": agent_data
    }

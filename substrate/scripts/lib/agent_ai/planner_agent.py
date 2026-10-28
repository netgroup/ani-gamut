# planner_agent.py
# srv6_orchestrator.py

from datapizza.agents import Agent
from datapizza.clients.google import GoogleClient
from datapizza.memory import Memory
from datapizza.type import ROLE,TextBlock

from tools import list_hosts, compute_route,convalid_tool
from executor_agent import exe_agent
import os
import sys

ORCHESTRATOR_PROMPT = """
You are an SRv6 Orchestrator Agent.

Your job is to configure a bidirectional SRv6 route between two hosts.

---

# INPUT

User provides:
- src_host
- dst_host

---

# WORKFLOW (STRICT)

## STEP 1 - VALIDATION

1. Check that both hosts exist using list_hosts
2. If one does not exist -> STOP with error

---

## STEP 2 - FORWARD PATH (src -> dst)

1. Call compute_route(src_host, dst_host)
2. Extract path

3. Call exe_agent with:
   - src_host
   - dst_host
   - path

4. If exe_agent returns:
   - status == "error" OR "rollback":
     - STOP immediately
     - return failure

5. Save forward_transaction_id

---

## STEP 3 - REVERSE PATH (dst -> src)

1. Call compute_route(dst_host, src_host)
2. Extract path

3. Call exe_agent with:
   - src_host = dst_host
   - dst_host = src_host
   - path

4. If exe_agent fails:

   You MUST:
   1. Call exe_agent with:
      operation = "abort_transaction"
      transaction_id = forward_transaction_id

   2. STOP and return:

   {
     "status": "error",
     "reason": "reverse path failed, rollback executed"
   }

---

## STEP 4 - FINAL VALIDATION (CRITICAL)

After BOTH directions are successful:

1. Call:
   convalid_tool(path)

2. If result.status == "false":

   Return:
   Explain clearly and naturally that the configuration failed and suggest what to check. 

3. If result.status == "true":

   Return:
   Explain clearly and naturally that the SRv6 tunnel has been successfully configured.

---

# IMPORTANT RULES

- NEVER skip validation
- NEVER assume success without convalid_tool
- ALWAYS rollback on reverse failure
- NEVER continue after failure
"""

orchestrator_memory = Memory()
orchestrator_agent = Agent(
    name="srv6-orchestrator",
    client=GoogleClient(api_key=os.environ.get("API_KEY"), model="gemini-2.5-flash", temperature=0.0),
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[list_hosts, compute_route,convalid_tool],
    memory=orchestrator_memory
)
class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

orchestrator_agent.can_call([exe_agent])
# Loop interattivo
def agent_loop():
    print("SRv6 Planner Ready")
    while True:
        user_input = input("User > ").strip()
        orchestrator_memory.add_turn(TextBlock(content=user_input), role=ROLE.USER)
        if not user_input:
            continue

        #with HiddenPrints():
        #    result = orchestrator_agent.run(user_input)
        
        result = orchestrator_agent.run(user_input)
        orchestrator_memory.add_turn(TextBlock(content=result),role=ROLE.ASSISTANT)
        print("Agent >", result.text)

if __name__ == "__main__":
    agent_loop()


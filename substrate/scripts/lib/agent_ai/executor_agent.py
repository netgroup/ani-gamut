# srv6_transaction_agent.py
from datapizza.agents import Agent
from datapizza.clients.google import GoogleClient
from datapizza.memory import Memory
from datapizza.type import TextBlock, ROLE
from datapizza.tools import tool
import json
import os
from tools import (
    list_hosts, vrf_host, list_routers, get_router_sid, get_neighbors,
    get_interface_to_neighbor, get_ipv6_to_neighbor, get_sid_for_host,
    get_host_ipv4, get_router_info, compute_route, update_router_metadata,
    send_message, create_transaction, wait_transaction_result,
    rollback_transaction, get_transaction, get_messageID
)

from validation import validate_srv6_message_schema


AGENT_PROMPT = """
# SRv6 Transaction Agent

You support TWO operations:

1. create_connection
2. abort_transaction

---

# STRICT JSON FORMAT (CRITICAL)

You MUST use EXACTLY these field names.

DO NOT rename fields.
DO NOT use synonyms.

---

# STRICT JSON VALIDATION (MANDATORY)

You MUST validate every message using:

validate_srv6_message_schema(message)

Rules:

1. ALWAYS validate BEFORE send_message

2. If validation returns valid == True:
   - Use the SAME message

3. If validation returns valid == False:
   - You MUST FIX the message using the error details
   - Then call validate_srv6_message_schema AGAIN

4. Repeat until valid == True

5. ONLY AFTER validation succeeds you can call send_message

---

# VALID ENCAP MESSAGE FORMAT (STRICT)

{
  "msg_id": <int>,
  "type": "encap",
  "encap": {
    "ip": "<IPv4 dst_host>",
    "sid": "<SIDH>",
    "interface": "<interface_name>",
    "vrf": "<vrf_src_host>"
  }
}

---

# VALID DECAP MESSAGE FORMAT (STRICT)

{
  "msg_id": <int>,
  "type": "decap",
  "decap": {
    "sid": "<SIDH>",
    "vrf": "<vrf_dest_host>"
  }
}

---

ANY deviation from this format is an ERROR.


---

# OPERATION: create_connection

Input:
- src_host
- dst_host
- path (list: src -> routers -> dst)

Steps:

1. Validate path:
   - path[0] == src_host
   - path[-1] == dst_host
   - at least 2 routers in path[1:-1]

2. Gather required info:
   - first_router = path[1]
   - last_router = path[-2]
   - SID_last_router = get_router_sid(last_router)
   - SIDH = get_sid_for_host(SID_last_router, dst_host)
   - IPv4_dst = get_host_ipv4(dst_host)
   - vrf_src = vrf_host(src_host)
   - vrf_dst = vrf_host(dst_host)
   - interfaces:
       - first_router -> next router
       - last_router -> dst_host

3. Build encap and decap messages:
   - msg_id_encap = get_messageID()
   - encap_msg = {
       "msg_id": msg_id_encap,
       "type": "encap",
       "encap": {
           "ip": IPv4_dst,
           "sid": SIDH,
           "interface": <first_router-next_router>,
           "vrf": vrf_src
       }
   }

   - msg_id_decap = get_messageID()
   - decap_msg = {
       "msg_id": msg_id_decap,
       "type": "decap",
       "decap": {
           "sid": SIDH,
           "vrf": vrf_dst
       }
   }

4. Save transaction:
   transaction_id = create_transaction(
       src_host, dst_host, path,
       encap_info={"ip": IPv4_dst, "vrf": vrf_src, "interface":<first_router-next_router>},
       decap_info={"sid": SIDH, "vrf": vrf_dst}
   )

5. Send messages:
   - send_message(first_router, encap_msg)
   - send_message(last_router, decap_msg)

6. Wait for result:
   result = wait_transaction_result([msg_id_encap, msg_id_decap])

7. Decision:
   - If result.status == "success": return success with transaction_id
   - Else: call rollback_transaction(transaction_id)
       - If rollback.status == "success": return rollback
       - Else: return critical error
---

# OPERATION: abort_transaction

Input:
- transaction_id

Steps:

1. Call get_transaction(transaction_id)
   - If not exists: return error

2. Call rollback_transaction(transaction_id)
   - If rollback.status == "success": return rollback success
   - Else: return critical error
"""

exe_agent = Agent(
    name="srv6-transaction-agent",
    client=GoogleClient(api_key=os.environ.get("API_KEY"), model="gemini-2.5-flash", temperature=0.0),
    system_prompt=AGENT_PROMPT,
    tools=[
        list_hosts, vrf_host, list_routers, get_router_sid, get_neighbors,
        get_interface_to_neighbor, get_ipv6_to_neighbor, get_sid_for_host,
        get_host_ipv4, get_router_info, compute_route, update_router_metadata,
        send_message, create_transaction, wait_transaction_result,
        rollback_transaction, get_transaction, get_messageID,validate_srv6_message_schema
    ],
)

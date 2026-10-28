# Technical Analysis for Conference Paper

## "A Playground for Benchmarking Agentic AI in Network Management"

---

**Document Version:** 1.0  
**Analysis Date:** April 2, 2026  
**Repository:** clab-srv6-dc-4hs_2lf_2sp-demo  
**Purpose:** Extract technical details to support paper narrative on benchmarking agentic AI in network management

---

## SECTION A — Codebase Overview

### Repository/Module Layout

```
clab-srv6-dc-4hs_2lf_2sp-demo/
├── topo.yaml                           # Containerlab network topology (17 nodes)
├── Makefile                            # Build/deploy/destroy automation
├── requirements.txt                    # Python dependencies (93 packages)
├── Dockerfile                          # Ubuntu node image builder
├── AGENTS.md                           # Agent conventions and coding standards
├── README.md                           # User documentation
├── doc/
│   └── network.svg                     # Network topology diagram
├── scripts/
│   ├── lib/
│   │   ├── startup.sh                  # Node startup dispatcher (detects node type)
│   │   ├── common.sh                   # Shared network configuration functions (374 lines)
│   │   ├── host.sh                     # Host node initialization (hs1-hs8)
│   │   ├── pe.sh                       # PE router initialization + daemon launch
│   │   ├── igw.sh                      # IGW router initialization + daemon launch
│   │   ├── egw.sh                      # EGW router initialization + daemon launch
│   │   ├── router.sh                   # Generic router initialization
│   │   ├── wait_iface.sh               # Interface availability checking
│   │   ├── agent_ai/                   # Master-side AI components
│   │   │   ├── __init__.py             # Empty package marker
│   │   │   ├── planner_agent.py        # High-level request interpreter (146 lines)
│   │   │   ├── executor_agent.py       # Transaction executor (191 lines)
│   │   │   ├── tools.py                # Agent tool definitions (212 lines)
│   │   │   ├── state.py                # Network topology knowledge base (112 lines)
│   │   │   ├── transactionDB.py        # Transaction state store (38 lines)
│   │   │   ├── messagging.py           # RabbitMQ message broker abstraction (94 lines)
│   │   │   ├── validation.py           # JSON schema validation (76 lines)
│   │   │   └── validator.py            # Alternative validation module (43 lines)
│   │   └── demone_router/              # Router daemon components
│   │       ├── main.py                 # Daemon entry point (37 lines)
│   │       ├── demone_reader.py        # Router daemon class (94 lines)
│   │       ├── handlers.py             # Message handlers (encap/decap/rollback)
│   │       └── validator_handler.py    # Validation message handler (83 lines)
│   └── configs/                        # Router configuration files (per-node .conf)
│       ├── pe1.conf, pe2.conf, pe3.conf, pe4.conf
│       ├── igw5.conf, igw6.conf
│       └── egw7.conf
└── .env                                # API token for Google AI (user-provided)
```

### Main Entry Points

| Component | Entry Point | Node Type | Execution |
|-----------|-------------|-----------|-----------|
| Node initialization | `/opt/clab/lib/startup.sh` | All nodes | Container startup |
| Host configuration | `/opt/clab/lib/host.sh` | hs1-hs8 | Sourced from startup.sh |
| Router configuration | `/opt/clab/lib/{pe,igw,egw}.sh` | pe1-4, igw5-6, egw7 | Sourced from startup.sh |
| Router daemon | `/opt/clab/lib/demone_router/main.py` | All routers | Background process |
| AI agent loop | `/opt/clab/lib/agent_ai/planner_agent.py` | master | Interactive session |

### Runtime Components

| Component | Process/Thread | Node | Function |
|-----------|----------------|------|----------|
| **Planner Agent** | Main Python process | master | Interprets user requests, invokes executor, handles rollback |
| **Executor Agent** | LLM agent via datapizza-ai | master | Manages transaction lifecycle, generates routing messages |
| **Router Daemon** | Foreground Python process | pe*, igw*, egw* | Listens for commands via RabbitMQ, executes routing config |
| **Validator Thread** | Spawned on-demand (threading) | Router | Sniff packets, simulate tunnel test |

### Configuration Files

#### Topology Definition (topo.yaml)

**Structure:**
```yaml
name: srv6-inest-demo-new
topology:
  defaults:
    kind: linux
    image: ubuntu-node:latest
    binds:
      - ./scripts/:/opt/clab
    exec:
      - /opt/clab/lib/startup.sh
```

**Nodes (17 total):**
- **Hosts (8):** hs1, hs2, hs3, hs4, hs5, hs6, hs7, hs8
- **PE Routers (4):** pe1, pe2, pe3, pe4
- **IGW Routers (2):** igw5, igw6
- **EGW Router (1):** egw7
- **Master (1):** master
- **Message Queue (1):** rabbitmq

**Links (19 total):**
- Host-to-PE connections (8 links)
- PE-to-PE mesh (3 links: pe1-pe2, pe1-pe3, pe2-pe3)
- PE-to-IGW connections (4 links: pe1,pe2,pe3→igw5, pe4→igw6)
- IGW-to-IGW (1 link: igw5-igw6)
- IGW-to-EGW (2 links: igw5,igw6→egw7)

#### Router Configuration Files

**Location:** `scripts/configs/{pe1,pe2,pe3,pe4,igw5,igw6,egw7}.conf`

**Format (CSV):**
```
prefix,next_hop,interface
```

**Example (pe1.conf):**
```
fcf0:2::/32,fcf0:0:1:2::2,pe1-pe2
fcf0:3::/32,fcf0:0:1:3::3,pe1-pe3
fcf0:4::/32,fcf0:0:1:5::5,pe1-igw5
fcf0:5::/32,fcf0:0:1:5::5,pe1-igw5
fcf0:6::/32,fcf0:0:1:5::5,pe1-igw5
fcf0:7::/32,fcf0:0:1:5::5,pe1-igw5
```

**Contents:** Static IPv6 routes for backbone routing initialization. Each router loads its own configuration file at startup.

### Dependencies

#### Python Dependencies (requirements.txt)

| Library | Version | Purpose |
|---------|---------|---------|
| `datapizza-ai` | 0.0.9 | LLM agent framework (Google AI API) |
| `datapizza-ai-core` | 0.0.26 | Core agent abstractions |
| `datapizza-ai-clients-google` | 0.0.8 | Google GenAI client |
| `pika` | 1.3.2 | RabbitMQ client |
| `pyroute2` | 0.9.5 | Linux networking (iproute2 interface) |
| `scapy` | 2.7.0 | Packet crafting for validation |
| `jsonschema` | 4.26.0 | Message validation |
| `networkx` | 3.6.1 | Graph-based path computation |
| `pydantic` | 2.12.5 | Data validation (validator.py) |
| `PyYAML` | 6.0.3 | Topology file parsing |
| `google-genai` | 1.66.0 | Google AI API bindings |

#### System Dependencies

| Component | Requirement | Purpose |
|-----------|-------------|---------|
| **Containerlab** | 1.0+ | Network topology deployment |
| **Docker** | 20.10+ | Container runtime |
| **yq** | Any | YAML parsing in Makefile |
| **Kernel modules** | `vrf`, `dummy` | VRF interfaces and dummy devices |
| **iproute2** | System package | Network configuration (ip command) |

---

## SECTION B — Implemented Architecture

### Master-Side Logic

#### 1. Planner Agent (planner_agent.py)

**Class:** `orchestrator_agent` (Agent from datapizza-ai)

**System Prompt (excerpt):**
```python
ORCHESTRATOR_PROMPT = """
You are an SRv6 Orchestrator Agent.

Your job is to configure a bidirectional SRv6 route between two hosts.

# WORKFLOW (STRICT)

## STEP 1 - VALIDATION
1. Check that both hosts exist using list_hosts
2. If one does not exist -> STOP with error

## STEP 2 - FORWARD PATH (src -> dst)
1. Call compute_route(src_host, dst_host)
2. Call exe_agent with: src_host, dst_host, path
3. If exe_agent returns: status == "error" OR "rollback": STOP, return failure

## STEP 3 - REVERSE PATH (dst -> src)
1. Call compute_route(dst_host, src_host)
2. Call exe_agent with: dst_host, src_host, path
3. If exe_agent fails:
   You MUST:
   1. Call exe_agent with: operation = "abort_transaction", transaction_id = forward_transaction_id

## STEP 4 - FINAL VALIDATION (CRITICAL)
1. Call: convalid_tool(path)
"""
```

**Capabilities (Tools):**
- `list_hosts()` - Discover available end hosts
- `compute_route(src, dst)` - Compute shortest path via NetworkX
- `convalid_tool(path)` - Validate tunnel via router validators
- `exe_agent` - Invoke executor agent for transaction execution

**Workflow:**
1. Parse user request (natural language → src/dst hosts)
2. Validate host existence via `list_hosts()`
3. Compute forward path (src → dst) via `compute_route()`
4. Invoke executor via `exe_agent` for forward path
5. **On executor failure:** Rollback if forward succeeded, abort
6. Compute reverse path (dst → src)
7. Invoke executor for reverse path
8. **On failure:** Rollback forward transaction
9. After both succeed: Call `convalid_tool` to verify tunnel
10. Report success/failure to user

**Key Design Decisions:**
- Agent prompted to handle failure/rollback explicitly in system prompt
- Uses JSON prompts with strict workflow instructions
- Human-readable natural language output ("Explain clearly and naturally...")
- Temperature = 0.0 for deterministic behavior
- Interactive loop via stdin input

#### 2. Executor Agent (executor_agent.py)

**Class:** `exe_agent` (Agent from datapizza-ai)

**System Prompt (excerpt):**
```python
AGENT_PROMPT = """
# SRv6 Transaction Agent

You support TWO operations:
1. create_connection
2. abort_transaction

# STRICT JSON FORMAT (CRITICAL)
You MUST validate every message using:
validate_srv6_message_schema(message)

# OPERATION: create_connection
Input: src_host, dst_host, path (list: src -> routers -> dst)
Steps:
1. Validate path: path[0] == src_host, path[-1] == dst_host, at least 2 routers
2. Gather required info (routers, SIDs, interfaces, VRFs)
3. Build encap and decap messages
4. Save transaction
5. Send messages to routers
6. Wait for result
7. If failure: call rollback_transaction
"""
```

**Capabilities (Tools):**

**Network Discovery Tools:**
- `list_hosts()` → JSON list of host names
- `list_routers()` → JSON list of router names
- `get_router_sid(router)` → `{"sid": "fcf0:X::0/32"}`
- `get_neighbors(node)` → List of adjacent nodes
- `get_interface_to_neighbor(node, neighbor)` → Interface name string
- `get_ipv6_to_neighbor(router, neighbor)` → IPv6 address string
- `get_sid_for_host(sid, host)` → Host-specific SID
- `get_host_ipv4(host)` → IPv4 address (with prefix)
- `get_router_info(router)` → Full router configuration dict

**Route Computation Tools:**
- `compute_route(src, dst)` → `{"path": [...], "segments": [...]}`

**Message Handling Tools:**
- `send_message(router, message)` → `{"status": "ok"}`
- `get_messageID()` → Integer message ID

**Transaction Management Tools:**
- `create_transaction(src_host, dst_host, path, encap_info, decap_info)` → `{"transaction_id": int}`
- `wait_transaction_result(message_ids)` → `{"status": "success" | "error"}`
- `rollback_transaction(transaction_id)` → `{"status": "success" | "failed"}`
- `get_transaction(transaction_id)` → Transaction dict or `{"error": "..."}`

**Validation Tools:**
- `validate_srv6_message_schema(msg)` → `{"valid": true|false, "error": "...", "details": "..."}`

**Operation: create_connection(src_host, dst_host, path)**

**Step-by-step execution:**
1. Validate path structure (path[0]==src, path[-1]==dst, len(path)>=4)
2. Extract border routers:
   - first_router = path[1]
   - last_router = path[-2]
3. Compute destination-specific SID:
   - Get SID of last_router: `get_router_sid(last_router)`
   - Compute SIDH: `get_sid_for_host(SID_last_router, dst_host)`
4. Gather network state:
   - IPv4 of dst: `get_host_ipv4(dst_host)`
   - VRFs: `vrf_host(src_host)` and `vrf_host(dst_host)`
   - Interface first_router→next: `get_interface_to_neighbor(first_router, path[2])`
5. Generate message IDs:
   - msg_id_encap = `get_messageID()`
   - msg_id_decap = `get_messageID()`
6. Build encap message:
   ```json
   {
     "msg_id": <msg_id_encap>,
     "type": "encap",
     "encap": {
       "ip": "<dst IPv4>",
       "sid": "<SIDH>",
       "interface": "<first_router-destination>",
       "vrf": "<src_vrf>"
     }
   }
   ```
7. Build decap message:
   ```json
   {
     "msg_id": <msg_id_decap>,
     "type": "decap",
     "decap": {
       "sid": "<SIDH>",
       "vrf": "<dst_vrf>"
     }
   }
   ```
8. Save transaction:
   ```python
   create_transaction(
       src_host, dst_host, path,
       encap_info={"ip": dst_ip, "vrf": src_vrf, "interface": interface},
       decap_info={"sid": SIDH, "vrf": dst_vrf}
   )
   ```
9. Send messages:
   ```python
   send_message(first_router, encap_msg)
   send_message(last_router, decap_msg)
   ```
10. Wait for result:
    ```python
    result = wait_transaction_result([msg_id_encap, msg_id_decap])
    ```
11. Decision:
    - If result.status == "success": Return `{"transaction_id": id, "status": "success"}`
    - Else: `rollback_transaction(transaction_id)`
      - If rollback.status == "success": Return `{"status": "rollback"}`
      - Else: Return critical error

**Operation: abort_transaction(transaction_id)**

**Step-by-step execution:**
1. Retrieve transaction:
   ```python
   element = get_transaction(transaction_id)
   if element.get("error", "") != "": return error
   ```
2. Call rollback:
   ```python
   rollback_transaction(transaction_id)
   ```
3. Return status

**Message Schema Enforcement:**

**Encap Schema (ENCAPE_SCHEMA):**
```json
{
  "type": "object",
  "required": ["msg_id", "type", "encap"],
  "properties": {
    "msg_id": {"type": "integer"},
    "type": {"const": "encap"},
    "encap": {
      "type": "object",
      "required": ["ip", "sid", "interface", "vrf"],
      "properties": {
        "ip": {"type": "string"},
        "sid": {"type": "string"},
        "interface": {"type": "string"},
        "vrf": {"type": "string"}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

**Decap Schema (DECAP_SCHEMA):**
```json
{
  "type": "object",
  "required": ["msg_id", "type", "decap"],
  "properties": {
    "msg_id": {"type": "integer"},
    "type": {"const": "decap"},
    "decap": {
      "type": "object",
      "required": ["sid", "vrf"],
      "properties": {
        "sid": {"type": "string"},
        "vrf": {"type": "string"}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

**Validation Protocol (enforced in executor prompt):**
1. BEFORE `send_message`: Call `validate_srv6_message_schema(msg)`
2. If `valid == true`: Use the SAME message
3. If `valid == false`: FIX the message using error details, re-validate
4. Repeat until `valid == true`
5. ONLY AFTER validation succeeds call `send_message`

#### 3. Tools (tools.py)

**Wrapper functions for agent tools that encapsulate infrastructure:**

**Network State Access:**
```python
state = NetworkState("/opt/conf/topo.yaml")
```

**Message Broker:**
```python
broker = RabbitBroker()
sender = MessageSender(broker)
```

**Transaction DB:**
```python
db = dbTransaction()
```

**Key Functions:**

`convalid_tool(path: list) -> dict:`
```python
def convalid_tool(path: list) -> dict:
    """
    Verifies that the SRv6 tunnel has been actually configured.
    Returns: {"status": "true" | "false"}
    """
    # Extract border routers
    r1 = path[1]
    r2 = path[2]
    src = path[0]
    dst = path[-1]
    
    # Get addresses
    ip_src = get_host_ipv4(src).split("/")[0]
    ip_dst = get_host_ipv4(dst).split("/")[0]
    
    # Get SIDs
    sid1 = state.node_map[r1]["ipv6"]["sid"]
    sid2 = state.node_map[r2]["ipv6"]["sid"]
    sid = json.loads(get_sid_for_host(sid2, dst)).get("sid")
    my_sid = json.loads(get_sid_for_host(sid1, src)).get("sid")
    
    # Build validation message
    msg_id = db.get_messageID()
    msg = {
        "msg_id": msg_id,
        "type": "validate",
        "ip_src": ip_src,
        "ip_dst": ip_dst,
        "iface_next_hope": r1+"-"+r2,
        "sid": sid,
        "my_sid": my_sid,
    }
    
    send_message(r1, msg)
    result = wait_transaction_result([msg_id])
    return result
```

#### 4. NetworkState (state.py)

**Class:** `NetworkTopology`

**Initialization Process:**
```python
def __init__(self, file_path):
    self.node_map = {}
    self.graph = nx.Graph()
    self._build_map(file_path)
```

**_build_map(file_path) Logic:**
1. Parse YAML topology file
2. **Node classification:** `kind = 'host' if n.startswith('hs') else 'router'`
3. Node graph construction via NetworkX
4. **Link processing:**
   - Parse endpoints: `node1, intf1 = ep1.split(':')`
   - Build bidirectional interface map
   - **IPv4 assignment (host-to-router):**
     - Host: `10.0.{hs_num}.1/32`
     - Router: `10.0.{hs_num}.254`
     - VRF: `vrf{100+hs_num}`
   - **IPv6 assignment (router-to-router):**
     - `fcf0:0:{min}:{max}::{node_id}/64`
   - Add edge to graph
5. **SID assignment to routers:**
   - `fcf0:{node_num}::0/32`

**Public Methods:**
- `get_neighbors(node)` → `list(self.graph.neighbors(node))`
- `shortest_path(node1, node2)` → `nx.shortest_path(self.graph, source, target)`
- `get_border_routers(src_host, dst_host)` → `(path[1], path[-2])`
- `get_intermediate_routers(src_host, dst_host)` → `path[2:-2]` (if any)
- `print_map()` → Debug output of full topology
- `update_sid(router, new_sid)` → Modify router SID in memory

**Topology Data Structure:**
```python
self.node_map = {
    "hs1": {
        "type": "host",
        "interfaces": {"hs1-pe1": "pe1"},
        "ipv4": {"hs1-pe1": "10.0.1.1/32", "vrf": "vrf101"},
        "ipv6": {}
    },
    "pe1": {
        "type": "router",
        "interfaces": {
            "pe1-hs1": "hs1",
            "pe1-pe2": "pe2",
            "pe1-pe3": "pe3",
            "pe1-igw5": "igw5"
        },
        "ipv4": {
            "pe1-hs1": "10.0.1.254",
            ...
        },
        "ipv6": {
            "pe1-pe2": "fcf0:0:1:2::1/64",
            "pe1-pe3": "fcf0:0:1:3::1/64",
            "pe1-igw5": "fcf0:0:1:5::1/64"
        },
        "ipv6": {"sid": "fcf0:1::0/32"}
    },
    ...
}
```

#### 5. TransactionDB (transactionDB.py)

**Class:** `dbTransaction`

**Warning (explicit in code):**
```python
# classe non pensata essere thread-safe!!
```

**Data Model:**
```python
transaction = {
    "id": transaction_id,
    "src_host": str,
    "dst_host": str,
    "path": [list, of, nodes],
    "encap": {
        "ip": str,          # Destination IPv4
        "vrf": str,         # Source VRF
        "interface": str,   # Outgoing interface
        "sid": str          # Destination SID (implicit)
    },
    "decap": {
        "sid": str,         # Destination SID
        "vrf": str          # Destination VRF
    }
}
```

**Instance Variables:**
- `self.__transactionElement = {}` → Stores all transactions keyed by ID
- `self.__transactionID = 0` → Auto-incrementing counter
- `self.__messageID = 0` → Auto-incrementing message ID counter

**Methods:**

`newTransaction(src_host, dst_host, path, encap_info, decap_info) -> int:`
```python
def newTransaction(self, src_host, dst_host, path, encap_info, decap_info):
    transactionID = self.__transactionID
    self.__transactionID += 1
    element = {
        "id": transactionID,
        "src_host": src_host,
        "dst_host": dst_host,
        "encap": encap_info,
        "decap": decap_info,
        "path": path
    }
    self.__transactionElement[transactionID] = element
    return transactionID
```

`get_messageID() -> int:`
```python
def get_messageID(self):
    messageID = self.__messageID
    self.__messageID = self.__messageID + 1
    return messageID
```

`get_transaction(id) -> dict:`
```python
def get_transaction(self, id):
    e = self.__transactionElement.get(id, {})
    if not e:
        return {"error": "transaction id not valid"}
    return e
```

**Limitations:**
- In-memory storage only (no persistence)
- Not thread-safe (explicit comment)
- No transaction state machine (always "active" until deleted)
- No rollback completion tracking

#### 6. MessageQueueAdapter (messagging.py)

**Classes:** `RabbitBroker`, `MessageAggregator`, `MessageSender`

**RabbitMQ Topology:**
- **Exchange:** `routers` (topic type)
- **Router command queue:** `router.{router_name}.commands` (dedicated per router)
- **Master response queue:** `router.master.response` (shared for all responses)
- **Routing key pattern:** `router.{router_name}.commands`

**RabbitBroker Operations:**

`send(topic, message) -> None:`
```python
def send(self, topic, message):
    """Manda messaggio a router specifico via EXCHANGE TOPIC"""
    connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
    channel = connection.channel()
    
    channel.exchange_declare(exchange="routers", exchange_type="topic")
    channel.basic_publish(
        exchange="routers",
        routing_key=topic,  # e.g., "router.pe1.commands"
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  # persistent
    )
    connection.close()
```

`wait_messageIDs(expected_ids, timeout=60) -> bool:`
```python
def wait_messageIDs(self, expected_ids, timeout=60):
    connection = pika.BlockingConnection(...)
    channel = connection.channel()
    
    channel.queue_declare(queue="router.master.response", durable=True)
    aggregator = MessageAggregator(expected_ids, timeout)
    
    def callback(ch, method, properties, body):
        data = json.loads(body)
        aggregator.add_message(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    channel.basic_consume(
        queue="router.master.response",
        on_message_callback=callback
    )
    
    aggregator.start_time = time.time()
    while True:
        connection.process_data_events(time_limit=3)
        if aggregator.is_error_occurred():
            return False
        if aggregator.is_complete():
            connection.close()
            return True
        if time.time() - aggregator.start_time > timeout:
            connection.close()
            return False
```

**MessageAggregator Class:**

**State:**
- `self.status = {rid: 0 for rid in expected_ids}` → Track each message ID
- `self.timeout = timeout`
- `self.start_time = time.time()`
- `self.num_min = len(expected_ids)`
- `self.err = 0`

**Methods:**

`add_message(data):`
```python
def add_message(self, data):
    self.c += 1
    self.start_time = time.time()  # Reset on activity
    msg_id = data.get("msg_id")
    if data.get("status") == "error":
        self.err = 1
    if msg_id in self.status:
        self.status[msg_id] = 1
```

`is_error_occurred() -> bool:`
```python
def is_error_occurred(self):
    return self.err == 1
```

`is_complete() -> bool:`
```python
def is_complete(self):
    return all(v == 1 for v in self.status.values())
```

**MessageSender Class:**

`send(router, message):`
```python
def send(self, router: str, message: dict):
    topic = f"router.{router}.commands"
    self.broker.send(topic, message)
    return message
```

`wait_ack(expected_ids):`
```python
def wait_ack(self, expected_ids):
    return self.broker.wait_messageIDs(expected_ids)
```

### Router-Side Logic

#### Router Daemon (demone_reader.py)

**Class:** `RouterDaemon`

**Initialization Process:**
```python
def __init__(self, router_name, rabbit_host="rabbit"):
    self.router = router_name
    self.rabbit_host = rabbit_host
    self.handlers = {}  # Message type → handler function mapping
    self.response_queue = "router.master.response"
    self.queue = f"router.{self.router}.commands"
    
    # Compute SID from router number
    num = int(''.join(filter(str.isdigit, self.router)))
    self.sid = f"fcf0:{num}::1/32"
    
    self._connect()
```

`_connect() -> None:`
```python
def _connect(self):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=self.rabbit_host)
    )
    self.channel = connection.channel()
    
    # Declare exchange
    self.channel.exchange_declare(exchange="routers", exchange_type="topic")
    
    # Declare dedicated command queue
    self.channel.queue_declare(queue=self.queue, durable=True)
    
    # Declare shared response queue
    self.channel.queue_declare(queue=self.response_queue, durable=True)
    
    # Bind queue to exchange
    self.channel.queue_bind(
        exchange="routers",
        queue=self.queue,
        routing_key=self.queue  # routing_key = queue name
    )
```

`register_handler(message_type, func):`
```python
def register_handler(self, message_type, func):
    """Register a handler function for a message type"""
    self.handlers[message_type] = func
```

`_process_message(ch, method, properties, body) -> None:`
```python
def _process_message(self, ch, method, properties, body):
    try:
        message = json.loads(body)
        msg_id = message.get("msg_id")
        msg_type = message.get("type")
        print(f"[{self.router}] Received {msg_id} message:", message)
        
        # Validate message type exists
        if msg_type not in self.handlers:
            print(f"[{self.router}] No handler for type: {msg_type}")
            return
        
        # Execute handler
        handler = self.handlers[msg_type]
        result = handler(message)
        print("msg_type: ", msg_type, "- risposta: ", result)
        
        # Send response to shared queue
        response = {"msg_id": msg_id} | result  # Dict merge
        self.channel.basic_publish(
            exchange="",
            routing_key=self.response_queue,
            body=json.dumps(response),
        )
        
        # ACK the command queue
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    except Exception as e:
        print(f"[{self.router}] Error processing message:", e)
        response = {
            "msg_id": msg_id,
            "status": "error",
            "message": str(e)
        }
        self.channel.basic_publish(
            exchange="",
            routing_key=self.response_queue,
            body=json.dumps(response),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
```

`start() -> None:`
```python
def start(self):
    """Main message loop"""
    self.channel.basic_consume(
        queue=self.queue,
        on_message_callback=self._process_message,
        auto_ack=False  # Manual ACK
    )
    print(f"[{self.router}] Router daemon started sid: {self.sid}")
    self.channel.start_consuming()
```

**Message Handler Registration (main.py):**
```python
daemon = RouterDaemon(ROUTER_NAME)

daemon.register_handler("encap", handle_encap)
daemon.register_handler("decap", handle_decap)
daemon.register_handler("encap_rollback", handle_encap_rollback)
daemon.register_handler("decap_rollback", handle_decap_rollback)
daemon.register_handler("validate", validator_handler)

daemon.start()
```

**Connection Retry Logic:**
```python
max_retries = 30
attempt = 0
while attempt < max_retries:
    try:
        daemon = RouterDaemon(ROUTER_NAME)
        print("Connessione riuscita!")
        break
    except Exception as e:
        attempt += 1
        print(f"Tentativo {attempt}/{max_retries} fallito: {e}")
        time.sleep(1)
else:
    raise Exception("Impossibile connettersi")
```

#### Message Handlers (handlers.py)

Helper function: `_vrf_table_from_name(vrf)`:
```python
def _vrf_table_from_name(vrf: str) -> int:
    if not vrf.startswith("vrf"):
        raise ValueError(f"VRF name '{vrf}' not in format 'vrf<N>'")
    return int(vrf[3:])
```

`handle_encap(message) -> dict:`

**Expected message format:**
```json
{
  "msg_id": int,
  "type": "encap",
  "encap": {
    "ip": "<IPv4 destination>",
    "sid": "<SIDH>",
    "interface": "<outgoing_interface>",
    "vrf": "<source_vrf>"
  }
}
```

**Execution:**
```python
def handle_encap(message):
    encap = message.get("encap")
    if encap != None:
        ip = encap.get("ip")
        sid = encap.get("sid")
        iface = encap.get("interface")
        vrf = encap.get("vrf")
        if ip != None and sid != None and iface != None and vrf != None:
            r = srv6_encap_route(ip, sid, iface, vrf)
            print(f"Configure SRv6 encap {encap}")
            return r
    return {"status": "error", "message": "bad format"}
```

`srv6_encap_route(ip_host, sid_routers, interface, vrf) -> dict:`
```python
def srv6_encap_route(ip_host, sid_routers, interface, vrf):
    """
    Execute:
    ip route add table <tab> <ip_host> encap seg6 mode encap segs <sid_router> dev <interface>
    """
    table_id = _vrf_table_from_name(vrf)
    try:
        result = subprocess.run(
            ["ip", "route", "add", "table", str(table_id),
             ip_host, "encap", "seg6", "mode", "encap", "segs", sid_routers, "dev", interface],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status": "ok"}
        else:
            stderr = result.stderr.lower()
            if "file exists" in stderr:  # Idempotent
                return {"status": "ok"}
            return {"status": "error", "message": stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": result.stderr}
```

`handle_decap(message) -> dict:`

**Expected message format:**
```json
{
  "msg_id": int,
  "type": "decap",
  "decap": {
    "sid": "<SIDH>",
    "vrf": "<destination_vrf>"
  }
}
```

**Execution:**
```python
def handle_decap(message):
    decap = message.get("decap")
    if decap != None:
        sid = decap.get("sid")
        vrf = decap.get("vrf")
        if vrf != None and sid != None:
            r = srv6_decap_route(sid, vrf)
            print(f"Configure decap {decap}")
            return r
    return {"status": "error", "message": "bad format"}
```

`srv6_decap_route(sid, vrf) -> dict:`
```python
def srv6_decap_route(sid, vrf):
    """
    Execute:
    ip -6 route add <sid> encap seg6local action End.DT4 vrftable <tab> dev <vrf>
    """
    table_id = _vrf_table_from_name(vrf)
    try:
        ret = route_exists(sid.split("/")[0], table_id)
        if ret:
            return {"status": "ok"}
        result = subprocess.run(
            ["ip", "-6", "route", "add", sid.split("/")[0] + "/128",
             "encap", "seg6local", "action", "End.DT4",
             "vrftable", str(table_id), "dev", vrf],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status": "ok"}
        else:
            stderr = result.stderr.lower()
            if "file exists" in stderr:  # Idempotent
                return {"status": "ok"}
            return {"status": "error", "message": stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": result.stderr}
```

`route_exists(sid, tab) -> bool:`
```python
def route_exists(sid, tab):
    result = subprocess.run(
        ["ip", "-6", "route", "show"],
        capture_output=True,
        text=True
    )
    return sid in result.stdout
```

`handle_encap_rollback(message) -> dict:`

**Expected message format:**
```json
{
  "msg_id": int,
  "type": "encap_rollback",
  "ip": "<IPv4 /24>",
  "vrf": "<vrf>",
  "dev": "<interface>"
}
```

**Execution:**
```python
def handle_encap_rollback(message):
    print("Executing encap rollback handler")
    ip = message.get("ip")
    vrf = message.get("vrf")
    dev = message.get("dev")
    if ip != None and vrf != None and dev != None:
        r = srv6_del_encap_route(ip, vrf, dev)
        return r
    return {"status": "error", "message": "bad format"}
```

`srv6_del_encap_route(ip, vrf, dev) -> dict:`
```python
def srv6_del_encap_route(ip, vrf, dev):
    """
    Execute:
    ip route del <ip> table <tab> dev <dev>
    """
    table_id = _vrf_table_from_name(vrf)
    try:
        result = subprocess.run(
            ["ip", "route", "del", ip.split("/")[0], "table", str(table_id), "dev", dev],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status": "ok"}
        else:
            stderr = result.stderr.lower()
            if "no such process" in stderr:  # Idempotent
                return {"status": "ok"}
            return {"status": "error", "message": stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": result.stderr}
```

`handle_decap_rollback(message) -> dict:`

**Expected message format:**
```json
{
  "msg_id": int,
  "type": "decap_rollback",
  "sid": "<SIDH>",
  "vrf": "<vrf>"
}
```

**Execution:**
```python
def handle_decap_rollback(message):
    print("Executing decap rollback handler")
    sid = message.get("sid")
    vrf = message.get("vrf")
    if sid != None and vrf != None:
        r = srv6_del_decap_route(sid, vrf)
        return r
    return {"status": "error", "message": "bad format"}
```

`srv6_del_decap_route(sid, vrf) -> dict:`
```python
def srv6_del_decap_route(sid, vrf):
    """
    Execute:
    ip -6 route del <sid> encap seg6local action End.DT4 vrftable <tab> dev <vrf>
    """
    table_id = _vrf_table_from_name(vrf)
    try:
        result = subprocess.run(
            ["ip", "-6", "route", "del", sid,
             "encap", "seg6local", "action", "End.DT4",
             "vrftable", str(table_id), "dev", vrf],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status": "ok"}
        else:
            stderr = result.stderr.lower()
            if "no such process" in stderr:  # Idempotent
                return {"status": "ok"}
            return {"status": "error", "message": stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": result.stderr}
```

#### Validator Handler (validator_handler.py)

**Purpose:** Active tunnel validation via packet injection and response observation

**Global State (issue - hard-coded IPs):**
```python
iface_send = "pe1-hs1"  # Interface for sending
h1_ip = "10.0.1.1"      # Hard-coded source
h2_ip = "10.0.5.1"      # Hard-coded destination
sid_list = ["fcf0:2::5"]
expected_sid = "fcf0:1::1"
reply_received = False
```

**Validation Logic:**
```python
def validator_schema(ip_src, ip_dst, iface_recv, sid, my_sid):
    global reply_received
    reply_received = False
    
    def check_srv6_reply(p):
        global reply_received
        if IPv6 in p:
            ipv6 = p[IPv6]
            # Check outer destination
            if ipv6.dst != my_sid:
                return False
            # Check for SRH
            if not p.haslayer(IPv6ExtHdrSegmentRouting):
                return False
            # Check for inner IPv4
            if not p.haslayer(IP):
                return False
            ip = p[IP]
            # Check inner address (reversed)
            if ip.src != ip_dst or ip.dst != ip_src:
                return False
            # Check ICMP type (echo reply)
            if not p.haslayer(ICMP):
                return False
            icmp = p[ICMP]
            if icmp.type == 0 and icmp.id == 1234:
                print("[+] SRv6 reply correct received!")
                reply_received = True
                return True
        return False
    
    # Start sniffer thread
    def sniff_thread():
        sniff(
            iface=iface_recv,
            filter="ip6",
            store=False,
            prn=check_srv6_reply,
            timeout=10  # Max 10 seconds
        )
    
    thread = threading.Thread(target=sniff_thread)
    thread.start()
    time.sleep(0.5)
    
    # Craft and send test packet
    inner_pkt = IP(src=ip_src, dst=ip_dst) / ICMP(id=1234, seq=1)
    srh = IPv6ExtHdrSegmentRouting(addresses=[sid])
    pkt = IPv6(dst=sid) / srh / inner_pkt
    print("[*] Sending SRv6 encapsulated ping...")
    send(pkt, verbose=False)
    
    thread.join(timeout=10)
    
    if reply_received:
        print("[SUCCESS] Tunnel functional")
        return {"status": "ok"}
    else:
        print("[FAIL] No response received")
        return {"status": "error", "message": "not packet send"}
```

**Handler Entry Point:**
```python
def validator_handler(msg):
    ip_src = msg.get("ip_src")
    ip_dst = msg.get("ip_dst")
    iface_recv = msg.get("iface_next_hope")
    sid = msg.get("sid")
    my_sid = msg.get("my_sid")
    
    if all([ip_src, ip_dst, iface_recv, sid, my_sid]):
        r = validator_schema(ip_src, ip_dst, iface_recv, sid, my_sid)
        print(r)
        return r
    return {"status": "error", "message": "bad format"}
```

### Queue-based / Messaging Logic

**Architecture:**
- RabbitMQ message broker
- Topic exchange for command routing
- Shared response queue for acknowledgments
- No pub/sub; all point-to-point communication

**Message Correlation:**
- Each command has unique `msg_id` (generated by master)
- Response echoes same `msg_id`
- Master correlates via `MessageAggregator`

**Connection Pattern:**
- New connection per message send (no pooling)
- Blocking connection (synchronous)
- Auto-reconnect on failure (30 retries in daemon)

### Transaction Handling

**Lifecycle:**
1. `create_transaction()` → Allocate ID, store routing info
2. `send_message()` → Send command (**not** tracked in transaction yet)
3. `wait_transaction_result()` → Wait for msg_id acknowledgments
4. On success: Transaction finalized (no explicit "complete" state)
5. On failure/cancel: `rollback_transaction()` → Send rollback commands

**State Model:**
- In-memory dictionary in `dbTransaction`
- No persistence across restarts
- No state machine (no transitional states like "pending", "committing")
- **Not thread-safe** (explicit comment)

### Validation Logic

**Three-tier validation:**

1. **Pre-execution (master-side):**
   - JSON schema validation (`validate_srv6_message_schema`)
   - Blocks message sending if invalid
   - Agent prompted to fix and re-validate

2. **Post-execution (router-side):**
   - Handler execution returns `{"status": "ok"}` or error
   - Master interprets missing acknowledgment as error

3. **Active validation (on-demand):**
   - `convalid_tool()` triggers router validator
   - Simulates end-to-end traffic
   - Reports tunnel functionality

### Rollback Logic

**Trigger conditions:**
- Executor agent timeout during `create_connection`
- Planner agent reverse path failure
- Explicit timeout (60s default)

**Execution:**
1. Retrieve original transaction: `get_transaction(id)`
2. Construct rollback messages:
   - encap_rollback: uses original ip, vrf, dev
   - decap_rollback: uses original sid, vrf
3. Send rollback commands to same routers (path[1] and path[-2])
4. Wait for acknowledgment
5. Return status

**Idempotency:**
- Deletion commands are idempotent
- Missing routes → return success ("no such process")

---

## SECTION C — Control Workflow

### 1. Startup Sequence

**Step-by-step:**

**Phase 1: Containerlab deployment**
```bash
sudo make deploy
```
- Pulls `ubuntu-node:latest` image for 15 nodes
- Pulls `rabbitmq:latest` for message broker
- Creates 19 point-to-point links
- Assigns container names: `clab-{topo_name}-{node}` (e.g., `clab-srv6-inest-demo-new-hs1`)

**Phase 2: Node initialization (all nodes in parallel)**
```bash
/opt/clab/lib/startup.sh
```
- Extract hostname: `hostname -s` (e.g., "hs3", "pe2", "master")
- Match regex: `(hs|pe|igw|egw)(\d+)`
- Determine node type from prefix
- Source corresponding script (host.sh, pe.sh, etc.)

**Phase 3: Router initialization (pe*, igw*, egw*)**
- `common.sh` executes:
  - Interface discovery and IPv4/IPv6 assignment
  - Static route loading from config file
  - VRF creation for attached hosts
- Start router daemon:
  ```bash
  source /.venv/bin/activate
  nohup python3 -u /opt/clab/lib/demone_router/main.py > /var/log/output_router.log 2>&1 &
  ```

**Phase 4: Host initialization (hs*)**
- `common.sh` configures interfaces and VRFs
- Sets default route via router's IPv4 address
- Configures VRF bridging (veth pairs)

**Phase 5: Master initialization**
- Checks for `.env` file with `API_TOKEN`
- Enters interactive planner agent loop:
  ```bash
  python3 /opt/clab/lib/agent_ai/planner_agent.py
  ```

### 2. Successful Tunnel Provisioning Request

**User interaction:**
```
User > Puoi crearmi un tunnel hs1 a hs5?
```

**Execution flow:**

**Step 1: Planner parsing**
- Prompt: "You are an SRv6 Orchestrator Agent"
- Natural language → src=hs1, dst=hs5
- Validate hosts exist

**Step 2: Forward path (hs1 → hs5)**

1. `compute_route("hs1", "hs5")` → `{"path": ["hs1", "pe1", "pe2", "hs5"], "segments": ["pe1", "pe2"]}`

2. Planner invokes executor:
   ```
   exe_agent with:
   - src_host: hs1
   - dst_host: hs5
   - path: [hs1, pe1, pe2, hs5]
   ```

3. Executor validates path (len >= 2 routers)

4. Gather network info:
   - first_router = pe1, last_router = pe2
   - SID of pe2: `fcf0:2::0/32`
   - SIDH: `fcf0:2::5/32` (host 5 specific)
   - IPv4 of hs5: `10.0.5.1/24`
   - VRFs: vrf101 (hs1), vrf105 (hs5)
   - Interface pe1→pe2: `pe1-pe2`

5. Generate message IDs:
   - msg_id_encap = 0
   - msg_id_decap = 1 (auto-increment in transactionDB)

6. Build encap message:
   ```json
   {
     "msg_id": 0,
     "type": "encap",
     "encap": {
       "ip": "10.0.5.1",
       "sid": "fcf0:2::5/32",
       "interface": "pe1-pe2",
       "vrf": "vrf101"
     }
   }
   ```

7. Build decap message:
   ```json
   {
     "msg_id": 1,
     "type": "decap",
     "decap": {
       "sid": "fcf0:2::5/32",
       "vrf": "vrf105"
     }
   }
   ```

8. Validate schemas before sending:
   ```python
   validate_srv6_message_schema(encap_msg)
   validate_srv6_message_schema(decap_msg)
   ```

9. Create transaction:
   ```python
   transaction_id = create_transaction(
       src="hs1", dst="hs5",
       path=["hs1", "pe1", "pe2", "hs5"],
       encap_info={"ip": "10.0.5.1", "vrf": "vrf101", "interface": "pe1-pe2"},
       decap_info={"sid": "fcf0:2::5/32", "vrf": "vrf105"}
   )
   # Returns: transaction_id = 0
   ```

10. Send messages:
    ```python
    send_message("pe1", encap_msg)
    send_message("pe2", decap_msg)
    ```

11. Wait for acks:
    ```python
    wait_transaction_result([0, 1])
    # Time: 0-10 seconds
    # Result: {"status": "success"}
    ```

12. Executor returns:
    ```json
    {
      "transaction_id": 0,
      "status": "success"
    }
    ```

13. Planner saves `forward_transaction_id = 0`

**Step 3: Reverse path (hs5 → hs1)**
- Repeat process with src=hs5, dst=hs1
- Path: ["hs5", "pe2", "pe1", "hs1"]
- Similar message exchange
- Transaction_id = 1 for reverse
- Both pe2 and pe1 acknowledge
- `reverse_transaction_id = 1`

**Step 4: Validation**
- Planner calls `convalid_tool(["hs1", "pe1", "pe2", "hs5"])`
- Builds validator message:
  ```json
  {
    "msg_id": 2,
    "type": "validate",
    "ip_src": "10.0.1.1",
    "ip_dst": "10.0.5.1",
    "iface_next_hope": "pe1-pe2",
    "sid": "fcf0:2::5/32",
    "my_sid": "fcf0:1::1/32"
  }
  ```
- Sends to pe1
- pe1 validator:
  - Sniffs on pe1-pe2 interface (10s timeout)
  - Sends SRv6-encapsulated ICMP echo
  - Receives reply
  - Returns `{"status": "ok"}`
- convalid_tool returns `{"status": "success"}`

**Step 5: Report**
- Planner outputs to user (natural language):
  "SRv6 tunnel hs1 ↔ hs5 successfully configured and validated"

### 3. Failed Request with Rollback

**Scenario:** Forward path succeeds, reverse path fails

**Flow:**

**Forward path (hs1 → hs5):**
- Executor creates transaction_id = 0
- pe1 and pe2 acknowledge
- Success: `forward_transaction_id = 0`

**Reverse path (hs5 → hs1):**
- Executor sends decap message to pe1
- **Timeout (60s) waiting for ack**
- `wait_transaction_result()` returns `False`
- Executor triggers rollback:
  ```python
  rollback_transaction(0)
  # Retrieves transaction 0
  # Sends encap_rollback to pe1
  # Sends decap_rollback to pe2
  # Waits for acks
  # Returns {"status": "success"}
  ```

**Planner Agent:**
- Receives error from executor: "reverse path failed, rollback executed"
- Aborts: does not attempt validation
- Reports to user: "Tunnel configuration failed, reverse path timeout, forward transaction rolled back"

### 4. Validation of a Tunnel

**Trigger:**
- Planner calls `convalid_tool(path)` after both directions succeed

**Process:**
1. Extract routers: r1 = path[1], r2 = path[2]
2. Get IPs: `ip_src = get_host_ipv4(src)`, `ip_dst = get_host_ipv4(dst)`
3. Get SIDs: `sid1`, `sid2`
4. Compute SIDH for src and dst
5. Build validator message
6. Send to r1
7. r1 validator handler:
   - Spawns sniffer thread on interface r1→r2
   - Crafts ICMP packet (src=hs1, dst=hs5)
   - Encapsulates in SRv6 with dst SID
   - Sends packet
   - Waits for SRv6-encapsulated ICMP echo reply (type=0, id=1234)
8. **Success criteria:**
   - Reply received within 10s
   - Outer IPv6 dest == my_sid
   - Reply has SRH header
   - Inner IPv4 has swapped src/dst
9. Return result to planner

---

## SECTION D — Data and Message Model

### Message Types

| Type | Direction | Fields | Purpose |
|------|-----------|--------|---------|
| `encap` | master→router | msg_id, encap.{ip, sid, interface, vrf} | Add IPv4→SRv6 encapsulation route |
| `decap` | master→router | msg_id, decap.{sid, vrf} | Add SRv6 End.DT4 decapsulation route |
| `encap_rollback` | master→router | msg_id, ip, vrf, dev | Remove encap route |
| `decap_rollback` | master→router | msg_id, sid, vrf | Remove decap route |
| `validate` | master→router | msg_id, ip_src, ip_dst, iface_next_hope, sid, my_sid | Test tunnel functionality |
| **response** | router→master | msg_id, status, [message] | Acknowledgment for any command |

### Response Format

**Success:**
```json
{
  "msg_id": <int>,
  "status": "ok"
}
```

**Error:**
```json
{
  "msg_id": <int>,
  "status": "error",
  "message": "<error description>"
}
```

### Correlation Identifiers

**msg_id:**
- Generated by `dbTransaction.get_messageID()`
- Auto-incrementing counter (0, 1, 2, ...)
- Not globally unique across restarts
- Used for request→response correlation
- Stored in `dbTransaction._dbTransaction__messageID`

**transaction_id:**
- Generated by `dbTransaction.newTransaction()`
- Auto-incrementing counter per transaction
- Used to retrieve transaction for rollback
- Stored in `dbTransaction._dbTransaction__transactionID`

### State Tracking (per transaction)

**Data structure (in dbTransaction):**
```python
{
  transaction_id: {
    "id": int,                    # Transaction ID
    "src_host": str,              # e.g., "hs1"
    "dst_host": str,              # e.g., "hs5"
    "path": [str],                # e.g., ["hs1", "pe1", "pe2", "hs5"]
    "encap": {
      "ip": str,                  # Destination IPv4
      "vrf": str,                 # Source VRF
      "interface": str            # Outgoing interface
    },
    "decap": {
      "sid": str,                 # Destination SID
      "vrf": str                  # Destination VRF
    }
  }
}
```

### State Tracking (per message acknowledgment)

**Data structure (in MessageAggregator):**
```python
{
  msg_id: 0|1,  # 0=pending, 1=acknowledged
}
```

**Additional flags:**
- `err: 0|1` → Error flag if any response has status=="error"

---

## SECTION E — Benchmarking-Relevant Features

### Reproducibility

| Feature | Implementation |
|---------|---------------|
| **Deterministic topology** | Static `topo.yaml` file with 17 nodes, 19 links |
| **Deterministic addressing** | Algorithmic IPv4/IPv6/SID assignment based on node numbers |
| **Deterministic routing** | Shortest path via NetworkX (no dynamic protocols) |
| **Containerized environment** | Docker + Containerlab for consistent deployment |
| **Versioned dependencies** | `requirements.txt` with exact package versions |
| **Deterministic LLM** | Temperature = 0.0 in agent configuration |
| **No randomness** | No random failures, timeouts, or backoffs |

### Observability

| Aspect | Implementation |
|--------|---------------|
| **Message logging** | Router daemon logs to `/var/log/output_router.log` |
| **Transaction tracking** | `dbTransaction` maintains in-memory transaction history |
| **Tool invocation** | Agent tool calls logged (partially commented in executor) |
| **Packet capture** | Validator spawns scapy sniffer on specific interface |
| **Error tracing** | Exception details included in error responses |
| **Status reporting** | Explicit success/error in every response |

### Deterministic Execution

| Feature | Implementation |
|---------|---------------|
| **Timeouts** | 60s for transactions, 10s for validation (fixed) |
| **Idempotent operations** | Handlers treat "exists"/"not exists" as success |
| **Retry logic** | Router daemon retries RabbitMQ connection 30 times |
| **State isolation** | Transaction DB is in-memory, no cross-contamination |
| **Auto-ACK** | Manual ACK in daemon, but response always sent |

### Structured Interfaces

| Interface | Protocol | Description |
|-----------|----------|-------------|
| Agent ↔ Tools | Python function calls | Tools decorated with `@tool` |
| Master ↔ Router | RabbitMQ topic exchange | JSON messages with msg_id + type |
| Router ↔ Kernel | subprocess calls | Linux `ip route` commands |
| Agent ↔ LLM | datapizza-ai framework | Structured prompts and tool bindings |

### Ability to Compare Different Agents

**Design features enabling agent substitution:**

1. **Planner agnosticism:**
   - Planner knows only tools, not implementation details
   - New planner can be implemented with different reasoning
   - Same `list_hosts()`, `compute_route()`, `exe_agent` interfaces
   - Agent prompt structure is modular

2. **Executor protocol:**
   - Executor conforms to `create_connection` / `abort_transaction` contract
   - Agent prompt includes strict JSON schema and retry logic
   - Replacement executor only needs to implement same tool interface
   - Internal logic can vary (LLM, rule-based, ML model)

3. **Tool abstraction layer:**
   - Tools wrap infrastructure (state, messaging, DB)
   - Agent framework sees tools as atomic operations
   - Tools can be reimplemented with different backends

4. **Router daemon invariance:**
   - Message handlers are protocol-locked
   - Independent of agent implementation
   - Can be replaced with gRPC, REST, or alternative daemon

### Logging/Auditing

| Aspect | Implementation |
|--------|---------------|
| **Command audit trail** | Message IDs, transaction IDs logged |
| **Router output** | `/var/log/output_router.log` (per-node) |
| **Agent state** | Memory object in datapizza framework (not persisted) |
| **Validation results** | Explicit success/failure responses |

### Fault Injection Hooks (Conceptual, not fully implemented)

**Potential entry points:**
1. **Message timeouts:** Built-in 60s timeout, can be reduced to test retry
2. **Router failures:** No active failure injection in daemon
3. **Network partitions:** No simulation capability
4. **Packet drops:** No QoS or loss modeling
5. **Schema errors:** Can deliberately send malformed messages

---

## SECTION F — Gaps and Recommendations

### What is Missing for the Paper Narrative

| Gap | Recommendation |
|-----|----------------|
| **Explicit benchmark metrics** | Define KPIs: tunnel setup latency, success rate, rollback latency, validation accuracy |
| **Multi-agent scenarios** | Implement concurrent tunnel requests to test agent interaction |
| **Failure injection framework** | Add automated fault injection (timeout reduction, packet loss, node failures) |
| **Agent comparison harness** | Create benchmark runner that swaps agent implementations |
| **Metrics collection** | Add Prometheus endpoint or structured logging for analysis |
| **Persistent state** | Add SQLAlchemy/SQLite backend for transaction recovery |

### Implemented but Should be Described More Clearly

| Aspect | Clarification Needed |
|--------|----------------------|
| **Validator hard-coded IPs** | `validator_handler.py` has hs1/hs5 hardcoded. Should be dynamic from message parameters |
| **Transaction not thread-safe** | Explicit comment in `transactionDB.py`. Needs awareness for concurrent benchmarks |
| **Schema validation partial** | Only encap/decap validated. Rollback/validate messages not validated at agent level |
| **No state persistence** | All transaction state lost on restart. Frame as design choice (ephemeral experiments) |
| **Blocking messaging** | No async operations. Blocks master during message waits |

### What Should be Generalized in Wording

| Over-specific term | Generalized term |
|--------------------|------------------|
| "Planner Agent", "Executor Agent" | "High-level orchestrator", "Low-level executor" |
| "SRv6", "End.DT4", "SIDH" | "Segment-routing protocols", "Tunnel encapsulation", "Forwarding identifiers" |
| "RabbitMQ" | "Message broker (currently RabbitMQ)" |
| "datapizza-ai framework" | "LLM agent framework" |
| "Containerlab" | "Containerized network simulation" |
| "uSID" | "Micro-segment identifiers" |

### Prototype Limitations (To Acknowledge in Paper)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Single transaction at a time** | Cannot benchmark concurrent demand | Queue-based serialization |
| **In-memory state** | State lost on restart | Document as "stateless benchmarking" |
| **Hard-coded validator IPs** | Validation only works for specific paths | Fix to use dynamic parameters |
| **No network dynamics** | Static topology, no link failures | Extend with fault injection |
| **Monolithic agent design** | Planner and executor tightly coupled | Decouple via API |
| **No validation schema** | Rollback/validate messages not validated | Add additional schemas |
| **Blocking send/receive** | No async operations | Use asyncio-based messaging |
| **No concurrency** | Sequential processing only | Add thread/async support |

---

## SECTION G — Material Reusable in the Paper

### System Architecture Section (directly reusable bullets)

- 17-node containerized testbed (8 hosts, 7 routers, 1 master, 1 message broker) implemented with Containerlab
- Topology defined in declarative YAML with algorithmic address assignment
- Static SRv6 routing with uSID (micro-segment identifier) encoding
- Separation of concerns:
  - Master: AI agent reasoning, policy generation, transaction management
  - Routers: Deterministic command execution, telemetry reporting
- Message-based control plane using RabbitMQ topic exchange
- Router-side daemon pattern: persistent listener, per-type handler registration
- Bidirectional tunnel provisioning (two unidirectional transactions)

### Agent-to-Network Interface Section (directly reusable bullets)

- Structured JSON message protocol with correlation IDs
- Four primary operations: encap, decap, encap_rollback, decap_rollback
- Optional validation operation using packet injection (scapy-based)
- Idempotent handlers (existence checks, graceful error handling)
- 60-second timeout for command acknowledgment
- Router message schema enforced via Python jsonschema validation
- Explicit state tracking via in-memory transaction database

### Benchmarking Playground Section (directly reusable bullets)

- Reproducible environment: deterministic topology, addressing, routing
- Reproducible agent loop: temperature=0.0, explicit prompts, tool invocation
- Observable execution: message identifiers, transaction IDs, error tracing
- Transaction-based state management with automatic rollback capability
- Tool abstraction layer for decoupling reasoning from infrastructure
- Agent substitution model: replace planner/executor without changing infrastructure

### Discussion / Limitations Section (directly reusable bullets)

- Single-request-at-a-time processing (no concurrency)
- In-memory state (no persistence across restarts)
- Static topology (no link/node failures simulated)
- Prototype code quality issues:
  - Hard-coded parameters in validation handler
  - Missing schema validation for rollback/validate messages
  - Thread safety concerns in transaction store
- Future work: fault injection, concurrent benchmarks, persistent state

---

## Architectural Diagram

### Architecture Overview

```
+--------------------------+
|       MASTER NODE        |
+--------------------------+
           |
           v
+--------------------------+
|     PLANNER AGENT        |
|     (Orchestrator)       |
+--------------------------+
           |
           v
+--------------------------+
|     EXECUTOR AGENT       |
|    (Transaction Mgr)     |
+--------------------------+
           |
           v
+--------------------------+
|      TOOL LAYER          |
+--------------------------+
|- state.py (NetworkTop)   |
|- tools.py (16 tools)     |
|- transactionDB.py        |
|- messaging.py            |
+--------------------------+
           |
           v
+--------------------------+
|    RABBITMQ BROKER       |
+--------------------------+
| Exchange: routers topic  |
| Queues:                  |
|- router.id.commands      |
|- router.master.response  |
+--------------------------+
         |         |
         v         v
+------------+ +------------+
|PE1 DAEMON  | |PE2 DAEMON  |
+------------+ +------------+
|E/D/R/V     | |E/D/V       |
+------------+ +------------+
         |         |
         +----+----+
              |
              v
+--------------------------+
|    LINUX KERNEL(SRv6)    |
+--------------------------+
|- IPv4  -> SRv6 encap     |
|- SRv6  -> IPv4 decap     |
|- VRF tables isolation    |
+--------------------------+
           |
           v
+--------------------------+
|    RESPONSE (shared)     |
| {msg_id,status,message}  |
+--------------------------+
```

**Legend:** E=encap  D=decap  R=rollback  V=validate

### Detailed Architecture

```
+--------------------------+
|       MASTER NODE        |
+--------------------------+
| +----------------+       |    
| | PLANNER AGENT  |       | 
| | (Orchestrator) |---+   | 
| +----------------+   |   |
|                      |   |
| +----------------+   |   |
| | EXECUTOR AGENT |<--+   |
| | (Transaction)  |       |
| +----------------+       |    
+--------------------------+
           |
           v
+--------------------------+
|      TOOL LAYER          |
+--------------------------+
|- state.py (NetworkTop)   |
|- tools.py (16 tools)     |
|- transactionDB.py        |
|- messaging.py            |
|- validation.py           |
+--------------------------+
           |
           v
+--------------------------+
|    RABBITMQ BROKER       |
+--------------------------+
| Exchange: routers topic  |
| Queues:                  |
|- router.id.commands      |
|- router.master.response  |
+--------------------------+
         |         |
         v         v
+------------+ +------------+
|PE1 DAEMON  | |PE2 DAEMON  |
+------------+ +------------+
|Handlers:   | |Handlers:   |
|E/D/R/V     | |E/D/V       |
+------------+ +------------+
         |         |
         +----+----+
              |
              v
+--------------------------+
|    LINUX KERNEL(SRv6)    |
+--------------------------+
|- IPv4  -> SRv6 encap     |
|- SRv6  -> IPv4 decap     |
|- VRF tables isolation    |
+--------------------------+
           |
           v
+--------------------------+
|    RESPONSE (shared)     |
| {msg_id,status,message}  |
+--------------------------+
```

### Message Flow: Tunnel Setup

```
User: "tunnel hs1 to hs5"
           |
           v
+--------------------------+
|     PLANNER AGENT        |
| 1. compute_route()       |
| 2. returns: [hs1...]     |
+--------------------------+
           |
           v
+--------------------------+
|     EXECUTOR AGENT       |
| 1. encap -> pe1          |
| 2. decap -> pe2          |
| 3. Create txn (ID:0)     |
| 4. Wait acks (60s)       |
+--------------------------+
         |         |
         v         v
+------------+ +------------+
|PE1 DAEMON  | |PE2 DAEMON  |
+------------+ +------------+
|[encap]     | |[decap]     |
+------------+ +------------+
         |         |
         v         v
+------------+ +------------+
|IPv4->SRv6  | |SRv6->IPv4  |
+------------+ +------------+
|route add   | |route add   |
+------------+ +------------+
        |         |
        +----+----+
             | 
             v 
       +------------+
       |Ack: ok     |
       +------------+
             |
             v
       +------------+
       |SUCCESS     |
       +------------+
```

### Message Flow: Rollback

```
Error/Timeout detected
           |
           v
+--------------------------+
|     PLANNER AGENT        |
| 1. Detect failure        |
| 2. Trigger rollback      |
+--------------------------+
           |
           v
+--------------------------+
|     EXECUTOR AGENT       |
| 1. rollback(ID)          |
| 2. Query txn DB          |
+--------------------------+
        |         |
        v         v
+------------+ +------------+
|PE1 DAEMON  | |PE2 DAEMON  |
+------------+ +------------+
|rollback    | |rollback    |
|encap       | |decap       |
+------------+ +------------+
        |         |
        v         v
+------------+ +------------+
|route del   | |route del   |
+------------+ +------------+
        |         |
        +----+----+
             |
             v
       +------------+
       |SUCCESS     |
       +------------+
```

### Message Flow: Validation

```
Tunnel established
           |
           v
+--------------------------+
|     PLANNER AGENT        |
| 1. convalid_tool(path)   |
| 2. Path: pe1->pe2        |
+--------------------------+
           |
           v
+--------------------------+
|      SEND MESSAGE        |
| [validate]->pe1 daemon   |
+--------------------------+
           |
           v
+--------------------------+
|        PE1 DAEMON        |
|   (validator handler)    |
+--------------------------+
| 1. Spawn sniffer(10s)    |
| 2. Craft ICMP packet     |
| 3. SRv6 encapsulate      |
| 4. Send packet           |
| 5. Wait reply            |
+--------------------------+
           |
           v
+--------------------------+
|          RESULT          |
| - reply OK -> status ok  |
| - reply err -> status e  |
+--------------------------+
           |
           v
+--------------------------+
|Return status to planner  |
+--------------------------+
```

### Component Layers

```
+--------------------------+
|   Layer 6: KERNEL        |
|  - Linux network stack   |
|  - SRv6 encap/decap      |
|  - VRF tables            |
+--------------------------+
           ^
           |
+--------------------------+
|   Layer 5: EXECUTION     |
|  - Router Daemon         |
|  - Message Handlers      |
+--------------------------+
           ^
           |
+--------------------------+
|   Layer 4: TRANSPORT     |
|  - RabbitMQ Exchange     |
+--------------------------+
           ^
           |
+--------------------------+
|   Layer 3: ABSTRACTION   |
|  - NetworkTopology       |
|  - Tools (tools.py)      |
|  - TransactionDB         |
|  - Messaging             |
+--------------------------+
           ^
           |
+--------------------------+
|  Layer 2: ORCHESTRATION  |
|  - Planner Agent         |
|  - Executor Agent        |
+--------------------------+
           ^
           |
+--------------------------+
|  Layer 1: PRESENTATION   |
|  - User Interface        |
+--------------------------+
```

### Component Interaction Matrix

```
+----------+------------+-------------+------+
|From    |To        |Method     |Response    |
+----------+------------+-------------+------+
|Planner |Executor  |Tool call  |Txn ID      |
|Executor|Tools     |Tool calls |Variable    |
|Tools   |RabbitMQ  |Publish    |None        |
|Tools   |TransactDB|Read/Write |Data        |
|RabbitMQ|Router    |Sub/Emit   |None        |
|Router  |Handler   |Invoke     |Result      |
|Handler |LinuxKern |Subproc    |Exit status |
|Router  |RabbitMQ  |Publish    |None        |
|RabbitMQ|Planner   |Subscribe  |Response    |
+----------+------------+-------------+------+
```

### Data Flow Summary

```
+--------------------------+
|     PLANNER AGENT        |
+--------------------------+
| Input: User intent       |
| Output: Path plan        |
+--------------------------+
           |
           v
+--------------------------+
|     EXECUTOR AGENT       |
+--------------------------+
| Input: Path, hosts       |
| Output: Txn ID, ack      |
+--------------------------+
           |
           v
+--------------------------+
|      TOOL LAYER          |
+--------------------------+
| Input: Tool calls        |
| Output: Topology, msg    |
+--------------------------+
           |
           v
+--------------------------+
|      RABBITMQ            |
+--------------------------+
| Input: JSON messages     |
| Routing: topic-based     |
+--------------------------+
           |
           v
+--------------------------+
|    ROUTER DAEMONS        |
+--------------------------+
| Input: encap/decap       |
| Output: Status ok/err    |
+--------------------------+
           |
           v
+--------------------------+
|    LINUX KERNEL(SRv6)    |
+--------------------------+
| Input: ip route cmds     |
| Output: Forwarded pkts   |
+--------------------------+
```

### Key Design Principles

**1. Separation of Concerns**
- Planner: High-level reasoning
- Executor: Transaction management
- Daemon: Deterministic execution

**2. Message-Driven Architecture**
- No shell commands from agent
- Structured JSON protocol
- Correlation via msg_id

**3. Transactional Execution**
- State tracking (TxnDB)
- Atomic operations (encap+decap)
- Auto rollback on failure

**4. Observability**
- Message correlation
- Transaction logging
- Active validation

**5. Benchmark-Friendly**
- Deterministic topology/addressing
- Containerized (reproducible)
- Reusable design principles

## Code Modules to Paper Concepts Mapping

| Paper Concept | Code Modules |
|---------------|--------------|
| **Network substrate** | `topo.yaml`, `state.py`, `common.sh`, `pe.sh`/`igw.sh`/`egw.sh` |
| **Control plane** | `messagging.py`, `demone_reader.py`, `handlers.py` |
| **Policy engine** | `planner_agent.py`, `executor_agent.py` |
| **Transaction manager** | `transactionDB.py`, tools.py (create_transaction, rollback_transaction) |
| **Observability** | `validator_handler.py`, router log files, `convalid_tool()` |
| **Agent framework** | `planner_agent.py`, `executor_agent.py` (datapizza-ai) |
| **Message protocol** | `messagging.py`, `demone_reader.py` (RabbitMQ topic exchange) |
| **State management** | `state.py`, `transactionDB.py` |
| **Failure handling** | `executor_agent.py` (rollback logic), `handlers.py` (idempotent operations) |
| **Benchmarking framework** | Makefile, startup.sh, tool abstraction layer |

---

## Concrete Code Artifacts for Paper Citations

| Artifact | File Path | Description | Lines |
|----------|-----------|-------------|-------|
| **Topo definition** | `topo.yaml` | Network structure, links, node types | 66 |
| **Node startup** | `startup.sh` | Node type detection, script dispatching | 115 |
| **Common functions** | `common.sh` | Shared networking utilities, helpers | 374 |
| **Router daemon** | `demone_router/main.py` | Daemon entry, handler registration | 37 |
| **Daemon class** | `demone_reader.py` | RabbitMQ connection, message loop | 94 |
| **Message handlers** | `demone_router/handlers.py` | encap/decap/rollback implementations | 171 |
| **Validator impl** | `demone_router/validator_handler.py` | Packet-based tunnel validation | 83 |
| **Planner agent** | `agent_ai/planner_agent.py` | High-level orchestration logic | 146 |
| **Executor agent** | `agent_ai/executor_agent.py` | Transaction-based routing config | 191 |
| **State model** | `agent_ai/state.py` | Topology parsing, path computation | 112 |
| **Transaction store** | `agent_ai/transactionDB.py` | Transaction lifecycle management | 38 |
| **Message broker** | `agent_ai/messagging.py` | RabbitMQ abstraction, correlation | 94 |
| **Schema validation** | `agent_ai/validation.py` | JSON schema for encap/decap | 76 |
| **Agent tools** | `agent_ai/tools.py` | Tool definitions for agents | 212 |
| **Router configs** | `configs/*.conf` | Static routes for network init | 6-7 each |

---

## Summary

This codebase implements a **benchmarking playground** for agentic AI in network management, featuring:

1. **Controlled environment:** Static 17-node SRv6 topology with reproducible addressing
2. **Agent infrastructure:** Planner and Executor agents with tool-based infrastructure access
3. **Message-based control:** RabbitMQ topic exchange with structured JSON protocol
4. **Transaction model:** In-memory transaction store with automatic rollback
5. **Validation layer:** Active packet-based tunnel testing
6. **Observability:** Transaction IDs, message correlation, logging hooks

**Design principles demonstrated:**
- Structured declarative messages over arbitrary shell commands
- Separation between high-level reasoning and deterministic execution
- Explicit state, acknowledgements, and telemetry
- Node-local reconciler/executor model over unconstrained direct control
- Validation and rollback as first-class operations
- Safety and auditability built into the protocol

**Limitations acknowledged:**
- Single-request-at-a-time processing (no concurrency)
- In-memory state (no persistence)
- Static topology (no dynamic failures)
- Prototype implementation issues (hard-coded values, partial validation)

**Future work enabled:**
- Concurrent transaction handling
- Persistent state for recovery
- Fault injection framework
- Multi-agent comparison harness
- Metrics collection and KPI dashboards

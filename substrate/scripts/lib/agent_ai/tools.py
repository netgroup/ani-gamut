from datapizza.tools import tool
import json
from state import NetworkTopology as NetworkState
from messagging import RabbitBroker, MessageSender
from transactionDB import dbTransaction

state = NetworkState("/opt/conf/topo.yaml")
broker = RabbitBroker()
sender = MessageSender(broker)
db = dbTransaction()

# --- Stato della rete ---
@tool
def list_hosts():
    hosts = [n for n,v in state.node_map.items() if v["type"] == "host"]
    return json.dumps(hosts,indent=2)
@tool
def vrf_host(host:str):
    node = state.node_map.get(host,"")
    if node =="":
        return json.dumps({"error":"Host not exist"},indent=2)
    if node["type"] != "host":
        return json.dumps({"error":"node is not a host"},indent=2)
    return json.dumps({"vrf":node["ipv4"]["vrf"]},indent=2)
@tool
def list_routers():
    routers = [n for n,v in state.node_map.items() if v["type"] == "router"]
    return json.dumps(routers,indent=2)
@tool
def get_router_sid(router: str):
    if state.node_map[router]["type"] != "router":
        return json.dumps({"errore":router+" is not a router"},indent=2)
    return json.dumps({"sid":state.node_map[router]["ipv6"]["sid"]},indent=2)
@tool
def get_neighbors(node: str):
    return state.get_neighbors(node)
@tool
def get_interface_to_neighbor(node: str, neighbor: str):
    node_info = state.node_map[node]

    for intf, peer in node_info["interfaces"].items():
        if peer == neighbor:
            return intf
    return None
@tool
def get_ipv6_to_neighbor(router: str, neighbor: str):
    node = state.node_map[router]
    for intf, peer in node["interfaces"].items():
        if peer == neighbor:
            return node["ipv6"].get(intf)
    return None

@tool
def get_sid_for_host(sid: str, host: str):
    if state.node_map[host]["type"] == "host":
        for intf, peer in state.node_map[host]["interfaces"].items():
            if state.node_map[peer]["ipv6"]["sid"] == sid:
                rid = int("".join(c for c in peer if c.isdigit()))
                hs_num = int(host[2:])
                # End.DT4 uSID (F3216, LIB Set 0xf4): 5f00:0:<egress router>:f4<host>::
                return json.dumps({"sid": f"5f00:0:{rid:x}:f4{hs_num:02x}::"},indent=2)
        return  json.dumps({"errore":"sid non esistente"},indent=2)
    return json.dumps({"errore":"non è un host"},indent=2)
@tool
def get_host_ipv4(host: str):
    node = state.node_map[host]
    return list(node["ipv4"].values())[0]

@tool
def get_router_info(router: str):
    if router not in state.node_map:
        return json.dumps({"error": "router not found"}, indent=2)
    return json.dumps(state.node_map[router], indent=2)

@tool
def compute_route(src: str, dst: str):
    path = state.shortest_path(src, dst)
    return json.dumps({"path": path, "segments": path[1:-1]}, indent=2)

@tool
def update_router_metadata(router: str, field: str, value: str):
    return json.dumps({"status": "router updated"}, indent=2)

# --- Invio messaggi SRv6 generati dall'agente ---
@tool
def send_message(router: str, message: dict):
    """
    L'agente genera direttamente il messaggio JSON, qui viene solo inviato.
    """
    sent_msg = sender.send(router, message)
    return json.dumps({"status": "message sent", "status": sent_msg}, indent=2)

# --- upate transaction --- 
@tool
def create_transaction( src_host: str, dst_host: str, path: list, encap_info: dict,
decap_info: dict) -> str:
    """
    Salva la transazione.
    encap_info:
        - router
        - interface
        - sid
        - ip
        - vrf

    decap_info:
        - router
        - interface
        - sid
        - ip
        - vrf
    """
    id= db.newTransaction(src_host,dst_host,path,encap_info,decap_info)
    return json.dumps({"transaction_id":id}, indent=2)
@tool
def wait_transaction_result(message_ids: list) -> dict:
    """
    Blocca finché la transazione termina.
    Returns:
    {
        "status": "success" | "error"
    }
    """ 
    if not sender.wait_ack(message_ids):
        return json.dumps({"status":"error"}, indent=2)
    return json.dumps({"status":"success"}, indent=2)

@tool
def rollback_transaction(transaction_id: int) -> dict:
    """
    Esegue rollback completo.

    Returns:
    {
        "status": "success" | "failed"
    }
    """
    element = db.get_transaction(transaction_id)#prendo la transazione

    if element.get("error","") != "": #se la transazione mi ritorna errore lo propago all'agente
        return json.dumps(element, indent=2)
    id_msg1= db.get_messageID()
    id_msg2= db.get_messageID()
    message_encap={
        "msg_id":id_msg1,
        "type":"encap_rollback",
        "ip":element["encap"]["ip"],
        "vrf":element["encap"]["vrf"],
        "dev":element["encap"]["interface"]
    }
    message_decap={
        "msg_id":id_msg2,
        "type":"decap_rollback",
        "sid":element["decap"]["sid"],
        "vrf":element["decap"]["vrf"]
    }
    r1_message=send_message(element["path"][1],message_encap)
    r2_message=send_message(element["path"][-2],message_decap)
    if not sender.wait_ack([id_msg1,id_msg2]):
        return json.dumps({"status":"error"}, indent=2)
    return json.dumps({"status":"success"}, indent=2)
@tool
def get_transaction(transaction_id: int) -> dict:
    """
    Ritorna la transazione se esiste, altrimenti None
    """
    element = db.get_transaction(transaction_id)
    return json.dumps(element,indent=2)

@tool
def get_messageID() -> int:
    """
    Ritorna la transazione se esiste, altrimenti None
    """
    id = db.get_messageID()
    return json.dumps({"msg_id":id},indent=2)


#----------------------------convalid tool----------------------------------------
@tool
def convalid_tool(path: list) -> dict:
    """
    Verifica che il tunnel SRv6 sia stato realmente configurato.

    Returns:
    {
        "status": "true" | "false"
    }
    """
    #qui devo mettere la logica per il ping tra i router di bordo
    r1=path[1]
    r2=path[2]
    src=path[0]
    dst=path[-1]
    ip_src = get_host_ipv4(src).split("/")[0]
    ip_dst = get_host_ipv4(dst).split("/")[0]
    sid1=state.node_map[r1]["ipv6"]["sid"]
    sid2=state.node_map[r2]["ipv6"]["sid"]
    sid = json.loads(get_sid_for_host(sid2,dst)).get("sid")
    my_sid = json.loads(get_sid_for_host(sid1,src)).get("sid")

    msg_id=db.get_messageID()
    msg={
        "msg_id":msg_id,
        "type":"validate",
        "ip_src":ip_src,
        "ip_dst":ip_dst,
        "iface_next_hope":r1+"-"+r2,
        "sid":sid,
        "my_sid":my_sid,
    }
    send_message(r1,msg)
    r=wait_transaction_result([msg_id])
    return r

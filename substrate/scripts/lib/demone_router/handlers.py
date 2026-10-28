from pyroute2 import IPRoute, NetlinkError
import socket
import subprocess

def route_exists(sid, tab):
    result = subprocess.run(
        ["ip", "-6", "route", "show"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    return sid in result.stdout


def _vrf_table_from_name(vrf: str) -> int:
    if not vrf.startswith("vrf"):
        raise ValueError(f"VRF name '{vrf}' non nel formato 'vrf<N>'")
    return int(vrf[3:])

def srv6_encap_route(ip_host, sid_routers, interface,vrf):
    """
    ip route add table <tab> <ip_host> encap seg6 mode encap segs <sid_router> dev <interface>
    """
    table_id = _vrf_table_from_name(vrf)  # funzione tua per ottenere l'ID della tabella VRF
    try:
        result = subprocess.run(
            ["ip", "route", "add","table",str(table_id),
             ip_host,"encap","seg6","mode","encap","segs",sid_routers,"dev",interface],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status":"ok"}
        else:
            stderr = result.stderr.lower()
            if "file exists" in stderr:
                return {"status":"ok"}
            return {"status":"error","message":stderr}
    except subprocess.CalledProcessError as e:
        print(e)
        print("stderr:", result.stderr)
        return {"status":"error","message":result.stderr}

def srv6_decap_route(sid,vrf):
    """
    ip -6 route add <sid> encap seg6local action End.DT4 vrftable <tab> dev <interface>
    """
    table_id = _vrf_table_from_name(vrf)  # funzione tua per ottenere l'ID della tabella VRF
    try:
        ret=route_exists(sid.split("/")[0],table_id)
        if ret:
            return {"status":"ok"}
        result = subprocess.run(
                ["ip", "-6", "route", "add",sid.split("/")[0]+"/128",
                "encap","seg6local","action","End.DT4","vrftable",str(table_id),"dev",vrf],
                capture_output=True,
                text=True
            )
        if result.returncode == 0:
            return {"status":"ok"}
        else:
            stderr = result.stderr.lower()
            if "file exists" in stderr:
                return {"status":"ok"}
            return {"status":"error","message":stderr}
    except subprocess.CalledProcessError as e:
        print(e)
        print("stderr:", result.stderr)
        return {"status":"error","message":result.stderr}

def srv6_del_encap_route(ip, vrf, dev):
    """
    Rimuove una rotta SRv6 in modalità encap.
    
    Esempio shell:
    ip route add table 101 10.0.5.0/24 encap seg6 mode encap segs fcf0:2::5 dev pe1-pe2
    """
    table_id = _vrf_table_from_name(vrf)  # funzione tua per ottenere l'ID della tabella VRF
    try:
        result = subprocess.run(
            ["ip", "route", "del",ip.split("/")[0],"table",str(table_id),"dev", dev],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status":"ok"}
        else:
            stderr = result.stderr.lower()
            if "no such process" in stderr:
                return {"status":"ok"}
            return {"status":"error","message":stderr}
    except subprocess.CalledProcessError as e:
        print(e)
        print("stderr:", result.stderr)
        return {"status":"error","message":result.stderr}

def srv6_del_decap_route(sid, vrf):
    """
    Rimuove una rotta SRv6 End.DT4 per un determinato VRF.
    
    ip -6 route add <sid> encap seg6local action End.DT4 vrftable <tab> dev <interface>
    """
    table_id = _vrf_table_from_name(vrf)  # funzione tua per ottenere l'ID della tabella VRF
    try:
        result = subprocess.run(
            [
                "ip", "-6", "route", "del",sid,
                "encap", "seg6local","action", "End.DT4",
                "vrftable", str(table_id),
                "dev", vrf
            ],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status":"ok"}
        else:
            stderr = result.stderr.lower()
            if "no such process" in stderr:
                return {"status":"ok"}
            return {"status":"error","message":stderr}
    except subprocess.CalledProcessError as e:
        print(e)
        print("stderr:", result.stderr)
        return {"status":"error","message":result.stderr}

def handle_decap(message):
    print("Executing BORDER handler")
    decap = message.get("decap")
    if decap != None:
        sid = decap.get("sid")
        vrf = decap.get("vrf")
        if vrf != None and sid != None:   
            r=srv6_decap_route(sid,vrf)
            print(f"Configure decap {decap}")   
            return r
    return {"status":"error","message":"bad format"}
def handle_encap(message):
    encap = message.get("encap")
    if encap != None:
        ip = encap.get("ip")
        sid = encap.get("sid")
        iface = encap.get("interface")
        vrf = encap.get("vrf")
        if ip !=None and sid !=None and iface !=None and vrf !=None:
            r=srv6_encap_route(ip,sid,iface,vrf)
            print(f"Configure SRv6 encap {encap}")
            return r
    print(f"Error: messsage:{message} non ha ne decap ne encap")
    return {"status":"error","message":"bad format"}

def handle_encap_rollback(message):
    print("Executing encap rollback handler")
    ip = message.get("ip")
    vrf = message.get("vrf")
    dev = message.get("dev")
    if ip != None and vrf != None and dev != None:
        print(ip,vrf,dev)
        r=srv6_del_encap_route(ip,vrf,dev)
        return r
    print(f"Error: messsage:{message} non ha ne decap ne encap")
    return {"status":"error","message":"bad format"}
def handle_decap_rollback(message):
    print("Executing denap rollback handler")
    sid = message.get("sid")
    vrf = message.get("vrf")
    if sid != None and vrf != None:
        r=srv6_del_decap_route(sid,vrf)
        return r
    print(f"Error: messsage:{message} non ha ne decap ne encap")
    return {"status":"error","message":"bad format"}
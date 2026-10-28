import threading
import time
from scapy.all import *
from scapy.layers.inet import IP, ICMP
from scapy.layers.inet6 import IPv6, IPv6ExtHdrSegmentRouting

# ================= CONFIG ====================
iface_send = "pe1-hs1"     # interfaccia di invio
#iface_sniff = "pe1-pe2"    # interfaccia per sniff
h1_ip = "10.0.1.1"
h2_ip = "10.0.5.1"

sid_list = ["fcf0:2::5"]
#outer_dst = sid_list[0]
expected_sid = "fcf0:1::1"
reply_received = False
# Variabile condivisa tra thread
def validator_schema(ip_src,ip_dst,iface_recv,sid,my_sid):
    global reply_received
    reply_received = False
    def check_srv6_reply(p):
        global reply_received
        if IPv6 in p:
            p.show()
            ipv6 = p[IPv6]
            # destinazione corretta
            if ipv6.dst != my_sid:
                return False
            # deve avere SRH
            if not p.haslayer(IPv6ExtHdrSegmentRouting):
                return False
            # deve avere inner IPv4
            if not p.haslayer(IP):
                return False
            ip = p[IP]
            if ip.src != ip_dst or ip.dst != ip_src:
                return False
            # ICMP reply
            if not p.haslayer(ICMP):
                return False
            icmp = p[ICMP]
            if icmp.type == 0 and icmp.id == 1234:
                print("[+] SRv6 reply corretto ricevuto!")
                reply_received = True
                return True
        return False
    # Thread per sniff
    def sniff_thread():
        sniff(
            iface=iface_recv,
            filter="ip6",
            store=False,
            prn=check_srv6_reply,
            timeout=10  # sniff massimo 10 secondi
        )

    thread = threading.Thread(target=sniff_thread)
    thread.start()
    time.sleep(0.5)
    inner_pkt = IP(src=ip_src, dst=ip_dst) / ICMP(id=1234, seq=1)
    srh = IPv6ExtHdrSegmentRouting(addresses=[sid])
    pkt = IPv6(dst=sid) / srh / inner_pkt
    print("[*] Sending SRv6 encapsulated ping...")
    send(pkt, verbose=False)
    thread.join(timeout=10)
    if reply_received:
        print("[SUCCESS] Tunnel funzionante (andata + ritorno OK)")
        return {"status":"ok"}
    else:
        print("[FAIL] Nessuna risposta ricevuta")
        return {"status":"error","message":"not packet send"}

def validator_handler(msg):
    ip_src = msg.get("ip_src")
    ip_dst = msg.get("ip_dst")
    iface_recv = msg.get("iface_next_hope")
    sid = msg.get("sid")
    my_sid = msg.get("my_sid") 
    if ip_src!= None and ip_dst !=None and iface_recv!=None and sid!=None and my_sid!=None:
        r=validator_schema(ip_src,ip_dst,iface_recv,sid,my_sid)
        print(r)
        return r
    return {"status":"error","message":"bad format"}

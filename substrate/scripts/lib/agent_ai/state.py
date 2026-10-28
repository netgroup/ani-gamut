import yaml
import networkx as nx

class NetworkTopology:
    def __init__(self, file_path):
        self.node_map = {}
        self.graph = nx.Graph()
        self._build_map(file_path)

    def _build_map(self, file_path):
        with open(file_path) as f:
            topology = yaml.safe_load(f)
        
        nodes_yaml = topology['topology']['nodes']
        links_yaml = topology['topology']['links']

        # Costruzione nodi
        for n in nodes_yaml:
            kind = 'host' if n.startswith('hs') else 'router'
            self.node_map[n] = {'type': kind, 'interfaces': {}, 'ipv4': {}, 'ipv6': {}}
            self.graph.add_node(n, type=kind)

        # Lista dei router
        router_types = ['pe', 'igw', 'egw']
        router_nodes = sorted([n for n in self.node_map if any(n.startswith(t) for t in router_types)])

        # Elaborazione dei link
        for link in links_yaml:
            ep1, ep2 = link['endpoints']
            node1, intf1 = ep1.split(':')
            node2, intf2 = ep2.split(':')

            # Salvo interfacce
            self.node_map[node1]['interfaces'][intf1] = node2
            self.node_map[node2]['interfaces'][intf2] = node1

            # IPv4 tra HS e router
            if self.node_map[node1]['type'] == 'host' and self.node_map[node2]['type'] == 'router':
                hs_num = int(node1[2:])
                self.node_map[node1]['ipv4'][intf1] = f"10.0.{hs_num}.1/32"
                self.node_map[node1]['ipv4']["vrf"] = "vrf"+str(100+hs_num)
                self.node_map[node2]['ipv4'][intf2] = f"10.0.{hs_num}.254"
            elif self.node_map[node2]['type'] == 'host' and self.node_map[node1]['type'] == 'router':
                hs_num = int(node2[2:])
                self.node_map[node2]['ipv4'][intf2] = f"10.0.{hs_num}.1/32"
                self.node_map[node1]['ipv4'][intf1] = f"10.0.{hs_num}.254"
                self.node_map[node2]['ipv4']["vrf"] = "vrf"+str(100+hs_num)
            # IPv6 tra router
            if self.node_map[node1]['type'] == 'router' and self.node_map[node2]['type'] == 'router':
                num1 = int(''.join(filter(str.isdigit, node1)))
                num2 = int(''.join(filter(str.isdigit, node2)))
                min_r, max_r = min(num1, num2), max(num1, num2)
                self.node_map[node1]['ipv6'][intf1] = f"fcf0:0:{min_r}:{max_r}::{num1}/64"
                self.node_map[node2]['ipv6'][intf2] = f"fcf0:0:{min_r}:{max_r}::{num2}/64"

            # Aggiungo arco al grafo
            self.graph.add_edge(node1, node2)

        # SID ai router
        for r in router_nodes:
            num = int(''.join(filter(str.isdigit, r)))
            # F3216 / NEXT-CSID uSID locator: Block 5f00:0000, Set 0x00, Node = hex(id)
            self.node_map[r]['ipv6']['sid'] = f"5f00:0:{num:x}::/48"

    # --- Metodi pubblici ---
    def print_map(self):
        for node, info in self.node_map.items():
            print(f"Node: {node} ({info['type']})")
            for intf, peer in info['interfaces'].items():
                ipv4 = info['ipv4'].get(intf, '-')
                ipv6 = info['ipv6'].get(intf, '-')
                vrf = info['ipv4'].get("vrf","-")
                print(f"  Interface {intf} -> {peer} | IPv4: {ipv4} on vrf {vrf} | IPv6: {ipv6}")
            if 'sid' in info['ipv6']:
                print(f"  SID: {info['ipv6']['sid']}")
            print()

    def update_sid(self, router, new_sid):
        if router in self.node_map and self.node_map[router]['type'] == 'router':
            self.node_map[router]['ipv6']['sid'] = new_sid
        else:
            raise ValueError(f"{router} is not a router")

    def get_neighbors(self, node):
        if node not in self.node_map:
            raise ValueError(f"{node} not in network")
        return list(self.graph.neighbors(node))

    def shortest_path(self, node1, node2):
        if node1 not in self.node_map or node2 not in self.node_map:
            raise ValueError("Nodes must exist in the network")
        try:
            path = nx.shortest_path(self.graph, source=node1, target=node2)
            return path
        except nx.NetworkXNoPath:
            return None
    def get_border_routers(self, src_host, dst_host):
        path = self.shortest_path(src_host, dst_host)
        if not path or len(path) < 3:
            raise ValueError("Path troppo corto o non esistente")
        return path[1], path[-2]  # primo e ultimo router della catena
    def get_intermediate_routers(self, src_host, dst_host):
        path = self.shortest_path(src_host, dst_host)
        if len(path) <= 3:
            return []
        return path[2:-2]  # router intermedi tra frontiere

if __name__ =="__main__":    
    # Creazione topologia
    net = NetworkTopology("../../../topo.yaml")

    # Stampare la mappa
    net.print_map()

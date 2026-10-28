FROM ubuntu:24.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        kmod \
        iproute2 \
        iputils-ping \
        net-tools \
        iperf3 \
        traceroute \
        tcpdump \
        termshark \
        vim \
        less \
        ca-certificates \
        nftables \
        iptables \
        haproxy \
        frr \
        frr-pythontools \
        python3 \
        python3-pip \
        python3-venv && \
	apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m venv .venv
RUN .venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/.venv/bin:$PATH"
RUN echo "source /.venv/bin/activate" >> /root/.bashrc
 
CMD ["/usr/bin/bash"]

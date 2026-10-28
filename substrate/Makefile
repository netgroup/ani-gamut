# SRv6 Data Center Network Simulation
# Copyright (C) 2026 Andrea Mayer
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# See <https://www.gnu.org/licenses/gpl-3.0.html>

# Makefile
# ========

# Configuration (change only these values if needed)
IMAGE_NAME    := ubuntu-node
IMAGE_TAG     := latest
DOCKERFILE    := Dockerfile
BUILD_CTX     := .
TOPO_FILE     := topo.yaml
TOPO_NAME     := $(shell yq -r '.name' "$(TOPO_FILE)")
IMAGE_FULL    := $(IMAGE_NAME):$(IMAGE_TAG)

# Verbosity handling
#   VERBOSE=1  -> commands are printed
#   (default)  -> commands are silent (prefixed with @)
ifeq ($(VERBOSE),)
  CMD         := @
else
  CMD         :=
endif

.PHONY: all help docker deploy destroy connect

all: help

help:
	@echo "Available targets (run with \`make <target>\`):"
	@echo ""
	@echo "docker"
	@echo "  Build the Docker image $(IMAGE_FULL)."
	@echo "  Run with: make docker"
	@echo ""
	@echo "deploy"
	@echo "  Verify that the kernel modules vrf and dummy are present and"
	@echo "  start the Containerlab testbed."
	@echo "  Run with: make deploy"
	@echo ""
	@echo "destroy"
	@echo "  Remove the Containerlab testbed created by \`make deploy\`."
	@echo "  Run with: make destroy"
	@echo ""
	@echo "connect NODE=<node>"
	@echo "  Connect to a specific node in the testbed via docker exec."
	@echo "  Run with: make connect NODE=<node>"
	@echo "  Example: make connect NODE=hs1"
	@echo ""
	@exit 0

# docker - build the Docker image $(IMAGE_FULL)
docker: $(DOCKERFILE)
	$(CMD)echo "Building Docker image $(IMAGE_FULL) ..."
	$(CMD)docker build -f "$(DOCKERFILE)" -t "$(IMAGE_FULL)" "$(BUILD_CTX)"

# deploy - check kernel modules and start the Containerlab testbed
deploy: $(TOPO_FILE)
	$(CMD){ \
	      if [ $$(id -u) != 0 ]; then \
		    echo "ERROR: Run with 'sudo make deploy'" >&2; \
		    exit 1; \
	      fi ; \
	      command -v containerlab >/dev/null || { echo 'ERROR: Containerlab not installed' >&2; exit 1; } ;\
	      command -v yq >/dev/null || { echo 'ERROR: yq not installed' >&2; exit 1; } ;\
	      if ! echo "$(TOPO_FILE)" | grep -qE '^[a-zA-Z0-9_.-]+$$'; then \
		    echo "ERROR: Invalid TOPO_FILE '$(TOPO_FILE)'. Must contain only alphanumeric, _, -, ." >&2; \
		    exit 1; \
	      fi ;\
	      missing=""; \
	      dummy_name="dummy-$$RANDOM-$$RANDOM" ; \
	      if ! ip link add name "$$dummy_name" type dummy >/dev/null 2>&1; then \
		    missing="dummy"; \
	      else \
		    ip link del "$$dummy_name" &>/dev/null ; \
	      fi ; \
	      vrf_name="vrf-$$RANDOM-$$RANDOM" ; \
	      if ! ip link add name "$$vrf_name" type vrf table 100 >/dev/null 2>&1; then \
		    if [ "$${missing}" = "" ]; then missing="vrf"; else missing="$${missing}, vrf"; fi ; \
	      else \
		    ip link del "$$vrf_name" &>/dev/null ;\
	      fi; \
	      if [ -n "$${missing}" ]; then \
		    echo "ERROR: required kernel interfaces not available: $${missing}" >&2; exit 1; \
	      fi ; \
	      echo "Deploying Containerlab testbed using $(TOPO_FILE) ..." >&2; \
	      containerlab deploy -t "$(TOPO_FILE)" ; \
	}

# destroy - remove the Container‑lab testbed
destroy: $(TOPO_FILE)
	$(CMD){ \
	      if ! echo "$(TOPO_FILE)" | grep -qE '^[a-zA-Z0-9_.-]+$$'; then \
		    echo "ERROR: Invalid TOPO_FILE '$(TOPO_FILE)'. Must contain only alphanumeric, _, -, ." >&2; \
		    exit 1; \
	      fi ;\
	      echo "Destroying Container‑lab testbed defined in $(TOPO_FILE) ..." >&2; \
	      containerlab destroy -t "$(TOPO_FILE)" ; \
	}

# connect - connect to a node in the testbed via docker exec
connect:
	$(CMD){ \
	      NODE_NAME="$(NODE)"; \
	      if [ -z "$$NODE_NAME" ]; then \
		    echo "ERROR: Missing NODE parameter. Usage: make connect NODE=<node>" >&2; \
		    exit 1; \
	      fi; \
	      if ! echo "$$NODE_NAME" | grep -qE '^[a-zA-Z0-9_-]+$$'; then \
		    echo "ERROR: Invalid NODE '$$NODE_NAME'. Must match regex: ^[a-zA-Z0-9_-]+$$" >&2; \
		    exit 1; \
	      fi; \
	      if ! echo "$(TOPO_NAME)" | grep -qE '^[a-zA-Z0-9_-]+$$'; then \
		    echo "ERROR: Invalid TOPO_NAME '$(TOPO_NAME)' from topology file. Must match regex: ^[a-zA-Z0-9_-]+$$" >&2; \
		    exit 1; \
	      fi; \
	      CONTAINER_NAME="clab-$(TOPO_NAME)-$$NODE_NAME"; \
	      if ! docker inspect "$$CONTAINER_NAME" > /dev/null 2>&1; then \
		    echo "ERROR: Container '$$CONTAINER_NAME' does not exist. Run 'make deploy' first." >&2; \
		    exit 1; \
	      fi; \
	      echo "Connecting to node $$NODE_NAME ..."; \
	      docker exec -it "$$CONTAINER_NAME" bash; \
	}

# AGENTS.md

## Build/Lint/Test Commands

This project is a Bash-based network simulation using Containerlab. There are no automated tests or linters configured.

**Build Commands:**
- Build Docker image: `make docker` or `docker build -f Dockerfile -t ubuntu-node:latest .`
- Deploy testbed: `make deploy`
- Destroy testbed: `make destroy`
- Show help: `make help`

**Run Single Test:**
- No automated tests exist; manual testing via CLI commands:
  - `docker exec -it clab-sr-4hs-2lf-2sp-demo-hs1 bash`
  - Test connectivity: `ip -6 ping fdf0:0:2::2`
  - Check routes: `ip -6 route show`

## Code Style

### Makefile Guidelines

#### Imports/Dependencies
- Makefile uses standard GNU Make conventions
- All dependencies must be checked before use (e.g., `command -v yq >/dev/null || exit 1`)

#### Formatting
- Recipe command lines: **MUST use TAB characters** (Make requirement, not spaces)
- Shell commands inside recipe blocks: 6-space indentation per AGENTS.md guidelines
- Variable assignments: Column-aligned for readability:
  - Left-align all variable names
  - Use spaces to vertically align the `:=` operator (typically at column 16)
  - Values begin immediately after the aligned `:=`, with no leading space
- Line continuation: Use `\` for multi-line commands
- Line length: prefer < 80 characters where possible

#### Naming Conventions
- **Configuration variables**: `UPPER_SNAKE_CASE` (e.g., `TOPO_FILE`, `IMAGE_NAME`, `NODE_NAME`)
- **Recipe targets**: lowercase with hyphens (e.g., `deploy`, `destroy`, `connect`)

#### Types
- Variables: No explicit type declarations in Make
- Shell variables inside recipes: Use `$$VAR` syntax for shell variable expansion

### Makefile vs Linux Kernel Comparison

#### Indentation
- **Make requirement**: Recipe commands MUST use TAB characters (GNU Make requirement)
- **Shell commands inside blocks**: 6-space indentation (project standard, more readable than kernel's 8-space)

#### Naming
- Current project uses `UPPER_SNAKE_CASE` for variables (project convention)
- Linux kernel uses mixed styles (lowercase/common abbreviations in scripts)

**Verdict**: Current project conventions are appropriate and more consistent than Linux kernel approaches.

### Makefile Formatting Examples

Column-aligned variable assignments improve readability:

```makefile
IMAGE_NAME    := ubuntu-node
IMAGE_TAG     := latest
DOCKERFILE    := Dockerfile
BUILD_CTX     := .
TOPO_FILE     := topo.yaml
TOPO_NAME     := $(shell yq -r '.name' "$(TOPO_FILE)")
IMAGE_FULL    := $(IMAGE_NAME):$(IMAGE_TAG)
```

- `:=` operator aligned in column for easy scanning
- Variable names left-aligned, padded with spaces as needed
- Values start immediately after `:=` without leading spaces

### Bash Guidelines

#### Imports/Dependencies
- Library files sourced via `startup.sh` which sets `__STARTUP_GUARD` sentinel
- Guard pattern: `: "${__STARTUP_GUARD:?Error: This file must be sourced via startup.sh}"`
- All dependencies: `iproute2`, `net-tools`, `iperf3`, `traceroute`, `tcpdump`, `termshark`, `vim`, `less`

#### Formatting
- 6-space indentation (spaces only, no tabs)
- Blank lines between logical sections
- Use `\` for line continuation
- Line length: prefer < 80 characters where possible

#### Naming Conventions
- **Constants/readonly**: `UPPER_SNAKE_CASE` (e.g., `SCRIPT_DIR`, `NODEID`, `CSID_BLOCK_NET`)
- **Local variables**: `lowercase_with_underscores` (e.g., `conf_file`, `neigh_name`, `iface`)
- **Global variables**: `UPPER_SNAKE_CASE` (e.g., `POLICIES`, `NEIGH_NODES`, `GLOBAL_POLICIES`, `IF_IPV6_NET`)
- **Functions**: `snake_case` verbs (e.g., `build_usid`, `add_policy_seg6_routes`, `wait_for_iface`, `find_neigh_nodes`)
- **Regex patterns**: `UPPER_SNAKE_CASE` suffixed with `REGPR` (e.g., `NODE_REGEXPR`, `LINK_REGEXPR`)

#### Node Type Detection

The `startup.sh` script detects node type from hostname using regex pattern:
```bash
NODE_REGEXPR="(hs|pe|igw|egw)([0-9]+)"
```

Node types and their prefixes:
- `hs` - Host nodes (e.g., `hs1`, `hs2`) - end hosts
- `pe` - Provider Edge nodes (e.g., `pe1`, `pe2`) - require config files  
- `igw` - Internet Gateway nodes (e.g., `igw1`)
- `egw` - Edge Gateway nodes (e.g., `egw1`)

Special `master` hostname triggers agent startup commands in `.bashrc`.

#### Types
- No explicit type declarations in Bash
- Use `readonly` for immutable variables
- Use `declare -A` for associative arrays
- Use `declare -a` for indexed arrays
- Local variables declared with `local` inside functions

### Bash vs Linux Kernel Comparison

The Linux kernel uses a different approach for bash scripting. Comparison:

| Convention | Linux Kernel | Current Project | Rationale |
|------------|--------------|-----------------|----------|
| **Indentation** | 8-space tabs | **6-space spaces** | 6-space more readable for nested structures |
| **Shebang** | `#!/bin/bash` | `#!/usr/bin/env bash` | More portable across different systems |
| **Strict mode** | Not used | `set -euo pipefail` | Ensures safer script execution |
| **Variable naming** | `tmp`, `i`, `j` | Descriptive `lowercase_with_underscore` | Improves code readability |
| **Exit codes** | 0/1 (non-zero) | 0/1/2 (specialized) | Better debugging with specific codes |

**Verdict**: Current project conventions are **superior** for maintainability and error prevention.

### Error Handling

- Strict mode in executable scripts: `set -euo pipefail`
  - `-e`: Exit on error
  - `-u`: Error on undefined variables
  - `-o pipefail`: Propagate errors in pipelines
- Error messages to stderr: `echo "ERROR: ..." >&2`
- Explicit exit codes: `exit 1` for general errors, `exit 2` for invalid arguments
- Optional error suppression: `|| true` or `|| :` when errors are acceptable
- Always capture exit codes: `command || { echo "failed"; exit 1; }`

### Documentation Standards

- **Header blocks**: Copyright/license at top of each file
- **Function documentation**: Plain-text comments above function definitions describing:
  - Purpose
  - Parameters
  - Return values/exit codes
- **Inline comments**: Sparingly used for complex logic
- **Guard documentation**: Extensive comments explaining sentinel patterns (e.g., `__STARTUP_GUARD`)
- **README**: Comprehensive documentation in `/README.md`
- **Commit Messages**: Adhere to Linux kernel conventions:
  - Title ≤50 chars with subsystem prefix, e.g. "Makefile:"
  - Body wrapped at 72 characters; explain why changes were made
  - Include `Fixes: <commit-hash> ("title")` for bug fixes
  - Mandatory `Signed-off-by: Name <email>` line (preceded by blank line)

### Agent Best Practices

1. **Before modifying**: Read existing files to match conventions
2. **Use `startup.sh`**: As the single entry point to source other scripts
3. **Respect the guard pattern**: Never remove or modify `__STARTUP_GUARD` logic
4. **Use snake_case**: For all function and variable names
5. **Read-only early**: Mark immutable variables with `readonly`
6. **Error handling**: Always check exit codes in critical paths
7. **Document SRv6 logic**: Complex routing decisions need comments
8. **Test manually**: Run `make deploy` and verify connectivity after changes
9. **Node-specific configs**: PE nodes load configs from `${CONFIG_DIR}/${hostname}.conf`
10. **Interface naming**: Link interfaces follow `<node1>-<node2>` pattern (e.g., `hs1-pe1`)

### Notes

- Never commit secrets (`.env`, credentials, config files with passwords)
- Prefer environment variables over hardcoded values
- All scripts must be sourced via `startup.sh`, never executed directly
- Image tag: `ubuntu-node:latest` defined in `Makefile`
- Topology file: `topo.yaml` defines 8 nodes (4 hosts, 2 leaves, 2 spines)

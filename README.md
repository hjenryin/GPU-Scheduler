# GPU Scheduler

**Distributed job scheduling across multiple GPU machines with active monitoring**

Version: 0.1.0  
Last Updated: 2025-10-28

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What is GPU Scheduler?

GPU Scheduler is a **lightweight, user-space distributed job scheduler** designed for shared GPU clusters. It enables teams to efficiently share GPU resources without requiring system administrator privileges.

**Key Features:**
- 🚀 **No sudo required** - runs entirely in user space
- 🔄 **Ray-inspired interface** - familiar commands for Ray users
- 📊 **Active GPU monitoring** - real-time utilization tracking
- 🔗 **Multi-node clusters** - coordinate jobs across multiple machines
- 🎯 **Smart scheduling** - considers GPU availability, stability, and grace periods
- 📸 **Automatic snapshots** - git-based workspace snapshots for reproducibility
- 🐍 **Python API** - programmatic job submission and monitoring
- 🖥️ **Interactive TUI** - real-time cluster visualization
- 📡 **HTTP-based** - no SSH required between machines

---

## Overview

GPU Scheduler provides distributed job scheduling across multiple GPU machines with active GPU monitoring. It follows Ray-like patterns and requires **no sudo privileges**.

## Quick Start

**1. Start a cluster:**
```bash
# On head machine
scheduler start --head

# On worker machines
scheduler start --address=head-machine:8265
```

**2. Submit a job:**
```bash
# Python script with arguments
scheduler submit --req 2 python train.py --epochs 100

# Bash script
scheduler submit --req 1 bash run.sh

# Any executable
scheduler submit --req 4 ./my_program --config config.yaml
```

**3. Monitor cluster:**
```bash
scheduler status
```

**4. View job logs:**
```bash
scheduler logs job_abc123
```

**5. Stop cluster:**
```bash
scheduler stop --all
```

**📖 For complete usage instructions, see [API_REFERENCE.md](API_REFERENCE.md)**

---

## Architecture

### Components

- **Head Node**: Central orchestrator managing job queue and node registry
- **Worker Nodes**: GPU machines that execute jobs
- **Client**: CLI, Python API, or HTTP REST API for job submission

### Communication

- **HTTP-based**: Workers poll head node for jobs (long-polling)
- **No SSH**: Direct HTTP communication only
- **Stateless**: Survives network disconnections and reconnections

### File Locations

All files stored in user space (no root required):
- Config: `~/.scheduler/config.yaml`
- Logs: `~/.scheduler/logs/`
- Work directory: `~/.scheduler/work/` (work files and job worktrees)
- Temp files: `~/.scheduler/tmp/`
- Lock files: `~/.scheduler/*.lock`
- Shadow repos: `{workspace}/.scheduler-git/` (per workspace)

### Workspace Mounting

**IMPORTANT**: For the scheduler to work correctly across multiple machines, **the same working directory paths must be accessible on all worker nodes**. This ensures that:

1. **Job snapshots are accessible**: When a job is submitted, a snapshot is created at the workspace root (where `.git` or `.scheduler-git` is found). Worker nodes need access to this location to restore the snapshot.

2. **File paths are consistent**: Scripts and data files referenced by jobs must have the same paths across all machines.

**Recommended Setup:**

- Use a shared network file system (NFS, Lustre, etc.) mounted at the same path on all machines
- Example: `/shared/users/username/` mounted identically on all worker nodes
- Alternative: Use rsync or similar tools to keep workspaces synchronized

**Example Configuration:**
```bash
# On all machines, ensure the same path exists
# Machine 1 (head + worker):
cd /shared/users/alice/myproject
scheduler submit python train.py

# Machine 2 (worker):
# /shared/users/alice/myproject must exist and be accessible
```

Without this setup, jobs may fail to restore snapshots or access required files on worker nodes.

---

## Design Philosophy

### 1. Ray-Inspired Interface
Familiar CLI patterns for Ray users:
- `scheduler start --head` / `scheduler start --address=...`
- Simple, consistent command structure
- Automatic node discovery

### 2. Active GPU Monitoring
- Real-time GPU utilization polling via `nvidia-smi`
- Designed for **shared GPU environments**
- Works alongside jobs from other users
- Cannot enforce isolation, but intelligently schedules around active usage

### 3. Robust Scheduling
- **Stability Detection**: GPUs must stay below threshold for 30s before considered free
- **Grace Periods**: Nodes pause accepting jobs for 120s after a job starts
- **Conservative**: Prevents scheduling conflicts and false positives

### 4. No System Privileges
- No sudo/root required
- No system-level GPU isolation or enforcement
- Uses `CUDA_VISIBLE_DEVICES` for GPU assignment
- All files in `~/.scheduler/` (user space)

### 5. HTTP-Based Communication
- No SSH between machines
- Workers pull jobs (long-polling)
- Survives network disconnections
- Easy to debug with `curl` or browser

---

## Git-Based Workspace Snapshots

The scheduler automatically snapshots your workspace when you submit a job, ensuring the job runs with the exact files that existed at submission time, even if you continue modifying them while the job is pending.

### How It Works

**On Job Submission:**
1. System creates a shadow git repository in your workspace (`.scheduler-git/`)
2. Files are filtered based on size limits and patterns (configurable)
3. Selected files are committed to a job-specific branch
4. Your original files and git state remain untouched

**On Job Execution:**
1. Job executes in an isolated git worktree at `~/.scheduler/work/job-{job_id}/snapshot/`
2. Worktree contains exact files from submission time
3. Multiple jobs can run simultaneously with different file versions
4. After completion, worktree is cleaned up automatically

### Key Benefits

✅ **Zero User Impact** - Your files and git state never modified  
✅ **No File Duplication** - In-place tracking saves disk space  
✅ **Complete Isolation** - Each job runs independently via worktrees  
✅ **Disk Efficient** - Smart filtering + git delta compression  
✅ **Fully Configurable** - Adjust all limits and patterns  
✅ **Works Anywhere** - Not limited to git repositories  

### Configuration

All snapshot settings can be configured in `~/.scheduler/config.yaml`:

```yaml
# Snapshot configuration
snapshot_max_file_size: 1048576  # 1 MB default
snapshot_max_files_per_folder: 1000
snapshot_data_type_limits:
  .npy: 10485760   # 10 MB for numpy arrays
  .pkl: 5242880    # 5 MB for pickle files
  .json: 2097152   # 2 MB for JSON files
snapshot_always_include_extensions: ['.py', '.sh', '.yaml', '.json', '.txt']
snapshot_exclude_patterns: ['__pycache__', '.git', '*.pyc']
```

**Tuning Guidelines:**
- **Small code/config files**: Keep defaults (1 MB) for code and config files
- **Data files**: Set higher limits for data types your workflows commonly use
- **Model checkpoints**: Either exclude from snapshots or store in shared locations
- **Large datasets**: Keep in external storage and reference via absolute paths

**For complete snapshot details, see [GIT_DEV_PLAN.md](GIT_DEV_PLAN.md)**

---

## Important Limitations

⚠️ **CUDA_VISIBLE_DEVICES Compliance**  
Not all frameworks respect `CUDA_VISIBLE_DEVICES`. The scheduler cannot prevent code from using all GPUs at the system level. Users should verify their code respects GPU assignments.

⚠️ **Shared Environment**  
This scheduler monitors but cannot prevent other users from starting jobs outside the system. Grace periods and stability detection help minimize conflicts.

⚠️ **Best Effort Coordination**  
This is a **coordination system**, not an enforcement system. It works well when users cooperate and code respects GPU assignments.

---

## Features

### Command-Line Interface

| Command | Purpose | Details |
|---------|---------|---------|
| `scheduler start` | Start head or worker node | [→ Docs](API_REFERENCE.md#starting-the-scheduler) |
| `scheduler stop` | Stop nodes | [→ Docs](API_REFERENCE.md#stopping-the-scheduler) |
| `scheduler submit` | Submit jobs | [→ Docs](API_REFERENCE.md#job-submission) |
| `scheduler submit-batch` | Submit multiple jobs from file | [→ Docs](API_REFERENCE.md#batch-job-submission) |
| `scheduler status` | Interactive TUI monitor | [→ Docs](API_REFERENCE.md#cluster-status) |
| `scheduler jobs` | List jobs (non-interactive) | [→ Docs](API_REFERENCE.md#scheduler-jobs) |
| `scheduler logs` | View job logs | [→ Docs](API_REFERENCE.md#scheduler-logs) |
| `scheduler cancel` | Cancel jobs | [→ Docs](API_REFERENCE.md#scheduler-cancel) |
| `scheduler freeze` | Freeze GPUs temporarily | [→ Docs](API_REFERENCE.md#gpu-freeze-unfreeze) |
| `scheduler unfreeze` | Unfreeze GPUs | [→ Docs](API_REFERENCE.md#gpu-freeze-unfreeze) |
| `scheduler config` | Manage configuration | [→ Docs](API_REFERENCE.md#configuration) |

### Job Management

- ✅ **Resource requirements**: Flexible GPU allocation (`--req 2` or `--req gpu1:4,gpu2:2`)
- ✅ **Job dependencies**: Chain jobs with `--depends-on`
- ✅ **Priority scheduling**: Higher priority jobs scheduled first
- ✅ **Environment variables**: Pass custom env vars to jobs
- ✅ **Working directory**: Execute jobs in specified directory
- ✅ **Script arguments**: Pass arguments to job scripts
- ✅ **Async by default**: Fire-and-forget submission, use `--block` to wait and stream logs
- ✅ **Log streaming**: Real-time log viewing in block mode with stderr on failure

### GPU Monitoring

- ✅ **Real-time utilization**: GPU % via `nvidia-smi`
- ✅ **Memory tracking**: Used/total memory per GPU
- ✅ **Temperature monitoring**: GPU temperature tracking
- ✅ **Power consumption**: Current power draw per GPU
- ✅ **Stability detection**: Configurable thresholds and stable time
- ✅ **Grace periods**: Prevent over-scheduling during job initialization
- ✅ **GPU freezing**: Temporarily prevent job scheduling on specific GPUs

### Cluster Management

- ✅ **Multi-node support**: Scale across multiple GPU machines
- ✅ **Automatic node discovery**: Workers auto-register with head
- ✅ **Heartbeat monitoring**: Detect disconnected nodes
- ✅ **Job-aware shutdown**: Running jobs marked as untracked, pending jobs cancelled
- ✅ **Port auto-fallback**: Automatically find available ports
- ✅ **Lock file management**: Prevent duplicate instances

### Interactive TUI

- ✅ **Cluster overview**: Nodes, GPUs, jobs at a glance
- ✅ **Node details**: Per-node GPU utilization and status
- ✅ **Job list**: Filter by status (pending/running/completed/failed/cancelled/untracked)
- ✅ **Job details**: Full job information and history
- ✅ **GPU view**: Detailed per-GPU statistics across cluster
- ✅ **Real-time updates**: Auto-refresh every 2 seconds
- ✅ **Keyboard shortcuts**: Navigate with N/J/G/Q keys
- ✅ **Search/filter**: Find jobs and nodes quickly

### Python API

Full programmatic access via Python client:

```python
from scheduler import SchedulerClient

client = SchedulerClient(address="head:8265")

# Submit job
job = client.submit_job(
    script="train.py",
    requirements="2",
    name="my-job"
)

# Monitor
job = client.get_job(job.job_id)
print(f"Status: {job.status}")

# Get logs
logs = client.get_job_logs(job.job_id)
```

**Available Methods:**
- `submit_job()` - Submit jobs
- `get_job()` / `list_jobs()` - Query jobs
- `cancel_job()` - Cancel jobs
- `get_job_logs()` / `stream_job_logs()` - View logs
- `list_nodes()` / `get_node()` - Query nodes
- `freeze_gpu()` / `unfreeze_gpu()` / `unfreeze_all_gpus()` - Manage GPU freezing
- `health_check()` - Check head node status
- `shutdown_cluster()` - Programmatic cluster shutdown

**[→ Complete Python API Reference](API_REFERENCE.md#python-api)**

### HTTP REST API

Direct HTTP access for advanced integration:

```bash
# Submit job
curl -X POST http://head:8265/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"script": "train.py", "requirements": "2"}'

# Get job status
curl http://head:8265/api/v1/jobs/job_abc123

# List nodes
curl http://head:8265/api/v1/nodes
```

**[→ Complete HTTP API Reference](API_REFERENCE.md#api-endpoint-reference-advanced)**

---

## Installation

### From PyPI (when published)

```bash
pip install gpu-scheduler
```

### From Source

```bash
git clone https://github.com/hjenryin/GPU-Scheduler.git
cd GPU-Scheduler
pip install -e .
```

### Requirements

- Python 3.8+
- NVIDIA GPU with drivers installed
- `nvidia-smi` available in PATH

---

## Usage Examples

### Example 1: Simple Training Job

```bash
scheduler submit --req 2 train.py
```

### Example 2: Multi-Stage Pipeline (Using submit-batch)

```bash
# Create a pipeline script list
cat > pipeline.txt << EOF
preprocess.py --input data.csv --output clean.csv
train.py --data clean.csv --epochs 50 --lr 0.001
evaluate.py --model best.pt --data test.csv
EOF

# Submit as sequential pipeline (each job depends on previous)
scheduler submit-batch --sequential --req 2 pipeline.txt
```

### Example 3: Multi-Stage Pipeline (Manual Dependencies)

```bash
# Preprocess
JOB1=$(scheduler submit --req 1 --name "preprocess" preprocess.py | grep "Job ID" | awk '{print $3}')

# Train (depends on preprocess)
JOB2=$(scheduler submit --req 4 --depends-on $JOB1 --name "train" train.py | grep "Job ID" | awk '{print $3}')

# Evaluate (depends on train)
scheduler submit --req 1 --depends-on $JOB2 --name "eval" eval.py
```

### Example 4: Batch Job Submission

```bash
# Create job list with arguments
cat > experiments.txt << EOF
train.py --lr 0.001 --model resnet50
train.py --lr 0.01 --model vgg16
train.py --lr 0.1 --model mobilenet
EOF

# Submit all experiments independently
scheduler submit-batch --req 2 --name "hyperparam-sweep" experiments.txt
```

### Example 5: Specific Node Requirements

```bash
# Must run on gpu1 with 4 GPUs
scheduler submit --req gpu1:4 train.py

# Can run on gpu1 (2 GPUs) OR gpu2 (4 GPUs)
scheduler submit --req gpu1:2,gpu2:4 train.py
```

### Example 6: Python API Integration

```python
from scheduler import SchedulerClient, JobStatus
import time

client = SchedulerClient()

# Submit batch of experiments
jobs = []
for lr in [0.001, 0.01, 0.1]:
    job = client.submit_job(
        script="train.py",
        requirements="2",
        name=f"lr-{lr}",
        env_vars={"LEARNING_RATE": str(lr)}
    )
    jobs.append(job)

# Wait for completion
while any(client.get_job(j.job_id).status == JobStatus.RUNNING for j in jobs):
    time.sleep(10)

print("All experiments complete!")
```

**[→ More Examples in API_REFERENCE.md](API_REFERENCE.md#common-workflows)**

---

## Configuration

Configuration is stored in `~/.scheduler/config.yaml`:

```yaml
# Head node address (for workers and clients)
address: 192.168.1.100:8265

# Node settings
node:
  temp_dir: ~/.scheduler/tmp
  log_dir: ~/.scheduler/logs
  gpu_poll_interval: 10
  gpu_util_threshold: 10
  gpu_mem_threshold: 10
  gpu_stable_time: 30
  job_startup_grace: 120

# Head node settings
head:
  port: 8265
  heartbeat_timeout: 60
  scheduling_interval: 5
  graceful_shutdown_timeout: 60
```

**[→ Complete Configuration Reference](API_REFERENCE.md#configuration)**

---

## Testing

The project includes comprehensive tests:

- **Unit tests**: `tests/unit/` - Individual component testing
- **Integration tests**: `tests/integration/` - Multi-component workflows
- **E2E tests**: `tests/e2e/` - Real process and HTTP testing
- **TUI tests**: `tests/tui/` - Interactive UI testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/test_real_processes.py -v -m "not slow"

# Run with coverage
pytest --cov=scheduler --cov-report=html
```

**Test Coverage:** 90%+ across core components

---

## Documentation

- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete technical reference for all commands and APIs
- **[CODEBASE_STRUCTURE.md](CODEBASE_STRUCTURE.md)** - Architecture and code organization
- **[tests/README.md](tests/README.md)** - Testing guide and patterns
- **[DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md)** - Documentation verification report

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) file for details

---

## Acknowledgments

- Inspired by [Ray](https://github.com/ray-project/ray) cluster management
- GPU monitoring via [pynvml](https://pypi.org/project/nvidia-ml-py/)
- TUI built with [Textual](https://github.com/Textualize/textual)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/hjenryin/GPU-Scheduler/issues)
- **Documentation**: [API_REFERENCE.md](API_REFERENCE.md)
- **Email**: hjenryin@example.com (update with actual contact)

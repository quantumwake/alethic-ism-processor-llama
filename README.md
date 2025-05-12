# Alethic Instruction-Based State Machine (Llama Processor)

The Alethic Llama Processor is a component of the Alethic Instruction-Based State Machine (ISM) ecosystem that integrates with Llama's chat completion API to provide natural language processing capabilities through a message-based architecture.

## Architecture

This processor integrates with the Alethic ISM core system to:

- Process natural language queries using the Llama API
- Support both synchronous and streaming responses
- Connect to a distributed message routing system (NATS)
- Store state in a PostgreSQL database
- Provide telemetry and monitoring

## Prerequisites

- Python 3.8+
- PostgreSQL database
- NATS server (for message routing)
- Llama API key from [llmapi.com](https://llmapi.com/)

## Installation

### Local Setup with uv

```shell
# Install uv (Python package manager)
pip install uv

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### Docker Build

You can build the Docker image using the included Makefile:

```shell
# Build with default image name (krasaee/alethic-ism-processor-llama:latest)
make build

# Build with custom image name
make build IMAGE=your-org/your-image-name:tag
```

## Environment Configuration

The processor requires the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLAMA_API_KEY` | Your Llama API key | None (Required) |
| `LLAMA_API_BASE_URL` | Llama API base URL | https://api.llama-api.com |
| `DATABASE_URL` | PostgreSQL connection string | postgresql://postgres:postgres1@localhost:5432/postgres |
| `ROUTING_FILE` | Path to NATS routing configuration | .routing.yaml |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | INFO |

## Running the Service

### Local Run

```shell
# Set required environment variables
export LLAMA_API_KEY="your_api_key_here"
export DATABASE_URL="postgresql://postgres:postgres1@localhost:5432/postgres"
export ROUTING_FILE=".routing.yaml"
export LOG_LEVEL="DEBUG"

# Run the processor
python main.py
```

### Docker Run

```shell
docker run -d \
  --name alethic-ism-processor-llama \
  -e LLAMA_API_KEY="your_api_key_here" \
  -e LOG_LEVEL=DEBUG \
  -e ROUTING_FILE=/app/repo/.routing.yaml \
  -e DATABASE_URL="postgresql://postgres:postgres1@host.docker.internal:5432/postgres" \
  krasaee/alethic-ism-processor-llama:latest
```

## Kubernetes Deployment

A Kubernetes deployment template is available in `k8s/deployment.yaml`. The template requires:

- A secret named `alethic-ism-processor-llama-secret` containing environment variables
- A secret named `alethic-ism-routes-secret` containing the routing configuration

## Version Management

Use the Makefile to manage versioning:

```shell
# Bump patch version and create a git tag
make version
```

## License

Alethic ISM is under a DUAL licensing model:

**AGPL v3**  
Intended for academic, research, and nonprofit institutional use. As long as all derivative works are also open-sourced under the same license, you are free to use, modify, and distribute the software.

**Commercial License**  
Intended for commercial use, including production deployments and proprietary applications. This license allows for closed-source derivative works and commercial distribution. Please contact us for more information.

For full license details, please refer to the [LICENSE.md](LICENSE.md) file.
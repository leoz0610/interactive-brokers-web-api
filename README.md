# Interactive Brokers Web API

## Video Walkthrough

https://www.youtube.com/watch?v=CRsH9TKveLo

## Requirements

* Docker Desktop - https://www.docker.com/products/docker-desktop/

## Clone the source code
```
git clone https://github.com/hackingthemarkets/interactive-brokers-web-api.git
```

## Bring up the container
```
docker-compose up
```

## Getting a command line prompt

```
docker exec -it ibkr bash
```

## Codex workflows

Open the repository root as the Codex project folder. The root `AGENTS.md` supplies project instructions, and [docs/CODEX_WORKFLOWS.md](docs/CODEX_WORKFLOWS.md) explains how to bootstrap and run the portfolio-return and CNBC extraction workflows.

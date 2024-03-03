# Introduction

This repository is maintained by me, Anton Bolychev, for educational purposes, specifically for the [Async Architecture course](https://tough-dev.school/architecture).

## Repository Overview

This repository is organized into multiple microservices, designed as API-only applications. The microservices included are:

- [Auth Service](#auth-service)
- [Task Tracker](#task-tracker)

The primary programming language is Python, with Postgres as the database and Nats Jestream serving as the message broker.

The project heavily relies on two core Python packages:

- [FastAPI](https://fastapi.tiangolo.com/): A web framework for building APIs with Python 3.8+, utilizing standard Python type hints.
- [FastStream](https://faststream.airt.ai/latest/faststream/): A framework that simplifies the creation of producers and consumers for message queues, providing automatic parsing, networking, and documentation generation.

These packages are well-integrated, allowing the main logic to be written in a single file and the application to be launched with a single command:

```bash
cd servicename/app
uvicorn --port=YOUR_PORT main:api --reload
```

### Auth Service

The Auth Service implements authentication using JWT tokens.

- [`auth/`](./auth): The primary directory for the Auth Service.
  - [`auth/app/main.py`](./auth/app/main.py): The main application file containing the core logic.
  - [`auth/auth`](./auth/auth/): Directory containing configurations, database models, password hashing functions, and request schemas.

### Task Tracker

The Task Tracker manages tasks and their tracking.

- [`tasktracker/`](./tasktracker/): The primary directory for the Task Tracker.
  - [`tasktracker/app/main.py`](./tasktracker/app/main.py): The main application file with the core logic.
  - [`tasktracker/tasktracker/`](./tasktracker/tasktracker/): Directory containing configurations and database models.

### Common Library

A separate library is included to provide shared functionality across all services. Currently, it is utilized for authorization and decoding JWT tokens.

- [`common/common/authorizer.py`](./common/common/authorizer.py): The single file in the common library responsible for authorization.
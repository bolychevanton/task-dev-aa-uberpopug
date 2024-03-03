# Introduction

This repository is maintained by me, Anton Bolychev, for educational purposes, specifically for the [Async Architecture course](https://tough-dev.school/architecture).

## Repo structure

The project consists of several microservices, that are organazied as pure API applications. At the moment they are 

- [Auth service](#auth-service)
- [Task tracker](#task-tracker)

The main language is python. Database used postgres. Nats Jestream is the message broker. 

The 2 core python packages for the projects are 

- [FastAPI](https://fastapi.tiangolo.com/) - web framework for building APIs with Python 3.8+ based on standard Python type hints. 
- [FastStream](https://faststream.airt.ai/latest/faststream/) - the framework that simplifies the process of writing producers and consumers for message queues, handling all the parsing, networking and documentation generation automatically.

They well integrated into each other, thus providing to write the main logics in one file and start the application in 1 command

```
cd servicename/app
uvicorn --port=YOUR_PORT main:api --reload
```

### Auth service 
Authentification service is done on the basis of jwt tokens.
- [auth/](./auth) - the main folder
    - [auth/app/main.py] - main application. Core file with the main logics.
    - [auth/auth](./auth/auth/) - configs, dbmodel, password hashing functions, request schemas 
### Task tracker

- [tasktracker](./tasktracker/) - the main folder
    - [tasktracker/app/main.py](./tasktracker/app/main.py) - main application. Core file with the main logics.
    - [tasktracker/tasktracker/](./tasktracker/tasktracker/) - configs, dbmodel

### Separate library that provides the common functionality for all the services
At the moment it is used only for authorization and decoding of jwt tokens and consists of only one file
- [common/common/authorizer.py](./common/common/authorizer.py)

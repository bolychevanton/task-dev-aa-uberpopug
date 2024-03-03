# Description

This repository is maintained by me, Anton Bolychev, for educational purposes, specifically for the [Async Architecture course](https://tough-dev.school/architecture).

## Repo structure

- [Auth service](./auth/) is done on the basis of jwt tokens
    - [Main application](./auth/app/main.py)
    - [Configs, dbmodel, password utils, schemas](./auth/auth/)
- [Task tracker service](./tasktracker/)
    - [Main application](./tasktracker/app/main.py)
    - [Configs, dbmodel](./tasktracker/tasktracker/)
- [Separate library for decoding of jwt-tokens](./common/common/authorizer.py) - used all across the project

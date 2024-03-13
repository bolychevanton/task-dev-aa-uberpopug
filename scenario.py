# DO NOT READ IT. IT IS ONLY FOR TESTING PURPOSES

import requests


auth_host = "http://127.0.0.1:2000"
tt_host = "http://127.0.0.1:2001"


def login(role, id=""):
    return requests.get(
        f"{auth_host}/login",
        json={"email": f"{role}{id}@popug.com", "password": "password"},
    ).text


def create(role, id=""):
    requests.post(
        f"{auth_host}/register",
        json={
            "fullname": f"{role}{id}",
            "email": f"{role}{id}@popug.com",
            "password": "password",
        },
    )
    requests.post(
        f"{auth_host}/change-role",
        headers={"Authorization": f"Bearer {login('admin')}"},
        params={"role": role, "email": f"{role}{id}@popug.com"},
    )


def create_task(role, role_id, description):
    requests.post(
        f"{tt_host}/create-task",
        headers={"Authorization": f"Bearer {login(role, role_id)}"},
        params={"description": description},
    )


def shuffle_tasks(role, id):
    requests.post(
        f"{tt_host}/shuffle-tasks",
        headers={"Authorization": f"Bearer {login(role, id)}"},
    )


def my_tasks(role, id):
    return requests.get(
        f"{tt_host}/tasks-me",
        headers={"Authorization": f"Bearer {login(role, id)}"},
    )


# for idx in range(1, 4):
#     create("worker", idx)

# for idx in range(1, 3):
#     create("manager", idx)

# for idx in range(1, 4):
#     create_task("worker", 1, "worker" + str(1))
#     create_task("worker", 2, "worker" + str(2))
#     create_task("worker", 3, "worker" + str(3))
#     create_task("manager", 1, "manager" + str(1))

# shuffle_tasks("manager", 1)
# print(login("worker", 1))

print(my_tasks("worker", 1).text)

# print(
#     requests.get(
#         f"{tt_host}/tasks/me",
#         headers={"Authorization": f"Bearer {login('worker', 1)}"},
#     )
# )

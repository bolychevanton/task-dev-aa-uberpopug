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


def create_task(role, role_id, title, description):
    requests.post(
        f"{tt_host}/add-task",
        headers={"Authorization": f"Bearer {login(role, role_id)}"},
        params={"title": title, "description": description},
    )


def shuffle_tasks(role, id):
    requests.post(
        f"{tt_host}/shuffle-tasks",
        headers={"Authorization": f"Bearer {login(role, id)}"},
    )


def my_tasks(role, id):
    return requests.get(
        f"{tt_host}/tasks-me",
        params={"status": "open"},
        headers={"Authorization": f"Bearer {login(role, id)}"},
    )


def complete_task(role, id, task_id):
    requests.post(
        f"{tt_host}/complete-task",
        headers={"Authorization": f"Bearer {login(role, id)}"},
        params={"task_id": task_id},
    )


for idx in range(1, 4):
    create("worker", idx)

for idx in range(1, 3):
    create("manager", idx)


create_task("worker", 1, "fifth", "desc1")
create_task("worker", 2, "sixth", "desc2")
create_task("worker", 3, "seventh", "desc3")
create_task("manager", 1, "eightth", "desc4")

# shuffle_tasks("manager", 1)
# print(login("worker", 1))

import json

for idx in range(1, 4):

    tasks = json.loads(my_tasks("worker", idx).text)
    for task in tasks:
        complete_task("worker", idx, task["id"])  # tasks[0]["id"]

# # print(
#     requests.get(
#         f"{tt_host}/tasks/me",
#         headers={"Authorization": f"Bearer {login('worker', 1)}"},
#     )
# )

import requests, json, time
url = "http://127.0.0.1:5000"

# send a post request
# response = requests.post(f"{url}/deck/1733693835908/add", json={"front": "Hello", "back": "World"})

# Delete card
# response = requests.post(f"{url}/note/remove", json={"note_id": 1733699994597})

# Answer card
# response = requests.post(f"{url}/study/answer", json={"card_id": 1296169988801, "rating": 1, "time_started": time.time()})

# response = requests.post(f"{url}/download", json={"url":"https://ankiweb.net/svc/shared/download-deck/1243388349?t=eyJvcCI6InNkZCIsImlhdCI6MTczMzcxNDY1MiwianYiOjF9.UTVMSk0oPTsMsGSKHUotvP22Cpx4_sD5Ak6BqM685PQ"})

# response = requests.post(f"{url}/register", json={"username": "zoey", "password": "admin"})
# print(response.json())

session = requests.Session()
response = session.post(f"{url}/login", json={"username": "zoey", "password": "admin"})
print(response.json())
while True:
    url = input("Enter the url: ")
    response = session.get(f"http://127.0.0.1:5000/{url}")
    print(response.json())
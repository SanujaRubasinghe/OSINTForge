import os
# import requests

# token = os.getenv("GITHUB_TOKEN", "")

# headers = {
#     "Authorization": f'Bearer {token}',
#     "Accept": "application/vnd.github+json"
# }

# url = "https://api.github.com/search/users"
# params = {
#     "q": "Sanuja Rubasinghe"
# }

# response = requests.get(url, headers=headers, params=params)

# print(response.json())

token = os.getenv("NEWSAPI_KEY")
print(token)
from google_auth_oauthlib.flow import InstalledAppFlow

# gmail.modify lets us read messages AND apply labels (mark as Processed/Vikunja)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

with open('token.json', 'w') as f:
    f.write(creds.to_json())

print("token.json saved.")

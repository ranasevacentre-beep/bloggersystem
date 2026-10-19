#!/usr/bin/env python3
"""
सिर्फ़ एक बार चलाना है (अपने कंप्यूटर पर) ताकि Google Refresh Token मिल जाए।

उपयोग:
  pip install google-auth-oauthlib
  python get_refresh_token.py client_secret.json
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/blogger"]

if len(sys.argv) != 2:
    sys.exit("उपयोग: python get_refresh_token.py client_secret.json")

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\n=== ये तीन वैल्यू GitHub Secrets में डालें ===")
print("GOOGLE_CLIENT_ID     =", creds.client_id)
print("GOOGLE_CLIENT_SECRET =", creds.client_secret)
print("GOOGLE_REFRESH_TOKEN =", creds.refresh_token)

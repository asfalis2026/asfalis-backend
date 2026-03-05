"""Quick sanity check for both Twilio accounts."""
import re, os, sys

env = {}
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
os.environ.update(env)

from twilio.rest import Client

sms_sid   = os.environ.get('TWILIO_ACCOUNT_SID')
sms_token = os.environ.get('TWILIO_AUTH_TOKEN')
wa_sid    = os.environ.get('TWILIO_WA_ACCOUNT_SID')
wa_token  = os.environ.get('TWILIO_WA_AUTH_TOKEN')

print('=== SMS Account (Account 1) ===')
sms_client = Client(sms_sid, sms_token)
sms_account = sms_client.api.accounts(sms_sid).fetch()
print(f'SID: {sms_sid[:12]}... | Type: {sms_account.type} | Status: {sms_account.status}')

print()
print('=== WhatsApp Account (Account 2) ===')
wa_client = Client(wa_sid, wa_token)
wa_account = wa_client.api.accounts(wa_sid).fetch()
print(f'SID: {wa_sid[:12]}... | Type: {wa_account.type} | Status: {wa_account.status}')

print()
print('Both accounts loaded successfully.')

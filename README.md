# keychecker
a fast, bulk key checker for various AI services

Currently supports and validates keys for the services below, and checks for the listed attributes a key might have:

- OpenAI - (Best model, key in quota, RPM (catches increase requests), tier, list of organizations if applicable, trial key status)
- Anthropic - (Pozzed status and key tier, along with remaining character quota)
- AI21 - (Trial check)
- Google MakerSuite (List of available models + billing status)
- AWS - (Admin status, auto-fetch the region, logging status, username, bedrock status + enabled models)
- Azure - (Auto-fetch all deployments, auto-fetch best deployment/model, filter status, dall-e deployment)
- Google Cloud Vertex AI - (Requires a key file since oauth tokens expire hourly.)
- MistralAI - (Subscription status)
- OpenRouter - (Estimated balance, usage in $, credit limit, RPM, has purchased any credits)
- ElevenLabs - (Key tier, remaining characters in plan, detect uncapped char quota, pro voice cloning limit, invoice details on pay as you go plans)
- DeepSeek - (Account balance)
- xAI - (Subscription status)

# Usage:
`pip install -r requirements.txt`

`python main.py`

# Optional Arguments:

`-proxyoutput`

Outputs keys in a format that can be easily copied and pasted into khanon's proxy instead of pretty print

`-nooutput`

Stops outputting and saving keys to the snapshot file (proxyoutput will also do this)

`-file`

Reads keys from a file instead of stdin, place either the absolute or relative path to the file in quotes after the flag.

`-verbose`

Displays an output as keys are being checked real time.

`-awslegacy`

Uses the slower legacy AWS checker (thread parallelized + boto3) instead of the new asynchronous REST API one.
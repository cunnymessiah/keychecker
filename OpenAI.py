import APIKey
import asyncio

oai_api_url = "https://api.openai.com/v1"
oai_tiers = {40000: 'Free', 200000: 'Tier1', 2000000: 'Tier2', 4000000: 'Tier3', 10000000: 'Tier4', 150000000: 'Tier5'}

standard_model_ids = {
    "omni-moderation-2024-09-26",
    "gpt-4o-mini-audio-preview-2024-12-17",
    "dall-e-3",
    "dall-e-2",
    "gpt-4o-audio-preview-2024-10-01",
    "o1",
    "gpt-4o-audio-preview",
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "o1-2024-12-17",
    "gpt-4-0314",
    "gpt-4o-mini-realtime-preview",
    "o1-mini-2024-09-12",
    "o1-preview-2024-09-12",
    "o1-mini",
    "o1-preview",
    "gpt-4o-mini-audio-preview",
    "whisper-1",
    "gpt-4-turbo",
    "gpt-4-32k-0314",
    "gpt-4o-realtime-preview-2024-10-01",
    "gpt-4",
    "babbage-002",
    "gpt-4-turbo-preview",
    "tts-1-hd-1106",
    "gpt-4-0125-preview",
    "gpt-4o-audio-preview-2024-12-17",
    "tts-1-hd",
    "gpt-4o-mini-2024-07-18",
    "gpt-4o-2024-08-06",
    "gpt-4o",
    "tts-1",
    "tts-1-1106",
    "gpt-4-turbo-2024-04-09",
    "davinci-002",
    "gpt-3.5-turbo-1106",
    "gpt-4o-mini",
    "gpt-4o-2024-05-13",
    "gpt-3.5-turbo-instruct",
    "chatgpt-4o-latest",
    "gpt-3.5-turbo-instruct-0914",
    "gpt-3.5-turbo-0125",
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k-0613",
    "gpt-4o-realtime-preview",
    "gpt-3.5-turbo-16k",
    "text-embedding-3-small",
    "gpt-4o-2024-11-20",
    "gpt-4-1106-preview",
    "text-embedding-ada-002",
    "text-embedding-3-large",
    "o3-mini-2025-01-31",
    "gpt-4-0613",
    "gpt-4-32k-0613",
    "o3-mini",
    "omni-moderation-latest",
    "gpt-4-base",
    "gpt-4-32k",
    "o1-pro",
    "o1-pro-2025-03-19",
    "gpt-4o-transcribe",
    "computer-use-preview",
    "computer-use-preview-2025-03-11",
    "gpt-4o-search-preview",
    "gpt-4o-search-preview-2025-03-11",
    "gpt-4o-mini-search-preview",
    "gpt-4o-mini-search-preview-2025-03-11",
    "gpt-4o-mini-transcribe",
    "gpt-4o-mini-tts",
    "gpt-4.5-preview",
    "gpt-4.5-preview-2025-02-27",
    "o3",
    "o4-mini",
    "o3-2025-04-16",
    "o4-mini-2025-04-16",
    "gpt-4.1-mini",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-nano",
    "gpt-4.1-nano-2025-04-14",
    "gpt-4.1",
    "gpt-4.1-2025-04-14",
}


async def get_oai_model(key: APIKey, session, retries, org=None):
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.get(f'{oai_api_url}/models', headers=headers) as response:
            if response.status == 200:
                data = await response.json()

                model_priority = ["gpt-4-32k-0314", "gpt-4o", "gpt-4o-mini"]
                available_priority_models = set()

                for model in data["data"]:
                    model_id = model["id"]

                    if "ft:" in model_id:
                        key.has_special_models = True
                    elif model_id not in standard_model_ids and ":ft-" not in model_id:
                        key.extra_models = True
                        key.extra_model_list.add(model_id)

                    if model_id == "gpt-4-base":
                        key.the_one = True
                    if model_id == "gpt-4-32k" or model_id == "gpt-4-32k-0613":
                        key.real_32k = True

                    if model_id in model_priority:
                        available_priority_models.add(model_id)

                key.model = "gpt-4o-mini"
                for priority_model in model_priority:
                    if priority_model in available_priority_models:
                        key.model = priority_model
                        break

                return True
            elif response.status == 403:
                key.model = "gpt-4o-mini"
                return True
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)


async def get_oai_key_attribs(key: APIKey, session, retries, org=None):
    chat_object = {"model": f'{key.model}', "messages": [{"role": "user", "content": ""}], "max_tokens": 0}
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}', 'accept': 'application/json'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.post(f'{oai_api_url}/chat/completions', headers=headers, json=chat_object) as response:
            if response.status in [400, 429]:
                data = await response.json()
                message = data["error"]["type"]
                if message is None:
                    return
                match message:
                    case "access_terminated":
                        return
                    case "billing_not_active":
                        return
                    case "insufficient_quota":
                        key.has_quota = False
                    case "invalid_request_error":
                        key.has_quota = True
                        key.rpm = int(response.headers.get("x-ratelimit-limit-requests"))
                        key.tier = await get_oai_key_tier(key, session, retries)
                return True
            elif response.status not in [502, 500]:
                return
        await asyncio.sleep(0.5)


# this will weed out fake t4/t5 keys reporting a 10k rpm limit, those keys would have requested to have their rpm increased
async def get_oai_key_tier(key: APIKey, session, retries, org=None):
    chat_object = {"model": f'gpt-4o-mini', "messages": [{"role": "user", "content": ""}], "max_tokens": 0}
    for attempt in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}', 'accept': 'application/json'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.post(f'{oai_api_url}/chat/completions', headers=headers, json=chat_object) as response:
            if response.status in [400, 429]:
                try:
                    return oai_tiers[int(response.headers.get("x-ratelimit-limit-tokens"))]
                except (KeyError, TypeError, ValueError):
                    if attempt == retries - 1:
                        # saw a few keys return no limit headers at all for 4o-mini, but then a 4mil token limit for normal 4o which is more than t4, while also having a t2 rpm (5k)?
                        # there also seems to be another key tier in between free and t1, with a 100k token limit and 200 rpm
                        return "Tier Unknown (strange or absent token limit in header)"
                    continue
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)
    return


async def get_oai_org(key: APIKey, session, retries):
    for _ in range(retries):
        async with session.get(f'{oai_api_url}/me', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
            if response.status == 200:
                data = await response.json()
                orgs = data["orgs"]["data"]

                for org in orgs:
                    if not org["personal"]:
                        if org["is_default"]:
                            key.default_org = org["name"]
                        key.organizations.append(org["name"])
                return True
            elif response.status == 403:
                key.default_org = None
                return True
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)


async def clone_key(key: APIKey, session, retries):
    cloned_keys = set()
    if len(key.organizations) <= 0:
        return False
    for org in key.organizations:
        if org == key.default_org:
            continue
        new_key = key.clone()
        new_key.default_org = org
        results = await asyncio.gather(get_oai_model(new_key, session, retries, org), get_oai_key_attribs(new_key, session, retries, org))
        model_result, attribs_result = results
        if model_result is not None and attribs_result is not None:
            cloned_keys.add(new_key)
    return cloned_keys


def check_manual_increase(key: APIKey):
    if key.model == 'gpt-4o-mini' and key.rpm > 500: # could false flag high tier alternative orgs that restrict model access to only 4o-mini
        return True
    elif key.tier == 'Tier1' and key.model != 'gpt-4o-mini' and key.rpm > 500:
        return True
    elif key.tier in ['Tier2', 'Tier3'] and key.rpm > 5000:
        return True
    elif key.tier in ['Tier3', 'Tier4'] and key.rpm > 10000:
        return True
    return False


def pretty_print_oai_keys(keys, cloned_keys):
    print('-' * 90)
    org_count = 0
    quota_count = 0
    no_quota_count = 0
    t5_count = 0

    key_groups = {
        "gpt-4o-mini": {
            "has_quota": [],
            "no_quota": []
        },
        "gpt-4o": {
            "has_quota": [],
            "no_quota": []
        },
        "gpt-4-32k-0314": {
            "has_quota": [],
            "no_quota": []
        }
    }

    for key in keys:
        if key.organizations:
            org_count += 1
        if key.tier == 'Tier5':
            t5_count += 1
        if key.has_quota:
            key_groups[key.model]['has_quota'].append(key)
            quota_count += 1
        else:
            key_groups[key.model]['no_quota'].append(key)
            no_quota_count += 1

    print(f'Validated {len(key_groups["gpt-4o-mini"]["has_quota"])} gpt-4o-mini keys with quota:')
    for key in key_groups["gpt-4o-mini"]["has_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + f" | {key.rpm} RPM" + (f" - {key.tier}" if key.tier else "")
              + (" (RPM increased via request)" if check_manual_increase(key) else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else ""))

    print(f'\nValidated {len(key_groups["gpt-4o-mini"]["no_quota"])} gpt-4o-mini keys with no quota:')
    for key in key_groups["gpt-4o-mini"]["no_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else ""))

    print(f'\nValidated {len(key_groups["gpt-4o"]["has_quota"])} gpt-4o keys with quota:')
    for key in key_groups["gpt-4o"]["has_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + f" | {key.rpm} RPM" + (f" - {key.tier}" if key.tier else "")
              + (" (RPM increased via request)" if check_manual_increase(key) else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else ""))

    print(f'\nValidated {len(key_groups["gpt-4o"]["no_quota"])} gpt-4o keys with no quota:')
    for key in key_groups["gpt-4o"]["no_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else ""))

    print(f'\nValidated {len(key_groups["gpt-4-32k-0314"]["has_quota"])} gpt-4-32k keys with quota:')
    for key in key_groups["gpt-4-32k-0314"]["has_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + f" | {key.rpm} RPM" + (f" - {key.tier}" if key.tier else "")
              + (" (RPM increased via request)" if check_manual_increase(key) else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else "")
              + (f" | real 32k key (pre deprecation)" if key.real_32k else "")
              + (f" | !!!god key!!!" if key.the_one else ""))

    print(f'\nValidated {len(key_groups["gpt-4-32k-0314"]["no_quota"])} gpt-4-32k keys with no quota:')
    for key in key_groups["gpt-4-32k-0314"]["no_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | key has access to non-standard models: {', '.join(key.extra_model_list)}" if key.extra_models else "")
              + (f" | real 32k key (pre deprecation)" if key.real_32k else "")
              + (f" | !!!god key!!!" if key.the_one else ""))

    if cloned_keys:
        print(f'\n--- Cloned {len(cloned_keys)} keys due to finding alternative orgs that could prompt ---')
    print(f'\n--- Total Valid OpenAI Keys: {len(keys)} ({quota_count} in quota, {no_quota_count} no quota, {org_count} orgs, {t5_count} Tier5) ---\n')

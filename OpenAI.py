import copy
import APIKey
import asyncio

oai_api_url = "https://api.openai.com/v1"
# free tier keys are no longer considered human
oai_tiers = {
    'Tier 1': {'tpm': 500000, 'rpm': 500},  # why is this grayed out on the website
    'Tier 2': {'tpm': 1000000, 'rpm': 5000},
    'Tier 3': {'tpm': 2000000, 'rpm': 5000},
    'Tier 4': {'tpm': 4000000, 'rpm': 10000},
    'Tier 5': {'tpm': 40000000, 'rpm': 15000} # non gpt-5 -> 30000000, 10000
}

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
    "o3-mini",
    "omni-moderation-latest",
    "gpt-4-base",
    "o1-pro",
    "o1-pro-2025-03-19",
    "gpt-4o-transcribe",
    "gpt-4o-transcribe-diarize",
    "computer-use-preview",
    "computer-use-preview-2025-03-11",
    "gpt-4o-search-preview",
    "gpt-4o-search-preview-2025-03-11",
    "gpt-4o-mini-search-preview",
    "gpt-4o-mini-search-preview-2025-03-11",
    "gpt-4o-mini-transcribe",
    "gpt-4o-mini-tts",
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
    "gpt-image-1",
    "gpt-image-1-mini",
    "codex-mini-latest",
    "gpt-4o-realtime-preview-2025-06-03",
    "gpt-4o-audio-preview-2025-06-03",
    "o3-pro",
    "o3-pro-2025-06-10",
    "o3-deep-research",
    "o3-deep-research-2025-06-26",
    "o4-mini-deep-research",
    "o4-mini-deep-research-2025-06-26",
    "gpt-5-mini",
    "gpt-5-mini-2025-08-07",
    "gpt-5-nano",
    "gpt-5-nano-2025-08-07",
    "gpt-5",
    "gpt-5-2025-08-07",
    "gpt-5-chat-latest",
    "gpt-5-codex",
    "gpt-5-pro",
    "gpt-5-pro-2025-10-06",
    "gpt-5-search-api",
    "gpt-5-search-api-2025-10-14",
    "gpt-audio-2025-08-28",
    "gpt-realtime-2025-08-28",
    "gpt-audio",
    "gpt-audio-mini",
    "gpt-audio-mini-2025-10-06",
    "gpt-realtime",
    "gpt-realtime-mini",
    "gpt-realtime-mini-2025-10-06",
    "sora-2",
    "sora-2-pro",
    "gpt-5.1-2025-11-13",
    "gpt-5.1-chat-latest",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5.1-codex-mini",
}

running_org_verify = False

non_slop_standard = {"gpt-5", "gpt-5-chat-latest", "o3", "gpt-4.1", "chatgpt-4o-latest", "gpt-4o"}  # i imagine this is all people care about now
async def get_oai_model(key: APIKey, session, retries, org=None):
    accessible_models = set()
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.get(f'{oai_api_url}/models', headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                for model in data["data"]:
                    model_id = model["id"]
                    if "ft:" in model_id:
                        key.has_special_models = True
                    elif model_id not in standard_model_ids and ":ft-" not in model_id:
                        key.extra_models = True
                        key.extra_model_list.add(model_id)

                    if model_id == "gpt-4-base" or model_id == "gpt-5-alpha-max" or model_id == "gpt-4.5-preview":
                        key.the_one = True
                        key.slop = False
                    if model_id == "gpt-4-32k" or model_id == "gpt-4-32k-0613":
                        key.real_32k = True
                        key.slop = False
                    if model_id in non_slop_standard:
                        key.slop = False
                        key.model = model_id
                        accessible_models.add(model_id)

                key.missing_models = non_slop_standard.difference(accessible_models)

                return True
            elif response.status == 403:
                key.model = "gpt-5"
                key.access_to_model_listing = False
                return True
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)


async def get_oai_key_attribs(key: APIKey, session, retries, org=None, check_id=False):
    param = "max_tokens" if "gpt-4" in key.model else "max_completion_tokens"
    chat_object = {"model": key.model, "messages": [{"role": "user", "content": ""}], param: 0}
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}', 'accept': 'application/json'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.post(f'{oai_api_url}/chat/completions', headers=headers, json=chat_object) as response:
            if (response.status == 403):
                return True
            elif response.status in [400, 429]:
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
                        tpm = int(response.headers.get("x-ratelimit-limit-tokens"))
                        key.tier = await get_oai_key_tier(tpm, key.model)
                        if check_id:
                            global running_org_verify
                            running_org_verify = True
                            key.id_verified = await check_id_verified(key, session, retries)
                        key.slop = False
                return True
            elif response.status not in [502, 500]:
                return
        await asyncio.sleep(0.5)


async def check_id_verified(key: APIKey, session, retries, org=None):
    # valid parameter check is ran before unverified org detection, so the request has to be legitimate.
    chat_object = {"model": "o3", "messages": [{"role": "user", "content": ""}], "max_completion_tokens": 1, "stream": True}
    for attempt in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}', 'accept': 'application/json'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.post(f'{oai_api_url}/chat/completions', headers=headers, json=chat_object) as response:
            if response.status == 200:
                return True
            if response.status == 429:
                continue
            if attempt == retries - 1:
                return False
            if response.status == 400:
                data = await response.json()
                message = data["error"]["message"]
                if "Your organization must be verified" in message:
                    return False
                else:
                    return True
            await asyncio.sleep(0.5)
    return False


# this will weed out fake t4/t5 keys reporting a 10k rpm limit, those keys would have requested to have their rpm increased
unknown = "Tier Unknown (strange or absent token limit in header)"
async def get_oai_key_tier(tpm, model_name):
    if not isinstance(tpm, int):
        return unknown

    fixed_tiers = copy.deepcopy(oai_tiers)
    if "gpt-5" not in model_name:
        fixed_tiers['Tier 5']['tpm'] = 30000000
    for tier_name, tier_data in fixed_tiers.items():
        if tier_data['tpm'] == tpm:
            return tier_name
    return unknown


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
    fixed_tiers = copy.deepcopy(oai_tiers)
    if "gpt-5" not in key.model:
        fixed_tiers['Tier 5']['rpm'] = 10000
    if key.tier in fixed_tiers:
        standard_rpm = fixed_tiers[key.tier]['rpm']
        return key.rpm > standard_rpm
    return False


def format_key_details(key: APIKey):
    details = [key.api_key]
    if key.access_to_model_listing is False:
        details.append("no access to /models endpoint")
    if len(key.missing_models) > 0 and not key.slop and key.has_quota:
        details.append(f"!!!WARNING!!! key doesn't have access to models: {key.missing_models}")
    if key.default_org:
        details.append(f"default org - {key.default_org}")
    other_orgs = [org for org in key.organizations if org != key.default_org]
    if other_orgs:
        details.append(f"other orgs - {other_orgs}")
    if key.has_quota:
        details.append(f"{key.rpm} RPM")
        if check_manual_increase(key):
            details.append("(RPM increased via request)")
    if key.the_one:
        details.append(f"!!!god key!!!")
    if key.real_32k:
        details.append(f"!!!32k key!!!")
    if key.has_special_models:
        details.append("key has finetuned models")
    if key.extra_models:
        details.append(f"key has access to non-standard models: {', '.join(key.extra_model_list)}")
    if key.id_verified:
        details.append("id verified")

    return " | ".join(details)

def pretty_print_oai_keys(keys, cloned_keys):
    print('-' * 90)

    group = {
        "quota": {},
        "no_quota": [],
        "slop": []
    }

    for key in keys:
        if key.slop:
            group["slop"].append(key)
        elif key.has_quota:
            if key.tier not in group["quota"]:
                group["quota"][key.tier] = []
            group["quota"][key.tier].append(key)
        else:
            group["no_quota"].append(key)

    quota_keys_by_tier = group["quota"]
    stats = {
        "quota_count": sum(len(tier_keys) for tier_keys in quota_keys_by_tier.values()),
        "no_quota_count": len(group["no_quota"]),
        "slop_count": len(group["slop"]),
        "org_count": sum(1 for k in keys if k.organizations),
        "verified_org_count": sum(1 for k in keys if k.id_verified),
        "t5_count": len(quota_keys_by_tier.get('Tier 5', []))
    }

    if stats["quota_count"] > 0:
        print(f"\n--- Verified {stats['quota_count']} OpenAI keys with quota ---")
        for tier_name in reversed(oai_tiers.keys()):
            if tier_name in quota_keys_by_tier:
                print(f"\nFound {len(quota_keys_by_tier[tier_name])} keys in {tier_name}:")
                for key in quota_keys_by_tier[tier_name]:
                    print(format_key_details(key))

        if unknown in quota_keys_by_tier:
            print(f"\nFound {len(quota_keys_by_tier[unknown])} keys of {unknown}:")
            for key in quota_keys_by_tier[unknown]:
                print(format_key_details(key))

    if stats["no_quota_count"] > 0:
        print(f"\n--- Verified {stats['no_quota_count']} OpenAI keys with no quota ---")
        for key in group["no_quota"]:
            print(format_key_details(key))

    if stats["slop_count"] > 0:
        print(f"\n--- Verified {stats['slop_count']} OpenAI keys that are slop (no access to useful models or on free tier) ---")
        for key in group["slop"]:
            print(format_key_details(key))

    if cloned_keys:
        print(f'\n--- Cloned {len(cloned_keys)} keys due to finding alternative orgs that could prompt ---')
    summary = f'\n--- Total Valid OpenAI Keys: {len(keys)} ' + f'({stats["quota_count"]} in quota, {stats["no_quota_count"]} no quota, {stats["slop_count"]} slop, {stats["org_count"]} orgs'
    if running_org_verify:
        summary += f' - {stats["verified_org_count"]} with id verified'
    summary += f', {stats["t5_count"]} Tier 5) ---\n'
    print(summary)

import APIKey
import asyncio

oai_api_url = "https://api.openai.com/v1"
oai_t1_rpm_limits = {"gpt-4o-mini": 500, "gpt-4-32k-0314": 20}
oai_tiers = {40000: 'Free', 200000: 'Tier1', 2000000: 'Tier2', 4000000: 'Tier3', 10000000: 'Tier4', 150000000: 'Tier5'}


async def get_oai_model(key: APIKey, session, retries, org=None):
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.get(f'{oai_api_url}/models', headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                models = sorted(data["data"], key=lambda m: len(m["id"]))
                top_model = "gpt-4o-mini"
                for model in models:
                    if "ft:" in model["id"]:
                        key.has_special_models = True
                    if model["id"] == "gpt-4-base":
                        key.the_one = True
                    if model["id"] == "gpt-4-32k":
                        key.real_32k = True
                    if model["id"] == "gpt-4-32k-0314":
                        top_model = model["id"]
                    elif model["id"] == "gpt-4o-mini":
                        top_model = model["id"]
                key.model = top_model
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
                        if key.rpm < oai_t1_rpm_limits[key.model]:  # oddly seen some gpt4 trial keys
                            key.trial = True
                        key.tier = await get_oai_key_tier(key, session, retries)
                return True
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)


# this will weed out fake t4/t5 keys reporting a 10k rpm limit, those keys would have requested to have their rpm increased
async def get_oai_key_tier(key: APIKey, session, retries, org=None):
    if key.trial:
        return 'Free'
    chat_object = {"model": f'gpt-4o-mini', "messages": [{"role": "user", "content": ""}], "max_tokens": 0}
    for _ in range(retries):
        headers = {'Authorization': f'Bearer {key.api_key}', 'accept': 'application/json'}
        if org is not None:
            headers['OpenAI-Organization'] = org
        async with session.post(f'{oai_api_url}/chat/completions', headers=headers, json=chat_object) as response:
            if response.status in [400, 429]:
                try:
                    return oai_tiers[int(response.headers.get("x-ratelimit-limit-tokens"))]
                except (KeyError, TypeError, ValueError):
                    continue
            elif response.status != 502:
                return
        await asyncio.sleep(0.5)
    return


async def get_oai_org(key: APIKey, session, retries):
    for _ in range(retries):
        async with session.get(f'{oai_api_url}/organizations', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
            if response.status == 200:
                data = await response.json()
                orgs = data["data"]

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
    if len(key.organizations) <= 1:
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
    """
    Checks if the key has manually increased limits beyond the default for its tier.
    Special case: For Free and Tier1 tiers, the 'rpm' attribute is actually RPD (requests per day).
    """

    # i'm not even joking when i say this, they change the response headers to rpd for free and t1 keys
    if key.tier == 'Free':
        return key.rpm > 200
    
    if key.tier == 'Tier1':
        return key.rpm > 10000

    default_limits = {
        'Free':  {'gpt-4o-mini': {'rpm': 3,     'tpm': 40000}},
        'Tier1': {'gpt-4o-mini': {'rpm': 500,   'tpm': 200000}},
        'Tier2': {'gpt-4o-mini': {'rpm': 5000,  'tpm': 2000000}},
        'Tier3': {'gpt-4o-mini': {'rpm': 5000,  'tpm': 4000000}},
        'Tier4': {'gpt-4o-mini': {'rpm': 10000, 'tpm': 10000000}},
        'Tier5': {'gpt-4o-mini': {'rpm': 30000, 'tpm': 150000000}},
    }

    tier_limits = default_limits.get(key.tier, {}).get(key.model)
    if tier_limits is None:
        return False

    if key.rpm > tier_limits['rpm'] or key.tpm > tier_limits['tpm']:
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

    def get_units_for_key(k: APIKey) -> str:
        if k.tier in ("Free", "Tier1"):
            return "RPD"
        else:
            return "RPM"

    print(f'\nValidated {len(key_groups["gpt-4o-mini"]["has_quota"])} gpt-4o-mini keys with quota:')
    for key in key_groups["gpt-4o-mini"]["has_quota"]:
        units = get_units_for_key(key)
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + f" | {key.rpm} {units}"  # <-- use units
              + (f" - {key.tier}" if key.tier else "")
              + (" (RPM increased via request)" if check_manual_increase(key) else "")
              + (f" | TRIAL KEY" if key.trial else "")
              + (f" | key has finetuned models" if key.has_special_models else ""))

    print(f'\nValidated {len(key_groups["gpt-4o-mini"]["no_quota"])} gpt-4o-mini keys with no quota:')
    for key in key_groups["gpt-4o-mini"]["no_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + (f" | key has finetuned models" if key.has_special_models else ""))

    # For gpt-4-32k-0314 with quota
    print(f'\nValidated {len(key_groups["gpt-4-32k-0314"]["has_quota"])} gpt-4-32k keys with quota:')
    for key in key_groups["gpt-4-32k-0314"]["has_quota"]:
        units = get_units_for_key(key)
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + f" | {key.rpm} {units}"  # <-- use units
              + (f" - {key.tier}" if key.tier else "")
              + (" (RPM increased via request)" if check_manual_increase(key) else "")
              + (f" | TRIAL KEY" if key.trial else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | real 32k key (pre deprecation)" if key.real_32k else "")
              + (f" | !!!god key!!!" if key.the_one else ""))

    print(f'\nValidated {len(key_groups["gpt-4-32k-0314"]["no_quota"])} gpt-4-32k keys with no quota:')
    for key in key_groups["gpt-4-32k-0314"]["no_quota"]:
        print(f"{key.api_key}"
              + (f" | default org - {key.default_org}" if key.default_org else "")
              + (f" | other orgs - {key.organizations}" if len(key.organizations) > 1 else "")
              + (f" | key has finetuned models" if key.has_special_models else "")
              + (f" | real 32k key (pre deprecation)" if key.real_32k else "")
              + (f" | !!!god key!!!" if key.the_one else ""))

    if cloned_keys:
        print(f'\n--- Cloned {len(cloned_keys)} keys due to finding alternative orgs that could prompt ---')
    print(f'\n--- Total Valid OpenAI Keys: {len(keys)} '
          f'({quota_count} in quota, {no_quota_count} no quota, {org_count} orgs, {t5_count} Tier5) ---\n')
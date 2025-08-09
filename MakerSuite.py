import random
import APIKey

gemmy_ultra = "gemini-1.0-ultra"


async def check_makersuite(key: APIKey, session):
    async with session.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key.api_key}") as response:
        if response.status != 200 or not await test_key_alive(key, session):
            return
        key.enabled_billing = await test_makersuite_billing(key, session)
        response_json = await response.json()
        model_names = [model['name'].replace('models/', '').replace('-latest', '') for model in response_json['models']]
        if gemmy_ultra in model_names:
            key.models.append(gemmy_ultra)
        if key.enabled_billing:
            await test_key_tier(key, session)
        else:
            key.tier = "Free Tier"
        return True


async def test_key_alive(key: APIKey, session):
    data = {"generationConfig": {"max_output_tokens": 0}}
    async with session.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-exp-03-25:generateContent?key={key.api_key}", json=data) as response:
        resp_json = await response.json()
        if response.status == 429:
            error_details = resp_json.get('error', {}).get('message', '')
            # different type of 429 error compared to hitting the rpm limit, keys with this seem to never recover and are just perma 429'd, so we mark them as invalid
            if "limit 'GenerateContent request limit per minute for a region' of service 'generativelanguage.googleapis.com' for consumer" in error_details:
                return False
        return True

async def test_key_tier(key: APIKey, session):
    data = {
        "contents": [{
            "parts": [{
                "text": "hello" * random.randint(66666, 77777),
            }]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
        },
        "model": "gemini-2.5-pro-preview-tts"
    }

    async with session.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-tts:generateContent?key={key.api_key}", json=data) as response:
        resp_json = await response.json()
        if response.status == 200:
            key.tier = "??? Tier"
        elif response.status == 400:
            if "exceeds the maximum number of tokens allowed" in resp_json.get("error", {}).get("message", ""):
                key.tier = "Tier 3"
        elif response.status == 429:
            violations = resp_json.get("error", {}).get("details", [])[0].get("violations", [])
            for violation in violations:
                quota_metric = violation.get("quotaMetric", "")
                quota_value = violation.get("quotaValue", "")
                if "paid_tier" in quota_metric and quota_value == "10000":
                    key.tier = "Tier 1"
                elif "tier_2" in quota_metric:
                    key.tier = "Tier 2"
                else:
                    key.tier = f"(QM {quota_metric} | QV {quota_value})"


async def test_makersuite_billing(key: APIKey, session):
    data = {"instances": [{"prompt": ""}]}
    async with session.post(f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={key.api_key}", json=data) as response:
        resp_json = await response.json()
        if response.status == 400:
            error_details = resp_json.get('error', {}).get('message', '')
            if 'Imagen API is only accessible to billed users at this time' not in error_details:
                return True
        return False

def pretty_print_makersuite_keys(keys):
    total = 0
    billing_count = 0
    ultra_count = 0

    print('-' * 90)
    print(f'Validated {len(keys)} MakerSuite keys:')

    keys_by_tier = {}
    unknown_keys = set()
    output_order = [
        "Free Tier",
        "Tier 1",
        "Tier 2",
        "Tier 3",
        "??? Tier",
    ]

    for key in keys:
        total += 1
        if key.enabled_billing:
            billing_count += 1
        if "(" in key.tier:
            unknown_keys.add(key)
        else:
            keys_by_tier.setdefault(key.tier, []).append(key)

    for tier in output_order:
        if tier in keys_by_tier:
            keys_in_tier = keys_by_tier[tier]
            print(f'\n{len(keys_in_tier)} keys found in {tier}:')
            for key in keys_in_tier:
                has_ultra = any(gemmy_ultra in model for model in key.models)
                print(f'{key.api_key}' + (' | has ultra' if has_ultra else ''))
                if has_ultra:
                    ultra_count += 1

    if len(unknown_keys) > 0:
        print(f"Found {len(unknown_keys)} keys with strange quota values")
        for key in unknown_keys:
            has_ultra = any(gemmy_ultra in model for model in key.models)
            print(key.api_key + " | " + key.tier + (' | has ultra' if has_ultra else ''))
            if has_ultra:
                ultra_count += 1

    print(f'\n--- Total Valid MakerSuite Keys: {total} ({billing_count} with billing enabled'
          + (f', {ultra_count} with ultra access) ---\n' if ultra_count > 0 else ') ---\n'))
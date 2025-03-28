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

    for key in keys:
        total += 1
        if key.enabled_billing:
            billing_count += 1
        if any(gemmy_ultra in model for model in key.models):
            ultra_count += 1

    sorted_keys = sorted(keys, key=lambda x: (not x.enabled_billing, not any(gemmy_ultra in model for model in x.models)))

    print('-' * 90)
    print(f'Validated {len(keys)} MakerSuite keys:')
    for key in sorted_keys:
        has_ultra = any(gemmy_ultra in model for model in key.models)
        print(f'{key.api_key}' + (' | billing enabled' if key.enabled_billing else '') + (' | has ultra' if has_ultra else ''))
    print(f'\n--- Total Valid MakerSuite Keys: {total} ({billing_count} with billing enabled'
          + (f', {ultra_count} with ultra access) ---\n' if ultra_count > 0 else ') ---\n'))
import APIKey

async def check_xai(key: APIKey, session):
    async with session.get(f'https://api.x.ai/v1/api-key', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status != 200:
            return
        data = await response.json()
        key.blocked = data.get('team_blocked', True) or data.get('api_key_blocked', True) or data.get('api_key_disabled', True)
        if not key.blocked:
            key.subbed = await test_xai_prompt(key, session)
        return True


async def test_xai_prompt(key: APIKey, session):
    data = {"messages": [], "model": "grok-3-mini-latest", "frequency_penalty": -3.0}
    async with session.post(f'https://api.x.ai/v1/chat/completions', headers={'Authorization': f'Bearer {key.api_key}'}, json=data) as response:
        if response.status == 400 or response.status == 200:
            return True
        return False

def pretty_print_xai_keys(keys):
    keys = sorted(keys, key=lambda x: x.subbed, reverse=True)
    print('-' * 90)
    subbed = 0
    print(f'Validated {len(keys)} xAI keys:')
    for key in keys:
        if key.subbed:
            subbed += 1
        print(f'{key.api_key}' + (' | has sub active' if key.subbed else ''))
    print(f'\n--- Total Valid xAI Keys: {len(keys)} ({subbed} with an active subscription) ---\n')
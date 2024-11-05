import APIKey


async def check_openrouter(key: APIKey, session):
    async with session.get(f'https://openrouter.ai/api/v1/auth/key', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status != 200:
            return
        response = await response.json()
        data = response['data']
        if data is None:
            return

        key.usage = data['usage']
        key.credit_limit = data['limit']
        key.bought_credits = not data['is_free_tier']
        key.limit_reached = key.credit_limit is not None and key.usage >= key.credit_limit
        key.rpm = int(data['rate_limit']['requests']) // int(data['rate_limit']['interval'].replace('s', '')) * 60
        # key.balance = await get_key_balance(key, session)

        return True


async def get_key_balance(key: APIKey, session):
    async with session.get(f'https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status != 200:
            return 0
        data = await response.json()
        for model in data['data']:
            if model['id'] == 'openai/gpt-4-turbo-preview':
                prompt_tokens = int(model['per_request_limits']['prompt_tokens'])
                prompt_price = float(model['pricing']['prompt'])
                balance = prompt_tokens * prompt_price
                return balance
        return 0


def pretty_print_openrouter_keys(keys):
    print('-' * 90)
    premium_keys = {key for key in keys if key.balance > 0}
    non_premium_keys = set(keys) - premium_keys

    print(f'Validated {len(keys)} OpenRouter keys:')
    print(f'{len(premium_keys)} keys with balance:')
    for key in premium_keys:
        print(f'{key.api_key} | estimated balance - ${format(key.balance, ".4f")} | usage - ${format(key.usage, ".4f")}' + (' - LIMIT REACHED' if key.limit_reached else "") + (f' | cred limit - ${key.credit_limit}' if key.credit_limit else "") + f' | RPM - {key.rpm}' + (' | purchased credits' if key.bought_credits else ""))

    print(f'\n{len(non_premium_keys)} keys without balance:')
    for key in non_premium_keys:
        print(f'{key.api_key} | usage - ${format(key.usage, ".4f")}' + (' - LIMIT REACHED' if key.limit_reached else "") + (f' | cred limit - ${key.credit_limit}' if key.credit_limit else "") + f' | RPM - {key.rpm}' + (' | purchased credits' if key.bought_credits else ""))

    print(f'\n--- Total Valid OpenRouter Keys: {len(keys)} ({len(premium_keys)} that have the balance to use premium models) ---\n')

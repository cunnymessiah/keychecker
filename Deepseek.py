import APIKey


async def check_whale(key: APIKey, session):
    async with session.get(f'https://api.deepseek.com/models', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status != 200:
            return
        if not await check_balance(key, session):
            return
        return True


async def check_balance(key: APIKey, session):
    async with session.get(f'https://api.deepseek.com/user/balance', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status != 200:
            return
        data = await response.json()
        key.available = data.get('is_available', False)
        balance_infos = data.get('balance_infos', [])
        if balance_infos:
            key.balance = float(balance_infos[0].get('total_balance', '0.0'))
        return True


def pretty_print_deepseek_keys(keys):
    keys = sorted(keys, key=lambda x: x.balance, reverse=True)
    print('-' * 90)
    available = sum(1 for key in keys if key.available)
    print(f'Validated {len(keys)} Deepseek keys:')
    for key in keys:
        balance_str = f'| ${key.balance}' if key.available else ''
        print(f'{key.api_key} {balance_str}')
    print(f'\n--- Total Valid Deepseek Keys: {len(keys)} ({available} with sufficient usage balance) ---\n')

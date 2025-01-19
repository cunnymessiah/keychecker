import APIKey

async def check_whale(key: APIKey, session):
    valid = await check_balance(key, session)
    return valid


async def check_balance(key: APIKey, session):
    async with session.get(f'https://api.deepseek.com/user/balance', headers={'Authorization': f'Bearer {key.api_key}'}) as response:
        if response.status == 429:
            return False
        elif response.status != 200:
            return None

        data = await response.json()
        key.available = data.get('is_available', False)
        balance_infos = data.get('balance_infos', [])
        total_usd = 0.0
        for balance in balance_infos:
            amount = float(balance.get('total_balance', '0.0'))
            currency = balance.get('currency', 'USD')
            if currency == 'CNY':
                amount *= 0.14
            total_usd += amount

        key.balance = f'${total_usd:.1f} USD'
        return True


def pretty_print_deepseek_keys(keys):
    def get_balance_value(key):
        return float(key.balance.split()[0].replace('$', ''))

    keys = sorted(keys, key=lambda x: (
        x.rate_limited,
        get_balance_value(x) == 0,
        -get_balance_value(x)
    ))

    print('-' * 90)
    available = sum(1 for key in keys if key.available)
    print(f'Validated {len(keys)} Deepseek keys:')
    for key in keys:
        balance_str = f' | {key.balance}' if key.available else ''
        ratelimit_str = f' | rate-limited' if key.rate_limited else ''
        print(f'{key.api_key}{balance_str}{ratelimit_str}')
    print(f'\n--- Total Valid Deepseek Keys: {len(keys)} ({available} with sufficient usage balance) ---\n')
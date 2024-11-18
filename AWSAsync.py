import APIKey
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import xml.etree.ElementTree as ET
import asyncio


aws_regions = [
    "us-east-1",
    "us-west-2",
    "ap-southeast-2",
    "ap-south-1",
    "eu-west-3",
]


async def check_aws(key: APIKey, session):
    key.username = await get_username(key, session)
    if key.username is None:
        return

    if not await test_invoke_perms(key, session, "anthropic.claude-3-sonnet-20240229-v1:0"):
        return

    if not key.bedrock_enabled and not key.useless:
        await test_invoke_perms(key, session, "anthropic.claude-v2")

    policies = await get_key_policies(key, session)
    if not key.useless and key.bedrock_enabled:
        await check_logging(key, session)
        await retrieve_activated_models(key, session)
        for region, models in key.models.items():
            key.models[region] = list(set(models))
    elif key.useless and policies is not None:
        key.useless_reasons.append('Key policies lack Admin or User Creation perms')
    return True


async def sign_request(key: APIKey, region, method, url, headers, data, service):
    line = key.api_key.split(":")
    access_key = line[0]
    secret = line[1]
    boto3_session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret,
        region_name=region
    )
    credentials = boto3_session.get_credentials()
    signer = SigV4Auth(credentials, service, region)
    request = AWSRequest(method=method, url=url, headers=headers, data=data)
    signer.add_auth(request)
    return request.headers, request.data


async def test_invoke_perms(key: APIKey, session, model):
    async def check_region(region):
        host = f'bedrock-runtime.{region}.amazonaws.com'
        url = f'https://{host}/model/{model}/invoke'

        signed_headers, signed_data = await sign_request(key, region, 'POST', url, headers, data, 'bedrock')
        async with session.post(url, headers=signed_headers, data=signed_data) as response:
            resp = await response.json()
            message = resp.get('message')
            if response.status == 403:
                if message and ('The request signature we calculated does not match the signature you provided' in message or 'The security token included in the request is invalid' in message):
                    return False
            elif response.status == 400 or response.status == 404:
                if message and 'The provided body' in message:
                    if key.region == "":
                        key.region = region
                    else:
                        key.alt_regions.append(region)
                    key.bedrock_enabled = True
            else:
                return False
        key.useless = False
        return True

    headers = {
        'content-type': 'application/json',
        'accept': '*/*',
    }
    data = {
        "prompt": "\n\nHuman:\n\nAssistant:",
        "max_tokens_to_sample": -1,
    }

    tasks = [asyncio.create_task(check_region(region)) for region in aws_regions]
    results = await asyncio.gather(*tasks)
    return any(results)


async def get_username(key: APIKey, session):
    region = 'us-east-1'
    url = 'https://sts.amazonaws.com/'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = 'Action=GetCallerIdentity&Version=2011-06-15'
    signed_headers, signed_data = await sign_request(key, region, 'POST', url, headers, data, 'sts')

    async with session.post(url, headers=signed_headers, data=signed_data) as response:
        resp = await response.text()
        if 'ErrorResponse' in resp:
            return

        root = ET.fromstring(resp)
        namespace = {'ns': 'https://sts.amazonaws.com/doc/2011-06-15/'}

        arn = root.find('.//ns:Arn', namespaces=namespace).text
        if not arn:
            return "default"
        username = arn.split('/')[-1]
        if "iam::" in username:
            return "default"
        return username


async def get_key_policies(key: APIKey, session):
    url = f'https://iam.amazonaws.com/?Action=ListAttachedUserPolicies&UserName={key.username}&Version=2010-05-08'
    signed_headers, signed_data = await sign_request(key, 'us-east-1', 'GET', url, {}, None, 'iam')
    async with session.get(url, headers=signed_headers) as response:
        resp = await response.text()
        root = ET.fromstring(resp)
        namespace = {'iam': 'https://iam.amazonaws.com/doc/2010-05-08/'}

        attached_policies = root.findall('.//iam:AttachedPolicies/iam:member', namespaces=namespace)
        policy_names = []
        if not attached_policies:
            if not key.bedrock_enabled:
                key.useless = True
            key.useless_reasons.append('Failed Policy Fetch')
            return

        for policy in attached_policies:
            policy_name = policy.find('iam:PolicyName', namespaces=namespace).text
            policy_names.append(policy_name)

            if policy_name == 'AdministratorAccess':
                key.admin_priv = True
            if 'AWSCompromisedKeyQuarantine' in policy_name:
                if not key.bedrock_enabled:
                    key.useless = True
                key.useless_reasons.append('Quarantined Key')
        return policy_names


async def check_logging(key: APIKey, session):
    region = key.region
    host = f'bedrock.{region}.amazonaws.com'
    url = f'https://{host}/logging/modelinvocations'
    signed_headers, signed_data = await sign_request(key, region, 'GET', url, {'accept': 'application/json'}, {}, 'bedrock')
    async with session.get(url, headers=signed_headers) as response:
        if response.status == 200:
            logging_config = await response.json()
            if 'loggingConfig' in logging_config and logging_config['loggingConfig'] is not None and 'textDataDeliveryEnabled' in logging_config['loggingConfig']:
                key.logged = logging_config['loggingConfig']['textDataDeliveryEnabled']
            else:
                key.logged = False
        else:
            key.logged = False


async def retrieve_activated_models(key: APIKey, session):
    tasks = []
    for region in aws_regions:
        if region not in key.models:
            key.models[region] = []
        task = handle_region(key, session, region)
        tasks.append(task)
    await asyncio.gather(*tasks)


async def handle_region(key: APIKey, session, region):
    listed_models = await retrieve_models(key, session, region)
    tasks = [invoke_model(key, session, region, model) for model in listed_models]
    await asyncio.gather(*tasks)


async def invoke_model(key: APIKey, session, region, model):
    model_id, model_name = model
    data = {
        "prompt": "\n\nHuman:\n\nAssistant:",
        "max_tokens_to_sample": -1,
    }
    host = f'bedrock-runtime.{region}.amazonaws.com'
    url = f'https://{host}/model/{model_id}/invoke'
    signed_headers, signed_data = await sign_request(key, region, 'POST', url, {'content-type': 'application/json', 'accept': '*/*'}, data, 'bedrock')
    async with session.post(url, headers=signed_headers, data=signed_data) as response:
        if response.status == 400:
            resp = await response.json()
            if resp['message'] and 'The provided body' in resp['message']:
                key.models[region].append(model_name)
            elif resp['message'] and 'Operation not' in resp['message']:
                key.useless = True
                key.useless_reasons.append('Quarantined Key')


async def retrieve_models(key: APIKey, session, region):
    host = f'bedrock.{region}.amazonaws.com'
    url = f'https://{host}/foundation-models'
    signed_headers, signed_data = await sign_request(key, region, 'GET', url, {'accept': 'application/json'}, {}, 'bedrock')
    async with session.get(url, headers=signed_headers) as response:
        if response.status == 200:
            response = await response.json()
            models = response["modelSummaries"]

            model_providers = ["Meta", "Anthropic", "Mistral AI"]
            model_info = []

            for model in models:
                provider_name = model["providerName"]
                model_id = model["modelId"]
                model_name = model["modelName"]

                if provider_name in model_providers or (provider_name == "Cohere" and ("Command R+" in model_name or "Command R" in model_name)):
                    parts = model_id.split(":")
                    if len(parts) <= 2:
                        model_info.append((model_id, model_name))

            return model_info
        else:
            return []

from enum import Enum


class APIKey:
    def __init__(self, provider, api_key):
        self.provider = provider
        self.api_key = api_key

        if provider == Provider.OPENAI:
            self.model = ""
            self.has_quota = False
            self.default_org = ""
            self.organizations = []
            self.rpm = 0
            self.tier = ""
            self.has_special_models = False
            self.real_32k = False
            self.the_one = False
            self.extra_models = False
            self.extra_model_list = []

        elif provider == Provider.ANTHROPIC:
            self.pozzed = False
            self.rate_limited = False
            self.has_quota = True
            self.tier = ""
            self.remaining_tokens = 0

        elif provider == Provider.AI21:
            self.trial_elapsed = False

        elif provider == Provider.AWS:
            self.username = ""
            self.useless = True
            self.admin_priv = False
            self.bedrock_enabled = False
            self.region = ""
            self.alt_regions = []
            self.useless_reasons = []
            self.logged = False
            self.models = {}

        elif provider == Provider.AZURE:
            self.endpoint = ""
            self.best_deployment = ""
            self.model = ""
            self.deployments = []
            self.unfiltered = False
            self.dalle_deployments = ""
            self.has_gpt4_turbo = []

        elif provider == Provider.VERTEXAI:
            self.project_id = ""
            self.has_opus = False

        elif provider == Provider.MISTRAL:
            self.subbed = False

        elif provider == Provider.MAKERSUITE:
            self.models = []
            self.enabled_billing = False

        elif provider == Provider.OPENROUTER:
            self.usage = 0
            self.credit_limit = 0
            self.rpm = 0
            self.balance = 0
            self.limit_reached = False
            self.bought_credits = False

        elif provider == Provider.ELEVENLABS:
            self.characters_left = 0
            self.usage = ""
            self.tier = ""
            self.unlimited = False
            self.pro_voice_limit = 0

        elif provider == Provider.DEEPSEEK:
            self.balance = "$0.0 USD"
            self.available = False
            self.rate_limited = False

        elif provider == Provider.XAI:
            self.blocked = True
            self.subbed = False

    def clone(self):
        cloned_key = APIKey(self.provider, self.api_key)
        cloned_key.__dict__ = self.__dict__.copy()
        return cloned_key


class Provider(Enum):
    OPENAI = 1,
    ANTHROPIC = 2
    AI21 = 3
    MAKERSUITE = 4
    AWS = 5
    AZURE = 6
    VERTEXAI = 7
    MISTRAL = 8
    OPENROUTER = 9
    ELEVENLABS = 10
    DEEPSEEK = 11
    XAI = 12

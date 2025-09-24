import random
import uuid
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session, joinedload
from openai import OpenAI

from .. import models
from ..core.config import settings
from ..core.security import decrypt_api_key
from ..models.credential import CredentialType

# Load system-wide default models from the .env file
MODELS_ENV_PATH = '/home/hxdi/Kosmos/models.env'
if os.path.exists(MODELS_ENV_PATH):
    load_dotenv(dotenv_path=MODELS_ENV_PATH)

# A map of known provider strings to their official base URLs
KNOWN_PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "kimi": "https://api.moonshot.cn/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

class AIProviderService:
    """
    A service to intelligently select and configure AI model clients
    based on knowledge space settings, user defaults, and system-wide defaults.
    """
    def __init__(self, db: Session):
        self.db = db

    def _infer_base_url(self, provider: str) -> str | None:
        """Infers the base URL from a known provider string."""
        return KNOWN_PROVIDER_BASE_URLS.get(provider.lower())

    def _get_system_default_client(self, credential_type: CredentialType) -> OpenAI | None:
        """
        Gets the system-wide default client from environment variables as the final fallback.
        """
        type_map = {
            CredentialType.VLM: "VLM",
            CredentialType.SLM: "SLM",
            CredentialType.LLM: "LLM",
            CredentialType.EMBEDDING: "EMBEDDING",
        }
        prefix = type_map.get(credential_type)
        if not prefix:
            return None

        model_name = os.getenv(f"{prefix}_MODEL_NAME")
        api_key = os.getenv(f"{prefix}_API_KEY")
        base_url = os.getenv(f"{prefix}_BASE_URL")

        if not (model_name and base_url):
            return None  # System default for this type is not configured

        try:
            client = OpenAI(
                base_url=base_url,
                api_key=api_key or "",
                max_retries=settings.OPENAI_MAX_RETRIES,
            )
            client.model_name = model_name
            # This client is ephemeral and doesn't correspond to a DB credential, so we can't return a credential object.
            return client
        except Exception as e:
            print(f"Warning: Failed to initialize system default client for {prefix} from environment: {e}")
            return None

    def get_default_client_for_user(self, user: models.User, credential_type: CredentialType) -> OpenAI:
        """
        Finds the user's default credential of a specific type and returns an initialized client.
        """
        credential = self.db.query(models.ModelCredential).filter(
            models.ModelCredential.owner_id == user.id,
            models.ModelCredential.credential_type == credential_type,
            models.ModelCredential.is_default == True
        ).first()

        if not credential:
            raise ValueError(f"User '{user.id}' has no default '{credential_type.value}' credential configured.")

        base_url = credential.base_url or self._infer_base_url(credential.provider)
        if not base_url:
            raise ValueError(f"Could not determine base URL for provider '{credential.provider}'.")

        decrypted_api_key = decrypt_api_key(credential.encrypted_api_key) if credential.encrypted_api_key else ""

        if credential.model_family == models.ModelFamily.OPENAI:
            try:
                client = OpenAI(
                    base_url=base_url,
                    api_key=decrypted_api_key,
                    max_retries=settings.OPENAI_MAX_RETRIES,
                )
                client.model_name = credential.model_name
                return client
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        else:
            raise NotImplementedError(f"Model family '{credential.model_family.value}' is not yet supported.")

    def get_client(self, knowledge_space_id: str | uuid.UUID, credential_type: CredentialType) -> OpenAI:
        """
        Selects the best credential for a given knowledge space and type,
        then returns an initialized and configured AI client.
        """
        if isinstance(knowledge_space_id, str):
            knowledge_space_id = uuid.UUID(knowledge_space_id)

        links = self.db.query(models.KnowledgeSpaceModelCredentialLink).options(
            joinedload(models.KnowledgeSpaceModelCredentialLink.credential)
        ).join(models.ModelCredential).filter(
            models.KnowledgeSpaceModelCredentialLink.knowledge_space_id == knowledge_space_id,
            models.ModelCredential.credential_type == credential_type
        ).all()

        if not links:
            raise ValueError(f"No '{credential_type.value}' credentials configured for knowledge space {knowledge_space_id}")

        highest_priority = max(link.priority_level for link in links)
        top_tier_links = [link for link in links if link.priority_level == highest_priority]

        selected_link = random.choices(
            population=top_tier_links,
            weights=[link.weight for link in top_tier_links],
            k=1
        )[0]

        credential = selected_link.credential
        base_url = credential.base_url or self._infer_base_url(credential.provider)
        if not base_url:
            raise ValueError(f"Could not determine base URL for provider '{credential.provider}'.")

        decrypted_api_key = decrypt_api_key(credential.encrypted_api_key) if credential.encrypted_api_key else ""

        if credential.model_family == models.ModelFamily.OPENAI:
            try:
                client = OpenAI(
                    base_url=base_url,
                    api_key=decrypted_api_key,
                    max_retries=settings.OPENAI_MAX_RETRIES,
                )
                client.model_name = credential.model_name
                return client, credential
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        else:
            raise NotImplementedError(f"Model family '{credential.model_family.value}' is not yet supported.")

    def get_vlm_client_with_fallback(self, user_id: uuid.UUID, knowledge_space_id: uuid.UUID) -> tuple[OpenAI, models.ModelCredential]:
        """
        Gets a VLM client with a robust fallback strategy.
        Priority: 1. KS-specific. 2. User's default. 3. System default.
        """
        return self._get_client_with_fallback(knowledge_space_id, user_id, CredentialType.VLM)

    def get_llm_client_with_fallback(self, user_id: uuid.UUID, knowledge_space_id: uuid.UUID) -> OpenAI:
        """
        Gets an LLM client with a robust fallback strategy.
        Priority: 1. KS-specific. 2. User's default. 3. System default.
        """
        client, _ = self._get_client_with_fallback(knowledge_space_id, user_id, CredentialType.LLM)
        return client

    def get_client_for_chunking(self, user_id: uuid.UUID, knowledge_space_id: uuid.UUID) -> OpenAI:
        """
        Gets a client for chunking tasks with a specific fallback priority:
        1. KS SLM -> 2. KS LLM -> 3. User SLM -> 4. User LLM -> 5. System SLM -> 6. System LLM
        """
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id '{user_id}' not found.")

        # Priority 1 & 2: Knowledge Space (SLM -> LLM)
        for cred_type in [CredentialType.SLM, CredentialType.LLM]:
            try:
                client, _ = self.get_client(knowledge_space_id, cred_type)
                return client
            except ValueError:
                continue

        # Priority 3 & 4: User's Default (SLM -> LLM)
        for cred_type in [CredentialType.SLM, CredentialType.LLM]:
            try:
                return self.get_default_client_for_user(user, cred_type)
            except ValueError:
                continue
        
        # Priority 5 & 6: System Default (SLM -> LLM)
        for cred_type in [CredentialType.SLM, CredentialType.LLM]:
            client = self._get_system_default_client(cred_type)
            if client:
                return client

        raise ValueError(f"Could not find any suitable SLM or LLM credential for user '{user_id}' or KS '{knowledge_space_id}', or system-wide.")

    def get_client_for_embedding(self, user_id: uuid.UUID, knowledge_space_id: uuid.UUID) -> OpenAI:
        """
        Gets a client for embedding tasks with a specific fallback priority:
        1. KS EMBEDDING -> 2. User EMBEDDING -> 3. System EMBEDDING
        """
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id '{user_id}' not found.")

        # 1. Try Knowledge Space EMBEDDING
        try:
            client, _ = self.get_client(knowledge_space_id, CredentialType.EMBEDDING)
            return client
        except ValueError:
            pass

        # 2. Try User's Default EMBEDDING
        try:
            return self.get_default_client_for_user(user, CredentialType.EMBEDDING)
        except ValueError:
            pass

        # 3. Try System Default EMBEDDING
        client = self._get_system_default_client(CredentialType.EMBEDDING)
        if client:
            return client

        raise ValueError(f"Could not find any suitable EMBEDDING credential for user '{user_id}' or KS '{knowledge_space_id}', or system-wide.")

    def _get_client_with_fallback(self, knowledge_space_id: uuid.UUID, user_id: uuid.UUID, credential_type: CredentialType) -> tuple[OpenAI, models.ModelCredential | None]:
        """
        Private helper to get a client with a fallback strategy.
        Priority: 1. KS-specific -> 2. User's default -> 3. System-wide default.
        Returns a tuple of (client, credential_object | None).
        The credential object is None for system defaults as they don't exist in the DB.
        """
        # 1. Try to get from Knowledge Space configuration
        try:
            client, credential = self.get_client(knowledge_space_id, credential_type)
            return client, credential
        except ValueError:
            pass

        # 2. Try to get from User's default configuration
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            try:
                credential = self.db.query(models.ModelCredential).filter(
                    models.ModelCredential.owner_id == user.id,
                    models.ModelCredential.credential_type == credential_type,
                    models.ModelCredential.is_default == True
                ).first()
                if credential:
                    client = self.get_default_client_for_user(user, credential_type)
                    return client, credential
            except ValueError:
                pass
        
        # 3. Fallback to System-wide default from environment
        client = self._get_system_default_client(credential_type)
        if client:
            return client, None # No DB credential object for system defaults

        raise ValueError(f"No '{credential_type.value}' credential found for KS '{knowledge_space_id}', as a default for user '{user_id}', or as a system-wide default.")

    def get_client_for_tagging(self, knowledge_space_id: uuid.UUID, user_id: uuid.UUID, mode: str) -> OpenAI:
        """
        Gets a client for tagging tasks with a robust fallback and model preference strategy.
        - 'assignment' & 'shadow': Prefer SLM, fall back to LLM.
        - 'evolution': Prefer LLM.
        """
        # For 'assignment' and 'shadow', prioritize SLM for cost/speed.
        if mode in ["assignment", "shadow"]:
            try:
                client, _ = self._get_client_with_fallback(knowledge_space_id, user_id, CredentialType.SLM)
                return client
            except ValueError:
                pass

        # For 'evolution', or as a fallback for other modes, use LLM.
        try:
            client, _ = self._get_client_with_fallback(knowledge_space_id, user_id, CredentialType.LLM)
            return client
        except ValueError as e:
            raise ValueError(f"Could not find any suitable SLM or LLM credential for mode '{mode}' in KS '{knowledge_space_id}': {e}")

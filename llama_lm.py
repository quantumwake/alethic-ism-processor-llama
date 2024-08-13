import os.path
from typing import Any

import openai
import dotenv
from core.base_processor_lm import BaseProcessorLM
from core.utils.ismlogging import ism_logger

from openai import OpenAI, Stream
from core.utils.general_utils import parse_response

dotenv.load_dotenv()

LLAMA_API_BASE_URL = os.environ.get("LLAMA_API_BASE_URL", "https://api.llama-api.com")
LLAMA_API_KEY = os.environ.get('LLAMA_API_KEY', None)

openai.api_key = LLAMA_API_KEY
openai.base_url = LLAMA_API_BASE_URL

logging = ism_logger(__name__)
logging.info(f'**** LLAMA API KEY (last 4 chars): {LLAMA_API_KEY[-4:]} ****')


class LlamaChatCompletionProcessor(BaseProcessorLM):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # async def process_input_data_entry(self, input_query_state: dict, force: bool = False):
    #     return []

    def calculate_usage(self, response: Any):

        if isinstance(response, Stream):
            completion_tokens = response.usage.prompt_tokens
            prompt_tokens = response.usage.prompt_tokens
            total_tokens = response.usage.total_tokens

    async def _stream(self, input_data: Any, template: str):
        if not template:
            template = str(input_data)

        # rendered message we want to submit to the model
        message_list = self.derive_messages_with_session_data_if_any(template=template, input_data=input_data)
        # TODO FLAG: OFF history flag injected here
        # TODO FEATURE: CONFIG PARAMETERS -> EMBEDDINGS

        client = OpenAI()

        # Create a streaming completion
        stream = client.chat.completions.create(
            model=self.provider.version,
            messages=message_list,
            max_tokens=4096,
            stream=True,  # Enable streaming
        )

        # Iterate over the streamed responses and yield the content
        output_data = []
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                output_data.append(content)
                yield content

        # add both the user and assistant generated data to the session
        self.update_session_data(
            input_data=input_data,
            input_template=template,
            output_data="".join(output_data))

    # def process_input_data_entry(self, input_query_state: dict, force: bool = False):
    #     input_query_state = [
    #         input_query
    #         for input_query in input_query_state
    #         if not isinstance(input_query, list)
    #     ]
    #     return super().process_input_data_entry(input_query_state=input_query_state, force=force)

    def _execute(self, user_prompt: str, system_prompt: str, values: dict):
        messages_dict = []

        if user_prompt:
            user_prompt = user_prompt.strip()
            messages_dict.append({
                "role": "user",
                "content": f"{user_prompt}"
            })

        if system_prompt:
            system_prompt = system_prompt.strip()
            messages_dict.append({
                "role": "system",
                "content": system_prompt
            })

        if not messages_dict:
            raise Exception(f'no prompts specified for values {values}')

        client = OpenAI(
            api_key=LLAMA_API_KEY,
            base_url=LLAMA_API_BASE_URL
        )

        stream = client.chat.completions.create(
            model=self.provider.version,
            messages=messages_dict,
            stream=False,
        )

        # calcualte the usage
        # calculate_usage(response=stream)

        # final raw response, without stripping or splitting
        raw_response = stream.choices[0].message.content
        return parse_response(raw_response=raw_response)

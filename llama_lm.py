import os.path
import time
from typing import Any

import openai
import dotenv
from core.base_processor_lm import BaseProcessorLM
from core.processor_state import StateConfigStream
from core.utils.ismlogging import ism_logger

from openai import OpenAI, Stream
from core.utils.general_utils import parse_response, build_template_text

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

    async def stream_input_data_entry(self, input_query_state: dict):
        if not self.stream_route:
            raise ValueError(
                f"streams are not supported by provider: {self.output_processor_state.id}, "
                f"route_id {self.output_processor_state.id}")

        if not input_query_state:
            raise ValueError("invalid input state, cannot be empty")

        if not isinstance(self.config, StateConfigStream):
            raise NotImplementedError()

        status, template = build_template_text(self.template, input_query_state)

        # this is a bit of a hack to use a session id for a given processor state stream
        if 'session_id' in input_query_state:
            session_id = input_query_state["session_id"]
            subject = f"processor.state.{self.output_state.id}.{session_id}"
        else:
            subject = f"processor.state.{self.output_state.id}"

        name = f"{subject}".replace("-", "_")

        # begin the processing of the prompts
        logging.debug(f"entered streaming mode, state_id: {self.output_state.id}")
        try:

            # submit to the fully qualified subject, which may include a session id
            stream_route = self.stream_route.clone(
                route_config_updates={
                    "subject": subject,
                    "name": name
                }
            )

            # submit the original request to the stream, such that it is broadcasted to all subscribers of the subject
            # TODO this needs to be invoked at the LM processor level, pre-stream-processing
            await stream_route.publish(input_query_state['source'])
            await stream_route.publish("<<>>SOURCE<<>>")
            await stream_route.publish(input_query_state['input'])
            await stream_route.publish("<<>>INPUT<<>>")
            await stream_route.flush()
            # await stream_route.drain()

            # execute the underlying model function
            stream = self._stream(
                input_data=input_query_state,
                template=template,
            )
            #
            # try:
            #     # Use explicit async iteration
            #     iterator = stream.__aiter__()
            #     while True:
            #         try:
            #             content = await iterator.__anext__()
            #         except StopAsyncIteration:
            #             break
            #         except Exception as iter_exception:
            #             # Log any exceptions encountered during iteration
            #             logging.warning(f'Exception during iteration: {iter_exception}', exc_info=True)
            #             continue
            #
            #         # Process the content if valid
            #         try:
            #             if isinstance(content, str):
            #                 await stream_route.publish(content)
            #                 await stream_route.flush()
            #             elif content is None:
            #                 # Log or handle the None case if necessary
            #                 logging.warning('Received NoneType content, skipping...')
            #             else:
            #                 # Handle unexpected types
            #                 logging.warning(f'Unexpected content type: {type(content)}')
            #         except Exception as process_exception:
            #             # Log exceptions encountered during processing
            #             logging.critical(f'Exception encountered during content processing: {process_exception}',
            #                              exc_info=True)
            #
            #
            # except Exception as critical:
            #     # Log any exceptions that occur in the overall streaming process
            #     logging.critical(f'Exception encountered during streaming: {critical}', exc_info=True)

            async for content in stream:
                try:
                    if isinstance(content, str):
                        await stream_route.publish(content)
                        await stream_route.flush()
                    elif content is None:
                        # Log or handle the None case if necessary
                        logging.warning('Received NoneType content, skipping...')
                    else:
                        # Handle unexpected types
                        logging.warning(f'Unexpected content type: {type(content)}')
                except Exception as critical:
                    # Provide more detailed exception handling
                    logging.critical(f'Exception encountered during streaming: {critical}', exc_info=True)

            # TODO this needs to be invoked at the LM processor level, post-stream-processing
            # submit the response message to the stream.
            await stream_route.publish("<<>>ASSISTANT<<>>")
            await stream_route.flush()
            # await stream_route.drain()

            time.sleep(2)

            # should gracefully close the connection
            await stream_route.disconnect()

            logging.debug(f"exit streaming mode, state_id: {self.output_state.id}")
        except Exception as exception:
            # submit the response message to the stream.
            await stream_route.publish("<<>>ERROR<<>>")
            await stream_route.flush()
            await stream_route.disconnect()
            await self.fail_execute_processor_state(
                # self.output_processor_state,
                route_id=self.output_processor_state.id,
                exception=exception,
                data=input_query_state
            )
    async def _stream(self, input_data: Any, template: str):
        if not template:
            template = str(input_data)

        # rendered message we want to submit to the model
        message_list = self.derive_messages_with_session_data_if_any(template=template, input_data=input_data)
        # TODO FLAG: OFF history flag injected here
        # TODO FEATURE: CONFIG PARAMETERS -> EMBEDDINGS

        client = OpenAI(
            api_key=LLAMA_API_KEY,
            base_url=LLAMA_API_BASE_URL
        )

        # Create a streaming completion
        stream = client.chat.completions.create(
            model=self.provider.version,
            messages=message_list,
            # max_tokens=2048,
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

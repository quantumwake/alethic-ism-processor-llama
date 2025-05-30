import asyncio
import os
import dotenv
from ismcore.messaging.base_message_consumer_processor import BaseMessageConsumerProcessor
from ismcore.messaging.base_message_router import Router
from ismcore.messaging.nats_message_provider import NATSMessageProvider
from ismcore.model.base_model import Processor, ProcessorProvider, ProcessorState
from ismcore.model.processor_state import State
from ismcore.processor.base_processor import (
    StatePropagationProviderDistributor, \
    StatePropagationProviderRouterStateSyncStore,
    StatePropagationProviderRouterStateRouter)

from ismcore.utils.ism_logger import ism_logger
from ismdb.postgres_storage_class import PostgresDatabaseStorage

from llama_lm import LlamaChatCompletionProcessor

dotenv.load_dotenv()

# message routing file, used for both ingress and egress message handling
ROUTING_FILE = os.environ.get("ROUTING_FILE", '.routing.yaml')

# database related
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres1@localhost:5432/postgres")

# state storage specifically to handle this processor state (stateless obj)
storage = PostgresDatabaseStorage(
    database_url=DATABASE_URL,
    incremental=True
)

# nats messaging provider is used, the routes are defined in the routing.yaml
message_provider = NATSMessageProvider()

# routing the persistence of individual state entries to the state sync store topic
router = Router(
    provider=message_provider,
    yaml_file=ROUTING_FILE
)

# find the monitor route for telemetry updates
monitor_route = router.find_route("processor/monitor")
llama_route = router.find_route_by_subject("processor.models.llama")
state_sync_route = router.find_route('processor/state/sync')
state_router_route = router.find_route('processor/state/router')
state_stream_route = router.find_route("processor/state")

state_propagation_provider = StatePropagationProviderDistributor(
    propagators=[
        StatePropagationProviderRouterStateSyncStore(route=state_sync_route),
        StatePropagationProviderRouterStateRouter(route=state_router_route, storage=storage)
    ]
)

logging = ism_logger(__name__)


class MessagingConsumerLlamaAPI(BaseMessageConsumerProcessor):

    def create_processor(self,
                         processor: Processor,
                         provider: ProcessorProvider,
                         output_processor_state: ProcessorState,
                         output_state: State):
        #
        logging.debug(f"received create processor request {provider.class_name}")

        if provider.class_name != "NaturalLanguageProcessing":
            raise NotImplementedError(f"provider type {provider.class_name} not supported by this processor")

        return LlamaChatCompletionProcessor(
            # storage class information
            state_machine_storage=storage,

            # state processing information
            output_state=output_state,
            provider=provider,
            processor=processor,
            output_processor_state=output_processor_state,

            # state information routing routers
            monitor_route=self.monitor_route,
            stream_route=state_stream_route,
            state_propagation_provider=state_propagation_provider,
        )


if __name__ == '__main__':
    consumer = MessagingConsumerLlamaAPI(
        storage=storage,
        route=llama_route,
        monitor_route=monitor_route
    )

    consumer.setup_shutdown_signal()
    asyncio.get_event_loop().run_until_complete(consumer.start_consumer())

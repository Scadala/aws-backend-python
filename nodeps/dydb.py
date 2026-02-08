import logging

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

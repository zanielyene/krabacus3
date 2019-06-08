from huey import RedisHuey
import logging
import os

is_docker = os.environ.get('IS_IN_CONTAINER', False)

logger=logging.getLogger(__name__)
if is_docker:
    raise Exception("configure me")
    player_queue = RedisHuey(url="redis://redis:6379/1")
    history_queue = RedisHuey(url="redis://redis:6379/1")
    general_queue = RedisHuey(url="redis://redis:6379/1")
else:
    player_queue = RedisHuey(name="player_queue", url="redis://localhost:6379/1", global_registry=False)
    history_queue = RedisHuey(name="history_queue", url="redis://localhost:6379/1", global_registry=False)
    general_queue = RedisHuey(name="general_queue", url="redis://localhost:6379/1", global_registry=False)



HUEY_QUEUES = {
    "player_queue": player_queue,
    "general_queue": general_queue,
    "history_queue": history_queue
}


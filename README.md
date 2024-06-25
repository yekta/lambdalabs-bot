It's a bot for continuously checking the availability of an instance on Lambda Labs and launching when an instance is found. Here are the example environment variables for launching the bot:

```ini
LAMBDA_API_KEY=YOUR_LAMBDA_API_KEY
INSTANCE_TYPE_NAME=gpu_1x_a6000
SSH_KEY_NAME=NAME_OF_YOUR_SSH_KEY
CHECK_INTERVAL_SECONDS=10
ERROR_WAIT_SECONDS=10
PORT=5000
```

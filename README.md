This is the source code for krabacus.

It should pretty much work with the exception of the payment module since it uses the old, removed journal endpoint.

scripts/deploy_krabacus.sh and the supervisor launcher scripts should help you get started on the production side of things

these commands should launch the huey workers for each task queue

python ./manage.py run_consumer --queue general_queue --worker-type process --workers 2

python ./manage.py run_consumer --queue player_queue --worker-type process --workers 2

python ./manage.py run_consumer --queue history_queue --worker-type process --workers 2

use eve_api.bootstrap_esi_database to bootstrap all the universe data types and stuff. im too cool to use fixtures.
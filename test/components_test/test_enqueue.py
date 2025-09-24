import time
# We need to import the broker instance from our app
from assessment_service.app.broker import redis_broker
# We also need to import the actor function itself
from assessment_service.app.tasks import scheduler_tick

print("This script will manually send two tasks to the 'default' queue.")

print("Sending task 1...")
scheduler_tick.send()
print("Task 1 sent.")

# Wait a moment to ensure the tasks are sent separately
time.sleep(2)

print("Sending task 2...")
scheduler_tick.send()
print("Task 2 sent.")

print("Done. Check your dramatiq worker's output.")
